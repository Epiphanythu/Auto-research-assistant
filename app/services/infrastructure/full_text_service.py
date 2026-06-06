"""full_text_service PDF 全文解析服务。"""

from __future__ import annotations

import io
import logging
import re

import requests
from pypdf import PdfReader

from app.api_error import FullTextBatchError, FullTextDownloadError, FullTextParseError
from app.config import get_settings
from app.constant.paper_constant import (
    DEFAULT_FULL_TEXT_CHUNK_CHAR_LIMIT,
    DEFAULT_FULL_TEXT_MIN_TEXT_LENGTH,
    DEFAULT_FULL_TEXT_PAGE_LIMIT,
    FULL_TEXT_SOURCE_PDF,
    SECTION_HEADING_PATTERNS,
    SECTION_KIND_OTHER,
)
from app.models.research_models import FullTextChunk, FullTextDocument, Paper
from app.services.infrastructure.pdf_table_service import PdfTableService

logger = logging.getLogger(__name__)

# 编译一次 section 标题匹配正则，提升解析效率
_SECTION_PATTERNS_COMPILED: list[tuple[str, re.Pattern]] = [
    (kind, re.compile(pattern, flags=re.IGNORECASE))
    for kind, pattern in SECTION_HEADING_PATTERNS
]
# 章节标题候选行的最大长度（标题通常不会太长，避免把正文整段当成标题）
_SECTION_HEADING_MAX_LEN = 80


class FullTextService:
    """FullTextService PDF 全文获取与分块器。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def load_documents(
        self,
        papers: list[Paper],
        max_papers: int,
    ) -> dict[str, FullTextDocument]:
        """load_documents 为候选论文加载全文文档。"""
        # 1. 只处理前 N 篇论文，控制运行成本与时延。
        logger.info(
            "FullTextService.load_documents start, candidate_count=%s, max_papers=%s",
            len(papers),
            max_papers,
        )
        documents: dict[str, FullTextDocument] = {}
        load_errors: list[Exception] = []
        for paper in papers[:max_papers]:
            try:
                document = self.load_document(paper)
            except (FullTextDownloadError, FullTextParseError) as error:
                load_errors.append(error)
                logger.info(
                    "FullTextService.load_documents document failed, paper_id=%s, error_code=%s, detail=%s",
                    paper.paper_id,
                    error.error_code,
                    error.detail,
                )
                continue
            if document and document.chunks:
                documents[paper.paper_id] = document
                logger.info(
                    "FullTextService.load_documents loaded document, paper_id=%s, chunk_count=%s, page_count=%s",
                    paper.paper_id,
                    len(document.chunks),
                    document.page_count,
                )
            else:
                logger.info(
                    "FullTextService.load_documents skip empty document, paper_id=%s, source=%s",
                    paper.paper_id,
                    paper.source,
                )
        if not documents and load_errors:
            logger.warning(
                "FullTextService.load_documents all documents failed, degrading to abstract-only mode. error_count=%s, last_error=%s",
                len(load_errors),
                load_errors[0].detail,
            )
            return {}
        logger.info(
            "FullTextService.load_documents completed, loaded_count=%s",
            len(documents),
        )
        return documents

    def load_document(self, paper: Paper) -> FullTextDocument | None:
        """load_document 加载单篇论文的全文文档。"""
        # 1. 优先下载 PDF 并抽取正文文本。
        logger.info(
            "FullTextService.load_document start, paper_id=%s, source=%s, has_pdf_url=%s",
            paper.paper_id,
            paper.source,
            bool(paper.pdf_url.strip()),
        )
        if not paper.pdf_url.strip():
            logger.info("FullTextService.load_document missing pdf url, paper_id=%s", paper.paper_id)
            return None
        try:
            response = requests.get(
                paper.pdf_url,
                timeout=self.settings.get_request_timeout_seconds(),
            )
            response.raise_for_status()
            logger.info(
                "FullTextService.load_document pdf downloaded, paper_id=%s, bytes=%s",
                paper.paper_id,
                len(response.content),
            )
        except requests.RequestException as error:
            logger.info(
                "FullTextService.load_document pdf download failed, paper_id=%s, error=%s",
                paper.paper_id,
                error,
            )
            raise FullTextDownloadError(paper.paper_id, str(error)) from error
        return self._parse_pdf_bytes(
            paper_id=paper.paper_id,
            pdf_bytes=response.content,
        )

    def _parse_pdf_bytes(self, paper_id: str, pdf_bytes: bytes) -> FullTextDocument | None:
        """_parse_pdf_bytes 从 PDF 字节流中解析章节感知的全文分块。"""
        # 1. 读取 PDF。
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            logger.info(
                "FullTextService._parse_pdf_bytes reader ready, paper_id=%s, page_count=%s",
                paper_id,
                len(reader.pages),
            )
        except Exception as error:
            logger.info(
                "FullTextService._parse_pdf_bytes parse failed, paper_id=%s, error=%s",
                paper_id,
                error,
            )
            raise FullTextParseError(paper_id, str(error)) from error

        # 2. 逐页提取原始行，附带页码。
        page_limit = min(len(reader.pages), DEFAULT_FULL_TEXT_PAGE_LIMIT)
        page_lines: list[tuple[int, list[str]]] = []
        failed_pages = 0
        total_chars = 0
        for page_index in range(page_limit):
            try:
                raw_text = reader.pages[page_index].extract_text() or ""
            except Exception as error:
                failed_pages += 1
                logger.info(
                    "FullTextService._parse_pdf_bytes page extract failed, paper_id=%s, page=%s, error=%s",
                    paper_id, page_index + 1, error,
                )
                raw_text = ""
            lines = self._split_into_lines(raw_text)
            page_lines.append((page_index + 1, lines))
            total_chars += sum(len(line) for line in lines)

        if total_chars < DEFAULT_FULL_TEXT_MIN_TEXT_LENGTH:
            if failed_pages == page_limit and page_limit > 0:
                raise FullTextParseError(paper_id, "所有页面在正文抽取阶段均失败。")
            logger.info(
                "FullTextService._parse_pdf_bytes empty document, paper_id=%s, total_chars=%s",
                paper_id, total_chars,
            )
            return None

        # 3. 按行级流式解析，识别章节标题并归并到 (section_title, section_kind) 段落。
        sections = self._segment_by_section(page_lines)
        if not sections:
            logger.info("FullTextService._parse_pdf_bytes no sections detected, paper_id=%s", paper_id)
            return None

        # 4. 章节内部按字符上限切分为 chunk，保留 page/section/section_kind 元信息。
        chunks: list[FullTextChunk] = []
        for section_title, section_kind, page, body in sections:
            chunks.extend(
                self._chunk_section_body(
                    body=body,
                    section_title=section_title,
                    section_kind=section_kind,
                    page=page,
                )
            )

        if not chunks:
            logger.info("FullTextService._parse_pdf_bytes empty chunks, paper_id=%s", paper_id)
            return None

        # 5. 调用 pdfplumber 抽取表格作为定量结果，失败时仅落空列表不阻断主流程
        tables = PdfTableService().extract_tables(pdf_bytes, paper_id)

        logger.info(
            "FullTextService._parse_pdf_bytes completed, paper_id=%s, sections=%s, chunks=%s, tables=%s",
            paper_id, len(sections), len(chunks), len(tables),
        )
        return FullTextDocument(
            paper_id=paper_id,
            source=FULL_TEXT_SOURCE_PDF,
            page_count=page_limit,
            chunks=chunks,
            tables=tables,
        )

    @staticmethod
    def _split_into_lines(text: str) -> list[str]:
        """_split_into_lines 把 PDF 抽取的文本按换行切分并清洗。"""
        # 1. 把多空格折叠为一个空格，但保留换行作为行分隔。
        if not text:
            return []
        lines = text.splitlines()
        cleaned: list[str] = []
        for line in lines:
            collapsed = re.sub(r"[\t\f\v]+", " ", line)
            collapsed = re.sub(r" +", " ", collapsed).strip()
            if collapsed:
                cleaned.append(collapsed)
        return cleaned

    @staticmethod
    def _classify_heading(line: str) -> tuple[str, str] | None:
        """_classify_heading 判断某行是否为章节标题，返回 (kind, normalized_title) 或 None。"""
        # 1. 标题不会太长，长行直接判断为正文。
        if not line or len(line) > _SECTION_HEADING_MAX_LEN:
            return None
        # 2. 用预编译规则匹配一次，避免重复正则编译开销。
        for kind, pattern in _SECTION_PATTERNS_COMPILED:
            if pattern.search(line):
                return kind, line.strip()
        return None

    def _segment_by_section(
        self,
        page_lines: list[tuple[int, list[str]]],
    ) -> list[tuple[str, str, int, str]]:
        """_segment_by_section 把页内行流式切分为 (section_title, section_kind, page, body) 列表。"""
        # 1. 初始化游标，未识别到章节前默认归入 "Preamble / other"。
        sections: list[tuple[str, str, int, list[str]]] = []
        current_title = "Preamble"
        current_kind = SECTION_KIND_OTHER
        current_page = 1
        current_buffer: list[str] = []

        # 2. 顺序扫描每一行，遇到章节标题就 flush 当前段落并开启新段。
        for page, lines in page_lines:
            if not current_buffer and not sections:
                current_page = page
            for line in lines:
                heading = self._classify_heading(line)
                if heading is not None:
                    if current_buffer:
                        sections.append(
                            (current_title, current_kind, current_page, list(current_buffer))
                        )
                    kind, title = heading
                    current_title = title
                    current_kind = kind
                    current_page = page
                    current_buffer = []
                else:
                    current_buffer.append(line)

        # 3. 收尾：把最后一段也写入。
        if current_buffer:
            sections.append((current_title, current_kind, current_page, list(current_buffer)))

        # 4. 把 list[str] body 拼成段落字符串后返回。
        merged: list[tuple[str, str, int, str]] = []
        for title, kind, page, body in sections:
            text = " ".join(body).strip()
            if len(text) >= 80:
                merged.append((title, kind, page, text))
        return merged

    def _chunk_section_body(
        self,
        body: str,
        section_title: str,
        section_kind: str,
        page: int,
    ) -> list[FullTextChunk]:
        """_chunk_section_body 把单个章节正文切分为多个 chunk，受字符上限约束。"""
        # 1. 以句子为最小切块单元，避免破坏语义。
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?。；;])\s+", body)
            if sentence.strip()
        ]
        if not sentences:
            return []

        # 2. 累积到字符上限就 flush 一个 chunk，剩余继续累积。
        chunks: list[FullTextChunk] = []
        buffer: list[str] = []
        for sentence in sentences:
            candidate = " ".join(buffer + [sentence]).strip()
            if buffer and len(candidate) > DEFAULT_FULL_TEXT_CHUNK_CHAR_LIMIT:
                chunks.append(
                    FullTextChunk(
                        text=" ".join(buffer).strip(),
                        section=section_title,
                        section_kind=section_kind,
                        page=page,
                    )
                )
                buffer = [sentence]
                continue
            buffer.append(sentence)
        if buffer:
            chunks.append(
                FullTextChunk(
                    text=" ".join(buffer).strip(),
                    section=section_title,
                    section_kind=section_kind,
                    page=page,
                )
            )
        return chunks
