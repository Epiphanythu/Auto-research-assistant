"""test_trend_analysis_service.py Tests for TrendAnalysisService: trend analysis, citation velocity, keyword extraction, and emerging topics."""

from __future__ import annotations

import pytest

from app.models.research_models import Paper, TopicTrendPoint
from app.services.analysis.trend_analysis_service import TrendAnalysisService
from app.services.core.llm_service import LLMService


def _mock_s2_search_results(year: int) -> list[dict]:
    """Build mock Semantic Scholar search results for a given year."""
    return [
        {
            "title": f"Paper on LLM repair {year}",
            "abstract": f"Abstract for paper {year}.",
            "year": year,
            "citationCount": 10 * (2026 - year),
            "fieldsOfStudy": ["Computer Science", "Artificial Intelligence"],
            "authors": [{"name": "Author A"}],
        },
        {
            "title": f"Agentic program repair {year}",
            "abstract": f"Abstract for agentic paper {year}.",
            "year": year,
            "citationCount": 5 * (2026 - year),
            "fieldsOfStudy": ["Computer Science"],
            "authors": [{"name": "Author B"}],
        },
    ]


class TestAnalyzeTrends:
    """Tests for TrendAnalysisService.analyze_trends."""

    def test_analyze_trends_returns_result(self, monkeypatch):
        """analyze_trends should return a TrendAnalysisResult with populated fields."""
        service = TrendAnalysisService()

        # Mock S2 search to return fake results per year
        monkeypatch.setattr(
            service.s2_client,
            "search_papers",
            lambda topic, max_results, year_range=None: _mock_s2_search_results(int(year_range) if year_range else 2024),
        )

        # Mock LLM
        monkeypatch.setattr(
            LLMService,
            "ask_json",
            lambda self, system_prompt, user_prompt, **kw: {
                "summary": "The field is growing rapidly.",
                "hot_directions": ["LLM-based repair", "Agent systems"],
                "cooling_directions": ["Rule-based repair"],
            },
        )

        result = service.analyze_trends("program repair", years=3)

        assert result.topic == "program repair"
        assert result.year_range == "2023-2026"
        assert len(result.yearly_paper_counts) > 0
        assert result.trend_summary == "The field is growing rapidly."
        assert len(result.hot_directions) == 2
        assert len(result.cooling_directions) == 1

    def test_analyze_trends_handles_search_failure(self, monkeypatch):
        """analyze_trends should gracefully handle search API failures."""
        service = TrendAnalysisService()

        def failing_search(topic, max_results, year_range=None):
            raise RuntimeError("API unavailable")

        monkeypatch.setattr(service.s2_client, "search_papers", failing_search)
        monkeypatch.setattr(
            LLMService,
            "ask_json",
            lambda self, system_prompt, user_prompt, **kw: {
                "summary": "Insufficient data.",
                "hot_directions": [],
                "cooling_directions": [],
            },
        )

        result = service.analyze_trends("test topic", years=2)
        assert result.topic == "test topic"
        assert len(result.yearly_paper_counts) == 0

    def test_analyze_trends_handles_llm_failure(self, monkeypatch):
        """analyze_trends should gracefully handle LLM failures."""
        service = TrendAnalysisService()

        monkeypatch.setattr(
            service.s2_client,
            "search_papers",
            lambda topic, max_results, year_range=None: _mock_s2_search_results(2024),
        )
        monkeypatch.setattr(
            LLMService,
            "ask_json",
            lambda self, system_prompt, user_prompt, **kw: (_ for _ in ()).throw(RuntimeError("LLM down")),
        )

        result = service.analyze_trends("test topic", years=1)
        assert result.trend_summary == ""
        assert result.hot_directions == []


class TestAnalyzePapersTrends:
    """Tests for TrendAnalysisService.analyze_papers_trends."""

    def test_analyzes_papers_by_year(self):
        """Should group papers by year and compute yearly counts."""
        service = TrendAnalysisService()
        papers = [
            Paper(paper_id="p1", title="Paper 1", authors=[], summary="S.", published="2023-01-01", source="arxiv"),
            Paper(paper_id="p2", title="Paper 2", authors=[], summary="S.", published="2023-06-01", source="arxiv"),
            Paper(paper_id="p3", title="Paper 3", authors=[], summary="S.", published="2024-01-01", source="arxiv"),
        ]

        result = service.analyze_papers_trends(papers)

        assert len(result.yearly_paper_counts) == 2
        year_2023 = next(p for p in result.yearly_paper_counts if p.year == 2023)
        year_2024 = next(p for p in result.yearly_paper_counts if p.year == 2024)
        assert year_2023.count == 2
        assert year_2024.count == 1

    def test_returns_empty_result_for_empty_list(self):
        """Should return a minimal result when no papers are provided."""
        service = TrendAnalysisService()
        result = service.analyze_papers_trends([])
        assert result.topic == ""
        assert result.year_range == "N/A"

    def test_handles_missing_published_dates(self):
        """Should skip papers with missing or invalid published dates."""
        service = TrendAnalysisService()
        papers = [
            Paper(paper_id="p1", title="Paper 1", authors=[], summary="S.", published="2024-01-01", source="arxiv"),
            Paper(paper_id="p2", title="Paper 2", authors=[], summary="S.", published="", source="arxiv"),
            Paper(paper_id="p3", title="Paper 3", authors=[], summary="S.", published="invalid", source="arxiv"),
        ]

        result = service.analyze_papers_trends(papers)
        # Only one paper has a valid year
        counts = result.yearly_paper_counts
        valid_counts = [p for p in counts if p.count > 0]
        assert len(valid_counts) == 1


class TestCitationVelocity:
    """Tests for citation velocity computation."""

    def test_computes_velocity_from_raw_results(self):
        """Should compute average citations per year for each year."""
        service = TrendAnalysisService()
        papers_by_year = {
            2024: [
                {"citationCount": 20},
                {"citationCount": 10},
            ],
            2023: [
                {"citationCount": 30},
            ],
        }

        velocity = service._compute_citation_velocity(papers_by_year)

        assert len(velocity) == 2
        # 2023: avg=30, age=3, per_year=10.0
        v_2023 = next(v for v in velocity if v.year == 2023)
        assert v_2023.avg_citations_per_year == 10.0
        assert v_2023.paper_count == 1

    def test_skips_years_with_no_citations(self):
        """Should skip years where no papers have citation counts."""
        service = TrendAnalysisService()
        papers_by_year = {
            2024: [{"title": "Paper"}],  # No citationCount field
        }

        velocity = service._compute_citation_velocity(papers_by_year)
        assert len(velocity) == 0


class TestEmergingTopics:
    """Tests for emerging topic identification."""

    def test_identifies_rapidly_growing_keywords(self):
        """Should identify keywords with >= 2x growth."""
        service = TrendAnalysisService()
        keyword_trends = {
            "agent": [
                TopicTrendPoint(year=2023, count=2, metric="agent"),
                TopicTrendPoint(year=2024, count=5, metric="agent"),
                TopicTrendPoint(year=2025, count=12, metric="agent"),
            ],
            "stable": [
                TopicTrendPoint(year=2023, count=5, metric="stable"),
                TopicTrendPoint(year=2025, count=6, metric="stable"),
            ],
        }

        emerging = service._identify_emerging_topics(keyword_trends)
        assert "agent" in emerging
        assert "stable" not in emerging

    def test_skips_keywords_with_fewer_than_2_data_points(self):
        """Should not flag keywords with only one data point."""
        service = TrendAnalysisService()
        keyword_trends = {
            "sparse": [TopicTrendPoint(year=2024, count=10, metric="sparse")],
        }

        emerging = service._identify_emerging_topics(keyword_trends)
        assert "sparse" not in emerging


class TestExtractYear:
    """Tests for _extract_year helper."""

    def test_extracts_year_from_date_string(self):
        """Should extract the year from a date string."""
        assert TrendAnalysisService._extract_year("2024-05-01") == 2024

    def test_extracts_year_from_year_only(self):
        """Should extract the year from a year-only string."""
        assert TrendAnalysisService._extract_year("2024") == 2024

    def test_returns_none_for_empty_string(self):
        """Should return None for empty strings."""
        assert TrendAnalysisService._extract_year("") is None

    def test_returns_none_for_invalid_string(self):
        """Should return None for non-year strings."""
        assert TrendAnalysisService._extract_year("invalid") is None
