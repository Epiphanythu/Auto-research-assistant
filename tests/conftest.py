"""conftest.py Shared pytest fixtures and configuration for the test suite."""

from __future__ import annotations

import pytest

from app.services.infrastructure.search_cache import get_search_cache


@pytest.fixture(autouse=True)
def _clear_search_cache():
    """Clear the global search cache before each test to prevent cross-test pollution."""
    get_search_cache().clear()
    yield


from app.models.research_models import (
    CitationVerificationReport,
    ClarificationResult,
    ComparisonSummary,
    EvidenceBundle,
    FullTextChunk,
    FullTextDocument,
    GapReport,
    InnovationIdea,
    Paper,
    PaperInsight,
    ResearchBrief,
    ResearchPlan,
    ResearchRequest,
    ResearchUnit,
    ReviewReport,
    SynthesisReliability,
)


# ---------------------------------------------------------------------------
# Paper / Request fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_papers() -> list[Paper]:
    """Return a list of 3 sample papers for testing."""
    return [
        Paper(
            paper_id="mock-001",
            title="Code Repair with Retrieval-Augmented Language Models",
            authors=["Alice Zhang", "Bob Lin"],
            summary=(
                "This paper studies automatic program repair with retrieval-augmented language models. "
                "The method retrieves historical bug-fix pairs, conditions the generator with evidence, "
                "and improves patch correctness on multi-language benchmarks."
            ),
            published="2024-05-01",
            pdf_url="https://example.com/mock-001.pdf",
            source="openalex",
        ),
        Paper(
            paper_id="mock-002",
            title="Agentic Literature Review for Scientific Discovery",
            authors=["Cara Xu", "David Chen"],
            summary=(
                "The work proposes an agent pipeline for scientific literature review. "
                "A planner decomposes the topic, a reader extracts evidence snippets, "
                "and a synthesizer builds structured notes and research gaps."
            ),
            published="2024-02-15",
            pdf_url="https://example.com/mock-002.pdf",
            source="arxiv",
        ),
        Paper(
            paper_id="mock-003",
            title="Faithful Paper Comparison with Evidence-Grounded Summaries",
            authors=["Ethan Wu", "Fiona Gu"],
            summary=(
                "This paper focuses on faithful comparison across research papers. "
                "It aligns papers under common dimensions and attaches evidence spans to each claim."
            ),
            published="2023-11-10",
            pdf_url="https://example.com/mock-003.pdf",
            source="openalex",
        ),
    ]


@pytest.fixture
def sample_request() -> ResearchRequest:
    """Return a standard ResearchRequest for testing."""
    return ResearchRequest(topic="test topic", max_papers=3)


@pytest.fixture
def sample_plan() -> ResearchPlan:
    """Return a sample ResearchPlan for testing."""
    return ResearchPlan(
        normalized_topic="test topic",
        search_keywords=["test topic"],
        focus_areas=["method"],
        output_sections=["Overview"],
    )


@pytest.fixture
def sample_clarification() -> ClarificationResult:
    """Return a sample ClarificationResult for testing."""
    return ClarificationResult(
        clarified_topic="test topic",
        research_goal="Summarize and identify gaps.",
        scope="Test scope",
    )


@pytest.fixture
def sample_brief() -> ResearchBrief:
    """Return a sample ResearchBrief for testing."""
    return ResearchBrief(
        topic="test topic",
        objective="Summarize and identify gaps.",
        key_questions=["What are the main approaches?"],
    )


@pytest.fixture
def sample_research_units() -> list[ResearchUnit]:
    """Return a sample list of ResearchUnit for testing."""
    return [
        ResearchUnit(
            unit_id="unit-1",
            question="What are the core paradigms?",
            focus="method",
            search_queries=["program repair llm"],
            completion_definition="Summarize main paradigms.",
        ),
    ]


@pytest.fixture
def sample_insights(sample_papers) -> list[PaperInsight]:
    """Return a sample list of PaperInsight for testing."""
    return [
        PaperInsight(
            paper=paper,
            problem="Test problem.",
            method="Test method.",
            innovation="Test innovation.",
            findings="Test findings.",
            limitation="Test limitation.",
            confidence=0.8,
        )
        for paper in sample_papers
    ]


@pytest.fixture
def sample_evidence_bundles() -> list[EvidenceBundle]:
    """Return a sample list of EvidenceBundle for testing."""
    return [
        EvidenceBundle(
            unit_id="unit-1",
            question="What are the core paradigms?",
            synthesized_findings="Two main paradigms identified.",
            supporting_paper_ids=["mock-001", "mock-002"],
            confidence=0.8,
        ),
    ]


@pytest.fixture
def sample_comparison() -> ComparisonSummary:
    """Return a sample ComparisonSummary for testing."""
    return ComparisonSummary(
        overview="Test overview.",
        trends=["Trend A"],
        gaps=["Gap A"],
        ideas=[InnovationIdea(title="Idea A", rationale="Test rationale.", risk="Test risk.")],
    )


@pytest.fixture
def sample_gap_report() -> GapReport:
    """Return a sample GapReport for testing."""
    return GapReport(
        need_follow_up=False,
        missing_aspects=[],
        follow_up_queries=[],
        reasoning="Current evidence is sufficient.",
    )


@pytest.fixture
def sample_full_text_documents(sample_papers) -> dict[str, FullTextDocument]:
    """Return a sample dict of FullTextDocument for testing."""
    documents: dict[str, FullTextDocument] = {}
    for paper in sample_papers[:2]:
        documents[paper.paper_id] = FullTextDocument(
            paper_id=paper.paper_id,
            source="pdf",
            page_count=2,
            chunks=[
                FullTextChunk(text="Introduction. Retrieval-augmented repair improves correctness.", section="Introduction", page=1),
                FullTextChunk(text="Method. The model retrieves bug-fix pairs and conditions generation.", section="Method", page=2),
            ],
        )
    return documents


@pytest.fixture
def sample_review_report() -> ReviewReport:
    """Return a sample ReviewReport for testing."""
    return ReviewReport(
        verdict="overall_pass",
        strengths=["Complete structure."],
        risks=["Still abstract-level."],
        revision_advice=["Add full-text evidence."],
    )


# ---------------------------------------------------------------------------
# Fake LLM / Search helpers (used across multiple test modules)
# ---------------------------------------------------------------------------


class FakeSearchClient:
    """A fake search client that returns pre-configured papers."""

    def __init__(self, papers: list[Paper]):
        self.papers = papers

    def search_papers(self, query: str, max_results: int):
        return self.papers[:max_results]


class FailingSearchClient:
    """A fake search client that always raises an error."""

    def search_papers(self, query: str, max_results: int):
        raise RuntimeError("network error")
