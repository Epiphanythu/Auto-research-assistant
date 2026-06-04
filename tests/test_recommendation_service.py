"""test_recommendation_service.py Tests for RecommendationService: TF-IDF similarity, topic recommendations, cosine similarity, and keyword extraction."""

from __future__ import annotations

from collections import Counter

import pytest

from app.models.research_models import Paper, PaperRecommendation
from app.services.analysis.recommendation_service import RecommendationService
from app.services.core.llm_service import LLMService


class TestCosineSimilarity:
    """Tests for RecommendationService._cosine_similarity."""

    def test_identical_vectors_return_one(self):
        """Identical word frequency vectors should have cosine similarity of 1.0."""
        vec_a = Counter(["hello", "world", "hello"])
        vec_b = Counter(["hello", "world", "hello"])
        sim = RecommendationService._cosine_similarity(vec_a, vec_b)
        assert sim == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        """Completely different word frequency vectors should have similarity near 0.0."""
        vec_a = Counter(["hello", "world"])
        vec_b = Counter(["foo", "bar"])
        sim = RecommendationService._cosine_similarity(vec_a, vec_b)
        assert sim == pytest.approx(0.0)

    def test_partial_overlap(self):
        """Partially overlapping vectors should have similarity between 0 and 1."""
        vec_a = Counter(["hello", "world", "test"])
        vec_b = Counter(["hello", "world", "other"])
        sim = RecommendationService._cosine_similarity(vec_a, vec_b)
        assert 0.0 < sim < 1.0

    def test_empty_vectors_return_zero(self):
        """Empty word frequency vectors should return 0.0."""
        sim = RecommendationService._cosine_similarity(Counter(), Counter())
        assert sim == 0.0

    def test_one_empty_vector_returns_zero(self):
        """One empty and one non-empty vector should return 0.0."""
        sim = RecommendationService._cosine_similarity(Counter(["hello"]), Counter())
        assert sim == 0.0


class TestRankBySimilarity:
    """Tests for RecommendationService._rank_by_similarity."""

    def test_ranks_by_cosine_similarity(self):
        """Candidates more similar to reference text should rank higher."""
        service = RecommendationService()
        reference_text = "retrieval augmented generation language model"
        candidates = [
            PaperRecommendation(
                paper_id="p1",
                title="Retrieval-Augmented Generation with Language Models",
                abstract="This paper studies retrieval-augmented generation for language models.",
            ),
            PaperRecommendation(
                paper_id="p2",
                title="Cooking with Fire",
                abstract="A paper about culinary techniques.",
            ),
        ]

        ranked = service._rank_by_similarity(candidates, reference_text)
        assert ranked[0].paper_id == "p1"

    def test_returns_original_order_for_empty_reference(self):
        """With empty reference text, should return candidates in original order."""
        service = RecommendationService()
        candidates = [
            PaperRecommendation(paper_id="p1", title="A", abstract="A"),
            PaperRecommendation(paper_id="p2", title="B", abstract="B"),
        ]

        ranked = service._rank_by_similarity(candidates, "")
        assert ranked[0].paper_id == "p1"


class TestExtractKeywords:
    """Tests for RecommendationService._extract_keywords."""

    def test_extracts_frequent_long_words(self):
        """Should extract the most frequent words longer than 4 characters."""
        service = RecommendationService()
        papers = [
            Paper(
                paper_id="p1",
                title="Retrieval-Augmented Generation for Repair",
                authors=[],
                summary="Retrieval-augmented generation improves program repair quality significantly.",
                source="arxiv",
            ),
        ]

        keywords = service._extract_keywords(papers)
        assert len(keywords) > 0
        # Should contain words from title and summary
        assert any("retrieval" in kw for kw in keywords)

    def test_returns_empty_for_empty_paper_list(self):
        """Should return empty list when no papers are provided."""
        keywords = RecommendationService._extract_keywords([])
        assert keywords == []


class TestRecommendForTopic:
    """Tests for RecommendationService.recommend_for_topic."""

    def test_returns_recommendations_from_search(self, monkeypatch):
        """Should return recommendations based on search results, filtered and ranked."""
        service = RecommendationService()

        mock_search_results = [
            {
                "title": "New Paper on Program Repair",
                "abstract": "Abstract for new paper.",
                "paperId": "new-001",
                "externalIds": {"ArXiv": "new-001"},
                "authors": [{"name": "Alice"}],
                "citationCount": 10,
                "year": 2024,
                "openAccessPdf": {"url": "https://example.com/new.pdf"},
                "tldr": {"text": "TLDR of new paper."},
            },
        ]

        monkeypatch.setattr(service.s2_client, "search_papers", lambda topic, max_results: mock_search_results)
        monkeypatch.setattr(LLMService, "ensure_enabled", lambda self: None)

        result = service.recommend_for_topic("program repair", existing_papers=[], limit=5)
        assert len(result) == 1
        assert result[0].title == "New Paper on Program Repair"

    def test_filters_existing_papers(self, monkeypatch):
        """Should exclude papers that already exist in the provided list."""
        service = RecommendationService()

        existing = [
            Paper(
                paper_id="existing-1",
                title="Existing Paper",
                authors=["Alice"],
                summary="Summary.",
                source="arxiv",
            ),
        ]

        mock_search_results = [
            {
                "title": "Existing Paper",
                "abstract": "Abstract.",
                "paperId": "existing-1",
                "externalIds": {},
                "authors": [{"name": "Alice"}],
                "citationCount": 5,
                "openAccessPdf": {},
            },
            {
                "title": "Brand New Paper",
                "abstract": "New abstract.",
                "paperId": "new-1",
                "externalIds": {"DOI": "new-1"},
                "authors": [{"name": "Bob"}],
                "citationCount": 3,
                "openAccessPdf": {},
            },
        ]

        monkeypatch.setattr(service.s2_client, "search_papers", lambda topic, max_results: mock_search_results)
        monkeypatch.setattr(LLMService, "ensure_enabled", lambda self: None)

        result = service.recommend_for_topic("test", existing_papers=existing, limit=5)
        assert len(result) == 1
        assert result[0].title == "Brand New Paper"

    def test_returns_empty_on_search_failure(self, monkeypatch):
        """Should return empty list when search fails."""
        service = RecommendationService()

        monkeypatch.setattr(
            service.s2_client,
            "search_papers",
            lambda topic, max_results: (_ for _ in ()).throw(RuntimeError("API down")),
        )
        monkeypatch.setattr(LLMService, "ensure_enabled", lambda self: None)

        result = service.recommend_for_topic("test", existing_papers=[])
        assert result == []


class TestRecommendFromPaper:
    """Tests for RecommendationService.recommend_from_paper."""

    def test_returns_mapped_recommendations(self, monkeypatch):
        """Should map S2 recommendations to PaperRecommendation objects."""
        service = RecommendationService()

        mock_recs = [
            {
                "paperId": "rec-001",
                "title": "Recommended Paper",
                "abstract": "Abstract.",
                "externalIds": {"ArXiv": "rec-001"},
                "authors": [{"name": "Alice"}],
                "citationCount": 20,
                "year": 2024,
                "openAccessPdf": {"url": "https://example.com/rec.pdf"},
            },
        ]

        monkeypatch.setattr(
            service.s2_client,
            "get_paper_recommendations",
            lambda paper_id, limit: mock_recs,
        )

        result = service.recommend_from_paper("source-001")
        assert len(result) == 1
        assert result[0].paper_id == "rec-001"
        assert result[0].citation_count == 20

    def test_filters_papers_without_id(self, monkeypatch):
        """Should skip recommendations that have no paperId."""
        service = RecommendationService()

        mock_recs = [
            {"paperId": "", "title": "No ID"},
            {"paperId": "valid-001", "title": "Valid"},
        ]

        monkeypatch.setattr(
            service.s2_client,
            "get_paper_recommendations",
            lambda paper_id, limit: mock_recs,
        )

        result = service.recommend_from_paper("source-001")
        assert len(result) == 1
        assert result[0].paper_id == "valid-001"


class TestRecommendDiversePapers:
    """Tests for RecommendationService.recommend_diverse_papers."""

    def test_returns_empty_for_empty_input(self):
        """Should return empty list when no papers are provided."""
        service = RecommendationService()
        result = service.recommend_diverse_papers([])
        assert result == []

    def test_returns_diverse_recommendations(self, monkeypatch):
        """Should return diverse (complementary) paper recommendations."""
        service = RecommendationService()

        papers = [
            Paper(
                paper_id="src-1",
                title="Source Paper",
                authors=["Alice"],
                summary="Retrieval augmented generation for program repair.",
                source="arxiv",
            ),
        ]

        mock_recs = [
            {
                "paperId": "div-1",
                "title": "Diverse Paper on Testing",
                "abstract": "Software testing methodology.",
                "externalIds": {"DOI": "div-1"},
                "authors": [{"name": "Bob"}],
                "citationCount": 5,
                "openAccessPdf": {},
            },
        ]

        monkeypatch.setattr(
            service.s2_client,
            "get_paper_recommendations",
            lambda paper_id, limit: mock_recs,
        )

        result = service.recommend_diverse_papers(papers, limit=5)
        assert len(result) >= 1
