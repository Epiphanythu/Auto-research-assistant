"""crossref_client CrossRef API 客户端。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.api_error import SearchSourceUnavailableError
from app.config import get_settings

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"


class CrossRefClient:
    """CrossRefClient CrossRef 元数据客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout = 20

    def search_papers(self, query: str, max_results: int = 5, year_from: Optional[int] = None) -> List[Dict[str, Any]]:
        """search_papers 搜索论文，获取 DOI、标题、引用计数、发表日期等。"""
        params = {
            "query": query,
            "rows": max_results,
            "sort": "relevance",
        }
        filter_parts = ["has-full-text:true"]
        if year_from:
            filter_parts.append(f"from-pub-date:{year_from}")
        params["filter"] = ",".join(filter_parts)
        headers = {"User-Agent": "AutoResearchAssistant/1.0 (mailto:research@example.com)"}
        try:
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SearchSourceUnavailableError("CrossRef", str(error)) from error

        try:
            items = response.json().get("message", {}).get("items", [])
        except ValueError as error:
            raise SearchSourceUnavailableError("CrossRef", f"parse error: {error}") from error

        results: List[Dict[str, Any]] = []
        for item in items:
            title_list = item.get("title", [])
            title = title_list[0] if title_list else ""
            if not title:
                continue
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                full = f"{given} {family}".strip()
                if full:
                    authors.append(full)
            doi = item.get("DOI", "")
            results.append({
                "doi": doi,
                "title": " ".join(title.split()),
                "authors": authors,
                "published_date": item.get("published-print", {}).get("date-parts", [[""]])[0][0] if item.get("published-print") else "",
                "citation_count": item.get("is-referenced-by-count", 0),
                "type": item.get("type", ""),
                "url": item.get("URL", ""),
                "container_title": item.get("container-title", [""])[0] if item.get("container-title") else "",
            })
        return results

    def get_paper_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """get_paper_by_doi 根据 DOI 获取论文元数据。"""
        try:
            response = requests.get(
                f"{CROSSREF_API_URL}/{doi}",
                timeout=self.timeout,
                headers={"User-Agent": "AutoResearchAssistant/1.0 (mailto:research@example.com)"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("CrossRef.get_paper_by_doi failed: %s", error)
            return None
        try:
            return response.json().get("message", {})
        except ValueError:
            return None

    def get_citation_count(self, doi: str) -> int:
        """get_citation_count 获取单篇论文被引次数。"""
        paper = self.get_paper_by_doi(doi)
        if paper:
            return paper.get("is-referenced-by-count", 0)
        return 0

    def get_reference_dois(self, doi: str) -> List[str]:
        """get_reference_dois 获取论文参考文献的 DOI 列表。"""
        paper = self.get_paper_by_doi(doi)
        if not paper:
            return []
        return [ref.get("DOI", "") for ref in paper.get("reference", []) if ref.get("DOI")]
