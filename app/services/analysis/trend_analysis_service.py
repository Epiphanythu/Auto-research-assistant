"""trend_analysis_service 研究趋势分析服务。"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from app.clients.semantic_scholar_client import SemanticScholarClient
from app.models.research_models import (
    TopicTrendPoint,
    CitationVelocity,
    TrendAnalysisResult,
)
from app.services.core.llm_service import LLMService

logger = logging.getLogger(__name__)


class TrendAnalysisService:
    """TrendAnalysisService 研究趋势分析引擎。"""

    def __init__(self) -> None:
        self.s2_client = SemanticScholarClient()
        self.llm = LLMService()

    def analyze_trends(self, topic: str, years: int = 5) -> TrendAnalysisResult:
        """analyze_trends 分析研究主题的趋势。"""
        current_year = 2026
        from_year = current_year - years

        # 1. 获取近年论文数据
        papers_by_year: Dict[int, List[Dict]] = defaultdict(list)
        for year in range(from_year, current_year + 1):
            try:
                results = self.s2_client.search_papers(
                    topic, max_results=50, year_range=str(year),
                )
                papers_by_year[year] = results
            except Exception as error:
                logger.warning("TrendAnalysis: search failed for year %s: %s", year, error)

        # 2. 计算引用速度（citation velocity）
        velocity = self._compute_citation_velocity(papers_by_year)

        # 3. 计算年度论文数量趋势
        yearly_counts = [
            TopicTrendPoint(year=year, count=len(papers), metric="paper_count")
            for year, papers in sorted(papers_by_year.items())
        ]

        # 4. 提取热门关键词趋势
        keyword_trends = self._extract_keyword_trends(papers_by_year)

        # 5. LLM 分析趋势方向
        trend_analysis = self._llm_analyze_trends(topic, papers_by_year)

        # 6. 识别新兴话题
        emerging_topics = self._identify_emerging_topics(keyword_trends)

        return TrendAnalysisResult(
            topic=topic,
            year_range=f"{from_year}-{current_year}",
            yearly_paper_counts=yearly_counts,
            citation_velocity=velocity,
            keyword_trends=keyword_trends,
            emerging_topics=emerging_topics,
            trend_summary=trend_analysis.get("summary", ""),
            hot_directions=trend_analysis.get("hot_directions", []),
            cooling_directions=trend_analysis.get("cooling_directions", []),
        )

    def analyze_papers_trends(self, papers: List[Any]) -> TrendAnalysisResult:
        """analyze_papers_trends 从已有论文列表分析趋势。"""
        if not papers:
            return TrendAnalysisResult(topic="", year_range="N/A")

        # 按年份分组
        by_year: Dict[int, List] = defaultdict(list)
        for paper in papers:
            year = self._extract_year(paper.published)
            if year:
                by_year[year].append(paper)

        yearly_counts = [
            TopicTrendPoint(year=year, count=len(papers), metric="paper_count")
            for year, papers in sorted(by_year.items())
        ]

        velocity = self._compute_citation_velocity_from_papers(by_year)

        return TrendAnalysisResult(
            topic=papers[0].title if papers else "",
            year_range=f"{min(by_year.keys())}-{max(by_year.keys())}" if by_year else "N/A",
            yearly_paper_counts=yearly_counts,
            citation_velocity=velocity,
        )

    def _compute_citation_velocity(
        self, papers_by_year: Dict[int, List[Dict]]
    ) -> List[CitationVelocity]:
        """_compute_citation_velocity 计算每年论文的平均引用速度。"""
        velocity: List[CitationVelocity] = []
        current_year = 2026

        for year in sorted(papers_by_year.keys()):
            papers = papers_by_year[year]
            if not papers:
                continue
            citation_counts = [p.get("citationCount", 0) for p in papers if p.get("citationCount")]
            if not citation_counts:
                continue
            age = max(current_year - year, 1)
            avg_citations = sum(citation_counts) / len(citation_counts)
            velocity.append(CitationVelocity(
                year=year,
                avg_citations_per_year=round(avg_citations / age, 1),
                total_citations=sum(citation_counts),
                paper_count=len(papers),
            ))
        return velocity

    def _compute_citation_velocity_from_papers(
        self, by_year: Dict[int, List]
    ) -> List[CitationVelocity]:
        """_compute_citation_velocity_from_papers 从 Paper 模型列表计算引用速度。"""
        velocity: List[CitationVelocity] = []
        current_year = 2026

        for year in sorted(by_year.keys()):
            papers = by_year[year]
            age = max(current_year - year, 1)
            velocity.append(CitationVelocity(
                year=year,
                avg_citations_per_year=0,
                total_citations=0,
                paper_count=len(papers),
            ))
        return velocity

    def _extract_keyword_trends(
        self, papers_by_year: Dict[int, List[Dict]]
    ) -> Dict[str, List[TopicTrendPoint]]:
        """_extract_keyword_trends 提取关键词出现频率的年度变化。"""
        yearly_keywords: Dict[int, Counter] = {}
        for year, papers in papers_by_year.items():
            counter: Counter = Counter()
            for paper in papers:
                fields = paper.get("fieldsOfStudy") or []
                for field in fields:
                    counter[field] += 1
                # 从标题中提取关键词
                title = (paper.get("title") or "").lower()
                words = [w for w in title.split() if len(w) > 4]
                counter.update(words)
            yearly_keywords[year] = counter

        # 收集出现频率最高的关键词
        total_counter: Counter = Counter()
        for counter in yearly_keywords.values():
            total_counter.update(counter)

        keyword_trends: Dict[str, List[TopicTrendPoint]] = {}
        for keyword, _ in total_counter.most_common(20):
            trends = []
            for year in sorted(yearly_keywords.keys()):
                count = yearly_keywords[year].get(keyword, 0)
                if count > 0:
                    trends.append(TopicTrendPoint(year=year, count=count, metric=keyword))
            if len(trends) >= 2:
                keyword_trends[keyword] = trends

        return keyword_trends

    def _llm_analyze_trends(
        self, topic: str, papers_by_year: Dict[int, List[Dict]]
    ) -> Dict[str, Any]:
        """_llm_analyze_trends 用 LLM 分析研究方向冷热。"""
        year_summary = []
        for year in sorted(papers_by_year.keys()):
            count = len(papers_by_year[year])
            top_titles = [p.get("title", "") for p in papers_by_year[year][:5] if p.get("title")]
            year_summary.append(f"{year}: {count} papers, top: {'; '.join(top_titles)}")

        context = "\n".join(year_summary)
        if not context.strip():
            return {}

        try:
            return self.llm.ask_json(
                system_prompt=(
                    "You are a research trend analyst. Analyze the following yearly paper data "
                    "for a research topic and return a JSON object with: "
                    "1. 'summary': a 2-3 sentence overview of the trend "
                    "2. 'hot_directions': list of 3-5 currently hot research directions "
                    "3. 'cooling_directions': list of 2-3 directions that seem to be losing momentum"
                ),
                user_prompt=f"Topic: {topic}\n\nYearly data:\n{context}",
            )
        except Exception as error:
            logger.warning("TrendAnalysis LLM failed: %s", error)
            return {}

    def _identify_emerging_topics(
        self, keyword_trends: Dict[str, List[TopicTrendPoint]]
    ) -> List[str]:
        """_identify_emerging_topics 识别出现频率快速增长的关键词。"""
        emerging: List[str] = []
        for keyword, points in keyword_trends.items():
            if len(points) < 2:
                continue
            sorted_points = sorted(points, key=lambda p: p.year)
            recent_count = sorted_points[-1].count
            early_count = sorted_points[0].count
            if early_count > 0 and recent_count / early_count >= 2.0:
                emerging.append(keyword)
        return emerging[:10]

    @staticmethod
    def _extract_year(date_str: str) -> Optional[int]:
        """_extract_year 从日期字符串提取年份。"""
        if not date_str:
            return None
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return None
