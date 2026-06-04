"""arxiv_client arXiv 检索客户端。"""

from __future__ import annotations

from typing import List
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import requests

from app.api_error import SearchResponseParseError, SearchSourceUnavailableError
from app.config import get_settings
from app.constant.paper_constant import ARXIV_API_URL, PAPER_SOURCE_ARXIV
from app.models.research_models import Paper


class ArxivClient:
    """ArxivClient arXiv API 客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def search_papers(self, query: str, max_results: int) -> List[Paper]:
        """search_papers 根据查询词搜索论文。"""
        # 1. 构造请求参数。
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
        }
        try:
            response = requests.get(
                f"{ARXIV_API_URL}?{urlencode(params)}",
                timeout=self.settings.get_request_timeout_seconds(),
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise SearchSourceUnavailableError("arXiv", str(error)) from error

        # 2. 解析 Atom XML，统一映射为 Paper 模型。
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as error:
            raise SearchResponseParseError("arXiv", str(error)) from error
        papers: List[Paper] = []
        for entry in root.findall("atom:entry", namespace):
            paper_id = self._read_text(entry, "atom:id", namespace).split("/")[-1]
            title = self._clean_text(self._read_text(entry, "atom:title", namespace))
            summary = self._clean_text(self._read_text(entry, "atom:summary", namespace))
            published = self._read_text(entry, "atom:published", namespace)
            authors = [
                self._clean_text(author.findtext("{http://www.w3.org/2005/Atom}name", default=""))
                for author in entry.findall("atom:author", namespace)
            ]
            pdf_url = self._extract_pdf_url(entry, namespace)
            papers.append(
                Paper(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    summary=summary,
                    published=published,
                    pdf_url=pdf_url,
                    source=PAPER_SOURCE_ARXIV,
                )
            )
        return papers

    @staticmethod
    def _read_text(entry: ET.Element, tag: str, namespace: dict) -> str:
        """_read_text 读取节点文本。"""
        return entry.findtext(tag, default="", namespaces=namespace)

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """_clean_text 规整文本空白。"""
        return " ".join(raw_text.split())

    @staticmethod
    def _extract_pdf_url(entry: ET.Element, namespace: dict) -> str:
        """_extract_pdf_url 提取 PDF 链接。"""
        for link in entry.findall("atom:link", namespace):
            title = link.attrib.get("title", "")
            if title == "pdf":
                return link.attrib.get("href", "")
        return ""
