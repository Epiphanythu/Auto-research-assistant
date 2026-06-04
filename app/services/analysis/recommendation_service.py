"""recommendation_service 论文推荐引擎。"""

from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Any, Dict, List, Optional

from app.clients.semantic_scholar_client import SemanticScholarClient
from app.models.research_models import Paper, PaperRecommendation
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)


class RecommendationService:
    """RecommendationService 论文推荐与相似度计算引擎。"""

    def __init__(self) -> None:
        self.s2_client = SemanticScholarClient()
        self.llm = LLMService()

    def recommend_from_paper(self, paper_id: str, limit: int = 10) -> List[PaperRecommendation]:
        """recommend_from_paper 基于单篇论文推荐相似论文。"""
        raw = self.s2_client.get_paper_recommendations(paper_id, limit=limit)
        return [self._map_recommendation(item) for item in raw if item.get("paperId")]

    def recommend_for_topic(
        self,
        topic: str,
        existing_papers: List[Paper],
        limit: int = 10,
    ) -> List[PaperRecommendation]:
        """recommend_for_topic 基于研究主题和已有论文推荐新论文。"""
        # 1. 用 Semantic Scholar 搜索相关论文
        try:
            search_results = self.s2_client.search_papers(topic, max_results=20)
        except Exception as error:
            logger.warning("Recommendation search failed: %s", error)
            return []

        # 2. 过滤掉已有的论文
        existing_titles = {p.title.strip().lower() for p in existing_papers}

        candidates: List[PaperRecommendation] = []
        for item in search_results:
            title = (item.get("title") or "").strip()
            if not title or title.lower() in existing_titles:
                continue
            candidates.append(self._map_recommendation(item))

        # 3. 如果有已有论文，计算与已有论文的相似度来排序
        if existing_papers:
            existing_text = " ".join(p.summary for p in existing_papers if p.summary)
            candidates = self._rank_by_similarity(candidates, existing_text)

        return candidates[:limit]

    def recommend_diverse_papers(
        self,
        papers: List[Paper],
        limit: int = 10,
    ) -> List[PaperRecommendation]:
        """recommend_diverse_papers 推荐能拓宽研究视野的论文（与已有论文互补）。"""
        if not papers:
            return []

        # 收集已有论文的主题关键词
        existing_keywords = self._extract_keywords(papers)

        # 用每个已有论文搜索相似论文，然后推荐与现有关键词不重叠的方向
        all_candidates: Dict[str, PaperRecommendation] = {}
        seen_titles = {p.title.strip().lower() for p in papers}

        for paper in papers[:5]:
            paper_id = paper.paper_id
            if not paper_id:
                continue
            try:
                recs = self.recommend_from_paper(paper_id, limit=5)
                for rec in recs:
                    title_key = rec.title.strip().lower()
                    if title_key not in seen_titles and title_key not in all_candidates:
                        all_candidates[title_key] = rec
            except Exception as error:
                logger.warning("Diverse recommendation failed for %s: %s", paper_id, error)
                continue

        # 排序：推荐关键词重叠度最低的（最不相似的 = 最互补的）
        candidates = list(all_candidates.values())
        existing_kw_set = set(existing_keywords)
        candidates.sort(
            key=lambda c: -len(set(c.reason.split()) & existing_kw_set) if c.reason else 0,
        )

        return candidates[:limit]

    def _rank_by_similarity(
        self,
        candidates: List[PaperRecommendation],
        reference_text: str,
    ) -> List[PaperRecommendation]:
        """_rank_by_similarity 用简易 TF-IDF 计算与参考文本的相似度来排序。"""
        if not reference_text:
            return candidates

        ref_words = Counter(reference_text.lower().split())

        scored: List[tuple] = []
        for candidate in candidates:
            cand_text = (candidate.title + " " + candidate.abstract).lower()
            cand_words = Counter(cand_text.split())
            sim = self._cosine_similarity(ref_words, cand_words)
            scored.append((sim, candidate))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]

    @staticmethod
    def _cosine_similarity(vec_a: Counter, vec_b: Counter) -> float:
        """_cosine_similarity 计算两个词频向量的余弦相似度。"""
        all_keys = set(vec_a.keys()) | set(vec_b.keys())
        if not all_keys:
            return 0.0
        dot = sum(vec_a[k] * vec_b[k] for k in all_keys)
        norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _extract_keywords(papers: List[Paper]) -> List[str]:
        """_extract_keywords 从论文列表中提取高频关键词。"""
        counter: Counter = Counter()
        for paper in papers:
            text = (paper.title + " " + paper.summary).lower()
            words = [w for w in text.split() if len(w) > 4]
            counter.update(words)
        return [w for w, _ in counter.most_common(30)]

    @staticmethod
    def _map_recommendation(item: Dict[str, Any]) -> PaperRecommendation:
        """_map_recommendation 将 Semantic Scholar 结果映射为推荐模型。"""
        authors = [a.get("name", "").strip() for a in (item.get("authors") or []) if a.get("name")]
        tldr = ""
        tldr_obj = item.get("tldr")
        if isinstance(tldr_obj, dict):
            tldr = tldr_obj.get("text", "")
        oa_pdf = item.get("openAccessPdf") or {}
        pdf_url = oa_pdf.get("url", "") if isinstance(oa_pdf, dict) else ""
        ext_ids = item.get("externalIds") or {}
        paper_id = ext_ids.get("ArXiv") or ext_ids.get("DOI") or item.get("paperId", "")
        return PaperRecommendation(
            paper_id=paper_id,
            title=item.get("title", ""),
            authors=authors,
            abstract=item.get("abstract", ""),
            tldr=tldr,
            year=item.get("year"),
            citation_count=item.get("citationCount", 0),
            pdf_url=pdf_url,
            reason=f"基于引用网络和语义相似性推荐。引用数: {item.get('citationCount', 0)}",
        )
