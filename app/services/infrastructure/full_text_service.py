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
)
from app.models.research_models import FullTextChunk, FullTextDocument, Paper

logger = logging.getLogger(__name__)


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
        """_parse_pdf_bytes 从 PDF 字节流中解析全文分块。"""
        # 1. 逐页提取文本，并在页内进一步分块，保留 page 与 section 信息。
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

        chunks: list[FullTextChunk] = []
        page_limit = min(len(reader.pages), DEFAULT_FULL_TEXT_PAGE_LIMIT)
        failed_pages = 0
        for page_index in range(page_limit):
            try:
                raw_text = reader.pages[page_index].extract_text() or ""
            except Exception as error:
                failed_pages += 1
                logger.info(
                    "FullTextService._parse_pdf_bytes page extract failed, paper_id=%s, page=%s, error=%s",
                    paper_id,
                    page_index + 1,
                    error,
                )
                raw_text = ""
            normalized_text = self._normalize_text(raw_text)
            if len(normalized_text) < DEFAULT_FULL_TEXT_MIN_TEXT_LENGTH:
                logger.info(
                    "FullTextService._parse_pdf_bytes skip short page, paper_id=%s, page=%s, text_length=%s",
                    paper_id,
                    page_index + 1,
                    len(normalized_text),
                )
                continue
            page_chunks = self._chunk_page_text(
                normalized_text,
                page=page_index + 1,
            )
            chunks.extend(page_chunks)
            logger.info(
                "FullTextService._parse_pdf_bytes page parsed, paper_id=%s, page=%s, chunk_count=%s",
                paper_id,
                page_index + 1,
                len(page_chunks),
            )

        # 2. 若抽取不到有效正文，则返回空结果。
        if not chunks:
            if failed_pages == page_limit and page_limit > 0:
                raise FullTextParseError(paper_id, "所有页面在正文抽取阶段均失败。")
            logger.info("FullTextService._parse_pdf_bytes empty document, paper_id=%s", paper_id)
            return None
        logger.info(
            "FullTextService._parse_pdf_bytes completed, paper_id=%s, total_chunks=%s",
            paper_id,
            len(chunks),
        )
        return FullTextDocument(
            paper_id=paper_id,
            source=FULL_TEXT_SOURCE_PDF,
            page_count=page_limit,
            chunks=chunks,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """_normalize_text 规整 PDF 提取文本。"""
        collapsed_text = re.sub(r"\s+", " ", text)
        return collapsed_text.strip()

    def _chunk_page_text(self, page_text: str, page: int) -> list[FullTextChunk]:
        """_chunk_page_text 将单页正文按长度分块。"""
        # 1. 以句子为边界切块，避免纯长度切分破坏语义连续性。
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?。；;])\s+", page_text)
            if sentence.strip()
        ]
        if not sentences:
            return []

        # 2. 累积句子到上限后输出 chunk，并为每个 chunk 推断 section 名。
        chunks: list[FullTextChunk] = []
        buffer: list[str] = []
        for sentence in sentences:
            candidate = " ".join(buffer + [sentence]).strip()
            if buffer and len(candidate) > DEFAULT_FULL_TEXT_CHUNK_CHAR_LIMIT:
                chunk_text = " ".join(buffer).strip()
                chunks.append(
                    FullTextChunk(
                        text=chunk_text,
                        section=self._infer_section_name(chunk_text, page),
                        page=page,
                    )
                )
                buffer = [sentence]
                continue
            buffer.append(sentence)
        if buffer:
            chunk_text = " ".join(buffer).strip()
            chunks.append(
                FullTextChunk(
                    text=chunk_text,
                    section=self._infer_section_name(chunk_text, page),
                    page=page,
                )
            )
        return chunks

    @staticmethod
    def _infer_section_name(chunk_text: str, page: int) -> str:
        """_infer_section_name 根据 chunk 首行推断 section。"""
        heading_match = re.match(r"^\s*([A-Z][A-Za-z0-9\s\-:]{2,60})", chunk_text)
        if heading_match:
            return heading_match.group(1).strip()
        return f"Page {page}"
