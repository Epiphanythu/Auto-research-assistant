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
    PAPER_RELEVANCE_FALLBACK_KEEP_RATIO,
    PAPER_RELEVANCE_KEYWORD_STOPWORDS,
    PAPER_RELEVANCE_MIN_KEEP_SCORE,
    PAPER_RELEVANCE_PHRASE_WEIGHT,
    PAPER_RELEVANCE_SUMMARY_WEIGHT,
    PAPER_RELEVANCE_TITLE_WEIGHT,
    SEARCH_MAX_WORKERS,
)
from app.models.research_models import Paper, ResearchPlan, ResearchRequest
from app.services.infrastructure.search_cache import SearchCache, get_search_cache

logger = logging.getLogger(__name__)

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

        papers = self._annotate_relevance(list(unique_papers.values()), normalized_queries, topic)
        papers = self._rank_papers(papers, normalized_queries, topic)
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
        """_filter_by_relevance 过滤与主题明显不相关的论文，并保留必要兜底数量。"""
        if not papers:
            return papers
        if len(papers) <= max_papers:
            return papers[:max_papers]

        # 1. 优先保留超过阈值的论文，从源头减少低相关论文进入抽取和报告。
        filtered = [
            paper for paper in papers
            if paper.get_relevance_score() >= PAPER_RELEVANCE_MIN_KEEP_SCORE
        ]

        # 2. 若主题很窄导致候选过少，保留少量最高分兜底，避免无报告可生成。
        min_keep = max(1, min(max_papers, int(max_papers * PAPER_RELEVANCE_FALLBACK_KEEP_RATIO)))
        if len(filtered) < min_keep:
            seen_ids = {id(paper) for paper in filtered}
            for paper in papers:
                if id(paper) not in seen_ids:
                    filtered.append(paper)
                    seen_ids.add(id(paper))
                if len(filtered) >= min_keep:
                    break

        logger.info(
            "SearchService._filter_by_relevance: %d papers, threshold=%.2f, kept=%d, max_papers=%d",
            len(papers), PAPER_RELEVANCE_MIN_KEEP_SCORE, len(filtered), max_papers,
        )
        return filtered[:max_papers]

    @staticmethod
    def _annotate_relevance(papers: List[Paper], queries: List[str], topic: str) -> List[Paper]:
        """_annotate_relevance 为候选论文写入主题相关性分数与可解释原因。"""
        query_keywords = _extract_query_keywords(queries, topic)
        query_phrases = _extract_query_phrases(queries, topic)
        if not query_keywords and not query_phrases:
            return papers

        for paper in papers:
            score, reason = SearchService._compute_relevance_score(
                paper, query_keywords, query_phrases,
            )
            paper.topic_relevance_score = score
            paper.relevance_reason = reason
        return papers

    @staticmethod
    def _compute_relevance_score(
        paper: Paper,
        query_keywords: set[str],
        query_phrases: list[str],
    ) -> tuple[float, str]:
        """_compute_relevance_score 计算论文与主题的相关性分数和命中依据。"""
        title_text = paper.get_title().lower()
        summary_text = paper.get_summary().lower()
        combined_text = f"{title_text} {summary_text}"
        keyword_count = max(1, len(query_keywords))

        # 1. 分别计算标题、摘要和完整查询短语命中，标题命中权重最高。
        title_hits = sorted(keyword for keyword in query_keywords if keyword in title_text)
        summary_hits = sorted(keyword for keyword in query_keywords if keyword in summary_text)
        phrase_hits = sorted(phrase for phrase in query_phrases if phrase in combined_text)
        title_score = len(title_hits) / keyword_count
        summary_score = len(summary_hits) / keyword_count
        phrase_score = len(phrase_hits) / max(1, len(query_phrases))
        score = (
            PAPER_RELEVANCE_TITLE_WEIGHT * title_score
            + PAPER_RELEVANCE_SUMMARY_WEIGHT * summary_score
            + PAPER_RELEVANCE_PHRASE_WEIGHT * phrase_score
        )

        # 2. 生成前端可展示的简短原因，便于用户理解为什么保留这篇论文。
        reason_parts: list[str] = []
        if phrase_hits:
            reason_parts.append(f"命中主题短语：{', '.join(phrase_hits[:2])}")
        if title_hits:
            reason_parts.append(f"标题命中：{', '.join(title_hits[:4])}")
        if summary_hits:
            reason_parts.append(f"摘要命中：{', '.join(summary_hits[:4])}")
        reason = "；".join(reason_parts) if reason_parts else "未命中核心主题词，仅作为候选兜底"
        return round(min(1.0, score), 4), reason

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
        relevance_int = int(round(paper.get_relevance_score() * 10000))
        return (relevance_int, authority_int) + base

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
        if token not in PAPER_RELEVANCE_KEYWORD_STOPWORDS:
            keywords.add(token)

    for char in re.findall(r"[一-鿿]", all_text):
        keywords.add(char)

    # 提取中文 bigram（相邻两字组合），提高中文相关度匹配粒度
    cn_chars = re.findall(r"[一-鿿]+", all_text)
    for segment in cn_chars:
        for i in range(len(segment) - 1):
            keywords.add(segment[i : i + 2])

    return keywords


def _extract_query_phrases(queries: List[str], topic: str = "") -> list[str]:
    """_extract_query_phrases 提取可用于精确匹配的主题短语。"""
    phrases: list[str] = []
    for raw in [topic, *queries]:
        phrase = re.sub(r"\s+", " ", raw.strip().lower())
        if len(phrase) < 4:
            continue
        # 1. 过滤只由停用词组成的泛短语，保留真正能约束主题的组合表达。
        tokens = [
            token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", phrase)
            if token not in PAPER_RELEVANCE_KEYWORD_STOPWORDS
        ]
        cn_chars = re.findall(r"[一-鿿]+", phrase)
        if len(tokens) >= 2 or cn_chars:
            phrases.append(phrase)
    return list(dict.fromkeys(phrases))


def _normalize_title(title: str) -> str:
    """_normalize_title 规范化标题用于模糊去重。

    策略: 移除标点、折叠空格、取前 8 个有效词。这样即使不同源的标题有
    大小写、标点、多余空格等差异，也能正确去重。
    """
    cleaned = re.sub(r"[^a-zA-Z0-9一-鿿]", " ", title.lower())
    tokens = [t for t in cleaned.split() if t]
    return " ".join(tokens[:8])
