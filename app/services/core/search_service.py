"""search_service 论文检索服务（并行多源）。"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

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
    PAGERANK_LITE_DAMPING,
    PAGERANK_LITE_LOG_BASE,
    PAGERANK_LITE_WEIGHT,
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
            topic=request.topic,
        )

    def search_by_queries(
        self,
        queries: List[str],
        max_papers: int,
        topic: str = "",
    ) -> List[Paper]:
        """search_by_queries 根据查询数组执行并行多源检索。"""
        normalized_queries = [query for query in queries if query.strip()]
        logger.info(
            "SearchService.search_by_queries start, queries=%s, max_papers=%s, topic=%s",
            normalized_queries,
            max_papers,
            topic[:40],
        )
        unique_papers: dict[str, Paper] = {}
        query_errors: list[APIError] = []

        per_query_limit = min(max_papers, DEFAULT_SOURCE_SEARCH_LIMIT)

        # 并行执行所有关键词 x 所有源的检索
        with ThreadPoolExecutor(max_workers=SEARCH_MAX_WORKERS) as executor:
            futures = {}
            for query in normalized_queries:
                for source_name, client in [
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

        papers = self._rank_papers(list(unique_papers.values()), normalized_queries, topic)
        papers = self._filter_by_relevance(papers, normalized_queries, topic, max_papers)
        logger.info(
            "SearchService.search_by_queries completed, unique=%d, returned=%d",
            len(unique_papers), len(papers),
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
    def _rank_papers(papers: List[Paper], queries: List[str] | None = None, topic: str = "") -> List[Paper]:
        """_rank_papers 对检索结果排序。

        排序键由三部分组成：
        1. 关键词重叠数（最高优先级，由 _score_paper_with_relevance 计算）
        2. PageRank-lite 权威度分量（基于 citation_count 对数归一化）
        3. 基础分（source_priority / summary_length / author_count / published）
        """
        query_keywords = _extract_query_keywords(queries or [], topic)
        # 1. 预先计算 PageRank-lite 分量，按 paper_id 索引
        authority_scores = SearchService._compute_pagerank_lite_scores(papers)
        return sorted(
            papers,
            key=lambda p: SearchService._score_paper_with_relevance(
                p, query_keywords, authority_scores.get(p.paper_id, 0.0),
            ),
            reverse=True,
        )

    @staticmethod
    def _compute_pagerank_lite_scores(papers: List[Paper]) -> Dict[str, float]:
        """_compute_pagerank_lite_scores 基于 citation_count 计算轻量权威度分量。

        策略：
        1. 取每篇论文 citation_count，做 log(1+x) 缩放抑制极端值
        2. 在候选集内做 min-max 归一化到 [0, 1]
        3. 乘以阻尼系数（避免与基础分量纲过大），即近似 PageRank 一次迭代后的稳态值
        """
        if not papers:
            return {}
        log_scores = [
            math.log(1 + max(0, paper.citation_count), PAGERANK_LITE_LOG_BASE)
            for paper in papers
        ]
        max_log = max(log_scores)
        min_log = min(log_scores)
        span = max_log - min_log
        scores: Dict[str, float] = {}
        for paper, log_score in zip(papers, log_scores):
            normalized = (log_score - min_log) / span if span > 0 else 0.0
            scores[paper.paper_id] = round(normalized * PAGERANK_LITE_DAMPING, 4)
        return scores

    @staticmethod
    def _filter_by_relevance(
        papers: List[Paper],
        queries: List[str],
        topic: str,
        max_papers: int,
    ) -> List[Paper]:
        """过滤掉与主题明显不相关的论文。"""
        if not papers or len(papers) <= max_papers:
            return papers

        query_keywords = _extract_query_keywords(queries, topic)
        if not query_keywords:
            return papers

        scored = []
        for paper in papers:
            text = f"{paper.get_title()} {paper.get_summary()}".lower()
            overlap = sum(1 for kw in query_keywords if kw in text)
            scored.append((overlap, paper))

        max_overlap = max(s for s, _ in scored) if scored else 0
        if max_overlap == 0:
            return papers

        threshold = max(1, max_overlap // 3)
        filtered = [p for score, p in scored if score >= threshold]

        if len(filtered) < max_papers:
            remaining = [p for score, p in scored if score < threshold]
            filtered.extend(remaining[: max_papers - len(filtered)])

        logger.info(
            "SearchService._filter_by_relevance: %d papers, max_overlap=%d, threshold=%d, kept=%d",
            len(papers), max_overlap, threshold, len(filtered),
        )
        return filtered

    @staticmethod
    def _score_paper_with_relevance(
        paper: Paper,
        query_keywords: set[str],
        authority_score: float = 0.0,
    ) -> tuple:
        """_score_paper_with_relevance 含查询相关度与 PageRank-lite 权威度的排序键。

        返回顺序：
        1. 关键词重叠数（无关键词时退化为基础分）
        2. PageRank-lite 加权后的权威度（量化为整数避免浮点抖动）
        3. 基础分（source_priority / summary_length / author_count / published）
        """
        base = SearchService._score_paper(paper)
        # 1. 把权威度量化到整数刻度（0~1000），便于在 tuple 中稳定比较
        authority_int = int(round(authority_score * PAGERANK_LITE_WEIGHT * 1000))
        if not query_keywords:
            return (authority_int,) + base
        text = f"{paper.get_title()} {paper.get_summary()}".lower()
        overlap = sum(1 for kw in query_keywords if kw in text)
        return (overlap, authority_int) + base

    @staticmethod
    def _score_paper(paper: Paper) -> tuple:
        """_score_paper 计算论文质量分（源优先级 > 摘要长度 > 作者数 > 发表日期）。"""
        summary_length = len(paper.get_summary())
        author_count = len(paper.authors)
        source_priority = PAPER_SOURCE_PRIORITY.get(paper.source, 0)
        published = paper.published or ""
        return (source_priority, summary_length, author_count, published)


def _extract_query_keywords(queries: List[str], topic: str = "") -> set[str]:
    """_extract_query_keywords 从查询文本和主题中提取关键词集合。"""
    keywords: set[str] = set()
    all_text = " ".join(queries)
    if topic:
        all_text += " " + topic

    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", all_text.lower()):
        keywords.add(token)

    for char in re.findall(r"[一-鿿]", all_text):
        keywords.add(char)

    # 提取中文 bigram（相邻两字组合），提高中文相关度匹配粒度
    cn_chars = re.findall(r"[一-鿿]+", all_text)
    for segment in cn_chars:
        for i in range(len(segment) - 1):
            keywords.add(segment[i : i + 2])

    return keywords


def _normalize_title(title: str) -> str:
    """_normalize_title 规范化标题用于模糊去重。

    策略: 移除标点、折叠空格、取前 8 个有效词。这样即使不同源的标题有
    大小写、标点、多余空格等差异，也能正确去重。
    """
    cleaned = re.sub(r"[^a-zA-Z0-9一-鿿]", " ", title.lower())
    tokens = [t for t in cleaned.split() if t]
    return " ".join(tokens[:8])
