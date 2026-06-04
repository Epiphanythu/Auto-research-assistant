"""test_search_service.py Tests for SearchService: multi-source merge, deduplication, ranking, and error handling."""

from __future__ import annotations

import pytest

from app.api_error import SearchAggregationError
from app.models.research_models import Paper, ResearchPlan, ResearchRequest
from app.services.core.search_service import SearchService

from tests.conftest import FakeSearchClient, FailingSearchClient


# ---------------------------------------------------------------------------
# Multi-source merge tests
# ---------------------------------------------------------------------------


class TestSearchMerge:
    """Tests for paper merging across multiple sources."""

    def test_merges_papers_from_multiple_sources(self):
        """Papers from different sources should be merged and deduplicated by title."""
        service = SearchService()
        service.openalex_client = FakeSearchClient(
            [
                Paper(
                    paper_id="openalex-1",
                    title="Paper A",
                    authors=["Alice", "Bob"],
                    summary="A much longer summary with evidence and more detail.",
                    published="2024-01-01",
                    pdf_url="https://example.com/openalex-a",
                    source="openalex",
                )
            ]
        )
        service.arxiv_client = FakeSearchClient(
            [
                Paper(
                    paper_id="arxiv-1",
                    title="Paper A",
                    authors=["Alice"],
                    summary="Short summary.",
                    published="2024-01-02",
                    pdf_url="https://example.com/arxiv-a",
                    source="arxiv",
                ),
                Paper(
                    paper_id="arxiv-2",
                    title="Paper B",
                    authors=["Carol"],
                    summary="Another valid summary for testing.",
                    published="2024-01-03",
                    pdf_url="https://example.com/arxiv-b",
                    source="arxiv",
                ),
            ]
        )
        service.s2_client = FakeSearchClient([])
        service.crossref_client = FakeSearchClient([])

        request = ResearchRequest(topic="test topic", max_papers=3)
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test topic"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )

        papers = service.search(request, plan)

        assert len(papers) == 2
        assert {p.title for p in papers} == {"Paper A", "Paper B"}

    def test_deduplicates_by_title_keeping_higher_quality(self):
        """When the same paper appears in multiple sources, keep the higher-quality version."""
        service = SearchService()
        service.openalex_client = FakeSearchClient(
            [
                Paper(
                    paper_id="openalex-1",
                    title="Same Title",
                    authors=["Alice", "Bob"],
                    summary="A much longer summary that provides more detail and evidence.",
                    published="2024-01-01",
                    pdf_url="https://example.com/a",
                    source="openalex",
                )
            ]
        )
        service.arxiv_client = FakeSearchClient(
            [
                Paper(
                    paper_id="arxiv-1",
                    title="Same Title",
                    authors=["Alice"],
                    summary="Short.",
                    published="2024-01-01",
                    pdf_url="https://example.com/b",
                    source="arxiv",
                )
            ]
        )
        service.s2_client = FakeSearchClient([])
        service.crossref_client = FakeSearchClient([])

        request = ResearchRequest(topic="test topic", max_papers=5)
        plan = ResearchPlan(
            normalized_topic="test topic",
            search_keywords=["test"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )

        papers = service.search(request, plan)
        assert len(papers) == 1
        # OpenAlex has higher source priority, and longer summary
        assert papers[0].source == "openalex"

    def test_respects_max_papers_limit(self):
        """Returned papers should not exceed the max_papers limit."""
        service = SearchService()
        many_papers = [
            Paper(
                paper_id=f"paper-{i}",
                title=f"Paper {i}",
                authors=["Author"],
                summary="Summary text for testing.",
                published="2024-01-01",
                source="arxiv",
            )
            for i in range(10)
        ]
        service.arxiv_client = FakeSearchClient(many_papers)
        service.openalex_client = FakeSearchClient([])
        service.s2_client = FakeSearchClient([])
        service.crossref_client = FakeSearchClient([])

        result = service.search_by_queries(queries=["test"], max_papers=3)
        assert len(result) <= 3


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestSearchErrors:
    """Tests for search error handling."""

    def test_returns_empty_when_all_sources_fail_with_runtime_error(self):
        """Should return empty list when all sources throw non-APIError exceptions."""
        service = SearchService()
        service.openalex_client = FailingSearchClient()
        service.arxiv_client = FailingSearchClient()
        service.s2_client = FailingSearchClient()
        service.crossref_client = FailingSearchClient()

        # RuntimeError is caught by the generic Exception handler, not added to query_errors,
        # so no SearchAggregationError is raised. Instead, empty results are returned.
        result = service.search_by_queries(queries=["test"], max_papers=2)
        assert result == []

    def test_raises_aggregation_error_when_all_sources_raise_api_error(self, monkeypatch):
        """Should raise SearchAggregationError when all sources raise APIError."""
        from app.api_error import SearchSourceUnavailableError

        service = SearchService()

        class APIErrorClient:
            def search_papers(self, query, max_results):
                raise SearchSourceUnavailableError("TestSource", "connection failed")

        service.openalex_client = APIErrorClient()
        service.arxiv_client = APIErrorClient()
        service.s2_client = APIErrorClient()
        service.crossref_client = APIErrorClient()

        with pytest.raises(SearchAggregationError) as exc_info:
            service.search_by_queries(queries=["test"], max_papers=2)

        assert exc_info.value.error_code == "search_aggregation_failed"

    def test_returns_partial_results_when_some_sources_fail(self):
        """Should return available results even if some sources fail."""
        service = SearchService()
        service.arxiv_client = FakeSearchClient(
            [
                Paper(
                    paper_id="arxiv-1",
                    title="Paper A",
                    authors=["Alice"],
                    summary="A valid summary for testing.",
                    published="2024-01-01",
                    source="arxiv",
                )
            ]
        )
        service.openalex_client = FailingSearchClient()
        service.s2_client = FailingSearchClient()
        service.crossref_client = FailingSearchClient()

        result = service.search_by_queries(queries=["test"], max_papers=5)
        assert len(result) == 1
        assert result[0].title == "Paper A"

    def test_handles_empty_queries_gracefully(self):
        """Should return empty list when all queries are empty strings."""
        service = SearchService()
        result = service.search_by_queries(queries=["", "  "], max_papers=5)
        assert result == []


# ---------------------------------------------------------------------------
# Ranking tests
# ---------------------------------------------------------------------------


class TestSearchRanking:
    """Tests for paper ranking logic."""

    def test_ranks_by_source_priority(self):
        """Papers from higher-priority sources should be ranked first."""
        papers = [
            Paper(
                paper_id="arxiv-1",
                title="Arxiv Paper",
                authors=["A"],
                summary="Test summary.",
                published="2024-01-01",
                source="arxiv",
            ),
            Paper(
                paper_id="s2-1",
                title="S2 Paper",
                authors=["B"],
                summary="Test summary.",
                published="2024-01-01",
                source="semantic_scholar",
            ),
        ]
        ranked = SearchService._rank_papers(papers)
        assert ranked[0].source == "semantic_scholar"

    def test_ranks_by_summary_length_when_source_equal(self):
        """Among same-source papers, longer summaries should rank higher."""
        papers = [
            Paper(
                paper_id="a",
                title="Short",
                authors=["A"],
                summary="Short.",
                published="2024-01-01",
                source="arxiv",
            ),
            Paper(
                paper_id="b",
                title="Long",
                authors=["A"],
                summary="A much longer summary with more detail and evidence.",
                published="2024-01-01",
                source="arxiv",
            ),
        ]
        ranked = SearchService._rank_papers(papers)
        assert ranked[0].paper_id == "b"
