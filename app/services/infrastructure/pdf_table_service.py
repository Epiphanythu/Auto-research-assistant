"""pdf_table_service PDF 表格抽取服务。"""

from __future__ import annotations

import io
import logging
from typing import List, Tuple

from app.constant.benchmark_alias_constant import (
    normalize_dataset_name,
    normalize_metric_name,
)
from app.constant.pdf_table_constant import (
    PDF_TABLE_MAX_RESULT_ROWS,
    PDF_TABLE_METHOD_HEADER_KEYWORDS,
    PDF_TABLE_METRIC_HEADER_KEYWORDS,
    PDF_TABLE_PAGE_LIMIT,
)
from app.models.research_models import QuantitativeResult

logger = logging.getLogger(__name__)


class PdfTableService:
    """PdfTableService 基于 pdfplumber 的论文表格抽取器。"""

    def extract_tables(self, pdf_bytes: bytes, paper_id: str) -> List[QuantitativeResult]:
        """extract_tables 从 PDF 字节流抽取定量结果表格。"""
        # 1. 延迟导入 pdfplumber，避免在未启用全文模式时引入依赖开销
        try:
            import pdfplumber
        except ImportError:
            logger.info("PdfTableService.extract_tables pdfplumber not installed, paper_id=%s", paper_id)
            return []
        # 2. 打开 PDF 并按页扫描表格，遇异常即兜底返回空列表
        results: List[QuantitativeResult] = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page_limit = min(len(pdf.pages), PDF_TABLE_PAGE_LIMIT)
                for page_index in range(page_limit):
                    if len(results) >= PDF_TABLE_MAX_RESULT_ROWS:
                        break
                    page_results = self._extract_page_tables(pdf.pages[page_index])
                    for item in page_results:
                        if len(results) >= PDF_TABLE_MAX_RESULT_ROWS:
                            break
                        results.append(item)
        except Exception as error:  # pragma: no cover - 第三方解析失败兜底
            logger.info(
                "PdfTableService.extract_tables failed, paper_id=%s, error=%s",
                paper_id, error,
            )
            return []
        logger.info(
            "PdfTableService.extract_tables completed, paper_id=%s, row_count=%s",
            paper_id, len(results),
        )
        return results

    def _extract_page_tables(self, page) -> List[QuantitativeResult]:
        """_extract_page_tables 解析单页的所有候选表格。"""
        # 1. 尝试抽取页内所有表格，pdfplumber 在无表格时会返回空列表
        try:
            tables = page.extract_tables() or []
        except Exception:
            return []
        page_results: List[QuantitativeResult] = []
        for table in tables:
            if not table or len(table) < 2:
                continue
            header = [self._clean_cell(cell) for cell in table[0]]
            method_idx, metric_columns = self._classify_header(header)
            if method_idx is None or not metric_columns:
                continue
            # 2. 遍历数据行，组合 (method, metric, value) 三元组
            for row in table[1:]:
                if not row:
                    continue
                cells = [self._clean_cell(cell) for cell in row]
                if method_idx >= len(cells):
                    continue
                dataset_value = cells[method_idx]
                if not dataset_value:
                    continue
                for col_idx, metric_label in metric_columns:
                    if col_idx >= len(cells):
                        continue
                    value = cells[col_idx]
                    if not value:
                        continue
                    page_results.append(
                        QuantitativeResult(
                            dataset=normalize_dataset_name(dataset_value),
                            metric=normalize_metric_name(metric_label),
                            value=value,
                            baseline="",
                        )
                    )
        return page_results

    @staticmethod
    def _classify_header(header: List[str]) -> Tuple[int | None, List[Tuple[int, str]]]:
        """_classify_header 判断表头是否符合方法 × 指标格式，并定位列索引。"""
        method_idx: int | None = None
        metric_columns: List[Tuple[int, str]] = []
        for index, cell in enumerate(header):
            lowered = cell.lower()
            if not lowered:
                continue
            if method_idx is None and any(kw in lowered for kw in PDF_TABLE_METHOD_HEADER_KEYWORDS):
                method_idx = index
                continue
            if any(kw in lowered for kw in PDF_TABLE_METRIC_HEADER_KEYWORDS):
                metric_columns.append((index, cell))
        return method_idx, metric_columns

    @staticmethod
    def _clean_cell(cell) -> str:
        """_clean_cell 规整表格单元格文本。"""
        if cell is None:
            return ""
        text = str(cell).replace("\n", " ").strip()
        while "  " in text:
            text = text.replace("  ", " ")
        return text
