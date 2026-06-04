"""openalex_client OpenAlex 检索客户端。"""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from app.api_error import SearchResponseParseError, SearchSourceUnavailableError
from app.config import get_settings
from app.constant.paper_constant import OPENALEX_API_URL, PAPER_SOURCE_OPENALEX
from app.models.research_models import Paper


class OpenAlexClient:
    """OpenAlexClient OpenAlex API 客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def search_papers(self, query: str, max_results: int) -> List[Paper]:
        """search_papers 根据查询词搜索论文。"""
        # 1. 调用 OpenAlex works 搜索接口，优先获取带摘要的结果。
        try:
            response = requests.get(
                OPENALEX_API_URL,
                params={
                    "search": query,
                    "per-page": max_results,
                    "filter": "has_abstract:true,is_oa:true",
                    "sort": "relevance_score:desc",
                },
                timeout=self.settings.get_request_timeout_seconds(),
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SearchSourceUnavailableError("OpenAlex", str(error)) from error

        # 2. 将 OpenAlex 结果统一映射为 Paper 模型。
        try:
            payload = response.json()
        except ValueError as error:
            raise SearchResponseParseError("OpenAlex", str(error)) from error
        papers: List[Paper] = []
        for result in payload.get("results", []):
            summary = self._extract_summary(result)
            if not summary:
                continue
            papers.append(
                Paper(
                    paper_id=self._extract_paper_id(result),
                    title=self._clean_text(str(result.get("title", ""))),
                    authors=self._extract_authors(result),
                    summary=summary,
                    published=str(result.get("publication_date", "")),
                    pdf_url=self._extract_best_url(result),
                    source=PAPER_SOURCE_OPENALEX,
                )
            )
        return papers

    @staticmethod
    def _extract_paper_id(result: Dict[str, Any]) -> str:
        """_extract_paper_id 提取论文唯一标识。"""
        openalex_id = str(result.get("id", ""))
        if openalex_id:
            return openalex_id.rstrip("/").split("/")[-1]
        doi = str(result.get("doi", ""))
        return doi or "unknown-openalex-id"

    @staticmethod
    def _extract_authors(result: Dict[str, Any]) -> List[str]:
        """_extract_authors 提取作者列表。"""
        authors: List[str] = []
        for authorship in result.get("authorships", []):
            author = authorship.get("author", {})
            display_name = str(author.get("display_name", "")).strip()
            if display_name:
                authors.append(display_name)
        return authors

    @classmethod
    def _extract_summary(cls, result: Dict[str, Any]) -> str:
        """_extract_summary 提取摘要。"""
        abstract = cls._reconstruct_abstract(
            result.get("abstract_inverted_index", {}) or {}
        )
        return cls._clean_text(abstract)

    @staticmethod
    def _reconstruct_abstract(abstract_index: Dict[str, List[int]]) -> str:
        """_reconstruct_abstract 从倒排索引重建摘要文本。"""
        if not abstract_index:
            return ""
        max_position = max(
            (position for positions in abstract_index.values() for position in positions),
            default=-1,
        )
        if max_position < 0:
            return ""
        tokens = [""] * (max_position + 1)
        for word, positions in abstract_index.items():
            for position in positions:
                if 0 <= position <= max_position:
                    tokens[position] = word
        return " ".join(token for token in tokens if token).strip()

    @classmethod
    def _extract_best_url(cls, result: Dict[str, Any]) -> str:
        """_extract_best_url 提取最佳跳转链接。"""
        primary_location = result.get("primary_location", {}) or {}
        if primary_location.get("pdf_url"):
            return str(primary_location["pdf_url"])
        if primary_location.get("landing_page_url"):
            return str(primary_location["landing_page_url"])
        best_oa_location = result.get("best_oa_location", {}) or {}
        if best_oa_location.get("pdf_url"):
            return str(best_oa_location["pdf_url"])
        if best_oa_location.get("landing_page_url"):
            return str(best_oa_location["landing_page_url"])
        return ""

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """_clean_text 规整文本空白。"""
        return " ".join(raw_text.split())
