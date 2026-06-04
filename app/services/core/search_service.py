"""search_service 论文检索服务（并行多源）。"""

from __future__ import annotations

import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.api_error import (
    APIError,
    SearchAggregationError,
    SearchSourceUnavailableError,
)
from app.clients.arxiv_client import ArxivClient
from app.clients.crossref_client import CrossRefClient
from app.clients.openalex_client import OpenAlexClient
from app.clients.semantic_scholar_client import SemanticScholarClient
from app.constant.paper_constant import (
    DEFAULT_SOURCE_SEARCH_LIMIT,
    PAPER_SOURCE_PRIORITY,
    PAPER_SOURCE_CROSSREF,
    PAPER_SOURCE_SEMANTIC_SCHOLAR,
)
from app.models.research_models import Paper, ResearchPlan, ResearchRequest
from app.services.infrastructure.search_cache import SearchCache, get_search_cache

logger = logging.getLogger(__name__)

SEARCH_MAX_WORKERS = 6


class SearchService:
    """SearchService 论文检索服务（并行多源聚合）。"""

    def __init__(self, cache: SearchCache | None = None) -> None:
        self.arxiv_client = ArxivClient()
        self.openalex_client = OpenAlexClient()
        self.s2_client = SemanticScholarClient()
        self.crossref_client = CrossRefClient()
        self._cache = cache

    def search(self, request: ResearchRequest, plan: ResearchPlan) -> List[Paper]:
        """search 根据规划检索候选论文。"""
        return self.search_by_queries(
            queries=plan.search_keywords,
            max_papers=request.get_max_papers(),
        )

    def search_by_queries(
        self,
        queries: List[str],
        max_papers: int,
    ) -> List[Paper]:
        """search_by_queries 根据查询数组执行并行多源检索。"""
        normalized_queries = [query for query in queries if query.strip()]
        logger.info(
            "SearchService.search_by_queries start, queries=%s, max_papers=%s",
            normalized_queries,
            max_papers,
        )
        unique_papers: dict[str, Paper] = {}
        query_errors: list[APIError] = []

        per_query_limit = min(max_papers, DEFAULT_SOURCE_SEARCH_LIMIT)

        # 并行执行所有关键词 x 所有源的检索
        with ThreadPoolExecutor(max_workers=SEARCH_MAX_WORKERS) as executor:
            futures = {}
            for query in normalized_queries:
                for source_name, client in [
                    ("SemanticScholar", self.s2_client),
                    ("OpenAlex", self.openalex_client),
                    ("arXiv", self.arxiv_client),
                    ("CrossRef", self.crossref_client),
                ]:
                    future = executor.submit(
                        self._search_source, source_name, client, query, per_query_limit,
                    )
                    futures[future] = (source_name, query)

            for future in as_completed(futures):
                source_name, query = futures[future]
                try:
                    papers = future.result()
                    logger.info(
                        "SearchService: %s returned %d papers for query=%s",
                        source_name, len(papers), query,
                    )
                    for paper in papers:
                        self._merge_paper(unique_papers, paper)
                except APIError as error:
                    query_errors.append(error)
                    logger.info(
                        "SearchService: %s failed for query=%s, error=%s",
                        source_name, query, error.detail,
                    )
                except Exception as error:
                    logger.warning(
                        "SearchService: %s unexpected failure for query=%s: %s",
                        source_name, query, error,
                    )

        if not unique_papers and query_errors:
            raise SearchAggregationError(
                detail=f"当前研究任务的检索请求全部失败。最近错误：{query_errors[0].detail}",
                suggestion="请检查外部学术检索源的可访问性、网络状态，或稍后重试。",
            )

        papers = self._rank_papers(list(unique_papers.values()), normalized_queries)
        logger.info(
            "SearchService.search_by_queries completed, unique=%d, returned=%d",
            len(unique_papers), min(len(papers), max_papers),
        )
        return papers[:max_papers]

    def _search_source(self, source_name: str, client: object, query: str, limit: int) -> List[Paper]:
        """_search_source 单源检索（带缓存）。"""
        cache = self._cache or get_search_cache()
        cached = cache.get(query, source_name)
        if cached is not None:
            return cached

        if source_name == "SemanticScholar":
            papers = self._search_s2(query, limit)
        elif source_name == "CrossRef":
            papers = self._search_crossref(query, limit)
        else:
            papers = client.search_papers(query, limit)  # type: ignore[union-attr]

        if papers:
            cache.put(query, source_name, papers)
        return papers

    def _search_s2(self, query: str, limit: int) -> List[Paper]:
        """_search_s2 Semantic Scholar 检索并映射为 Paper 模型。"""
        raw_results = self.s2_client.search_papers(query, limit)
        papers: List[Paper] = []
        for item in raw_results:
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstract") or "").strip()
            if not title or not abstract:
                continue
            authors = [a.get("name", "").strip() for a in (item.get("authors") or []) if a.get("name")]
            ext_ids = item.get("externalIds") or {}
            paper_id = ext_ids.get("ArXiv") or ext_ids.get("DOI") or item.get("paperId", "")
            tldr = ""
            tldr_obj = item.get("tldr")
            if isinstance(tldr_obj, dict):
                tldr = tldr_obj.get("text", "")
            oa_pdf = item.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url", "") if isinstance(oa_pdf, dict) else ""
            summary = tldr if tldr else abstract
            pub_date = str(item.get("publicationDate") or item.get("year") or "")
            papers.append(Paper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                summary=summary,
                published=pub_date,
                pdf_url=pdf_url,
                source=PAPER_SOURCE_SEMANTIC_SCHOLAR,
            ))
        return papers

    def _search_crossref(self, query: str, limit: int) -> List[Paper]:
        """_search_crossref CrossRef 检索并映射为 Paper 模型。"""
        raw_results = self.crossref_client.search_papers(query, limit)
        papers: List[Paper] = []
        for item in raw_results:
            title = item.get("title", "").strip()
            if not title:
                continue
            papers.append(Paper(
                paper_id=item.get("doi", ""),
                title=title,
                authors=item.get("authors", []),
                summary=f"Journal: {item.get('container_title', '')}. Cited by {item.get('citation_count', 0)}.",
                published=str(item.get("published_date", "")),
                pdf_url=item.get("url", ""),
                source=PAPER_SOURCE_CROSSREF,
            ))
        return papers

    @staticmethod
    def _merge_paper(unique_papers: dict[str, Paper], candidate: Paper) -> None:
        """_merge_paper 融合相同标题的多源结果（模糊去重）。"""
        title_key = _normalize_title(candidate.get_title())
        existing_paper = unique_papers.get(title_key)
        if existing_paper is None:
            unique_papers[title_key] = candidate
            return
        if SearchService._score_paper(candidate) > SearchService._score_paper(existing_paper):
            unique_papers[title_key] = candidate

    @staticmethod
    def _rank_papers(papers: List[Paper], queries: List[str] | None = None) -> List[Paper]:
        """_rank_papers 对检索结果排序（含关键词相关度加分）。"""
        query_keywords = _extract_query_keywords(queries or [])
        return sorted(
            papers,
            key=lambda p: SearchService._score_paper_with_relevance(p, query_keywords),
            reverse=True,
        )

    @staticmethod
    def _score_paper_with_relevance(paper: Paper, query_keywords: set[str]) -> tuple:
        """_score_paper_with_relevance 含查询相关度的排序分。"""
        base = SearchService._score_paper(paper)
        if not query_keywords:
            return base
        text = f"{paper.get_title()} {paper.get_summary()}".lower()
        overlap = sum(1 for kw in query_keywords if kw in text)
        return (overlap,) + base

    @staticmethod
    def _score_paper(paper: Paper) -> tuple:
        """_score_paper 计算论文质量分（源优先级 > 摘要长度 > 作者数 > 发表日期）。"""
        summary_length = len(paper.get_summary())
        author_count = len(paper.authors)
        source_priority = PAPER_SOURCE_PRIORITY.get(paper.source, 0)
        published = paper.published or ""
        return (source_priority, summary_length, author_count, published)


def _extract_query_keywords(queries: List[str]) -> set[str]:
    """_extract_query_keywords 从查询文本中提取关键词集合。"""
    keywords: set[str] = set()
    for query in queries:
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", query.lower()):
            keywords.add(token)
    return keywords


def _normalize_title(title: str) -> str:
    """_normalize_title 规范化标题用于模糊去重。

    策略: 移除标点、折叠空格、取前 8 个有效词。这样即使不同源的标题有
    大小写、标点、多余空格等差异，也能正确去重。
    """
    cleaned = re.sub(r"[^a-zA-Z0-9一-鿿]", " ", title.lower())
    tokens = [t for t in cleaned.split() if t]
    return " ".join(tokens[:8])
