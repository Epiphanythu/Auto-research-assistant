"""test_report_service.py Tests for ReportService: end-to-end report generation with fused pipeline stages, memory, and full text."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from app.constant.paper_constant import FULL_TEXT_SOURCE_PDF
from app.models.research_models import (
    FullTextChunk,
    FullTextDocument,
    Paper,
    ResearchPlan,
    ResearchReport,
    ResearchRequest,
    ResearchUnit,
)
from app.services.core.llm_service import LLMConfigurationError, LLMService
from app.services.core.report_service import ReportService
from app.services.core.search_service import SearchService
from app.services.infrastructure.full_text_service import FullTextService


# ---------------------------------------------------------------------------
# LLM response builder: returns appropriate fused JSON per pipeline stage
# ---------------------------------------------------------------------------


def _build_fake_llm_response(system_prompt: str, user_prompt: str) -> dict:
    """Return a mock LLM JSON response appropriate for the current pipeline stage.

    Detection order matters: evidence prompt contains serialized insights with
    "problem"/"method" so we check for "synthesized_findings" BEFORE checking
    for extraction keywords.
    """
    # Fused: clarify + brief
    if "clarified_topic" in user_prompt:
        return {
            "clarified_topic": "LLM-based Automatic Program Repair",
            "research_goal": "Summarize mainstream methods and identify research gaps.",
            "scope": "Focus on retrieval-augmented, agent-based, and evidence-grounded repair.",
            "constraints": ["Focus on recent three years"],
            "key_questions": ["What are the main approaches?", "Which gaps remain?"],
            "search_strategy": ["program repair llm", "agentic program repair"],
            "success_criteria": ["Cover representative methods", "Identify innovation directions"],
        }

    # Fused: plan + supervise
    if "normalized_topic" in user_prompt:
        return {
            "normalized_topic": "LLM-based Automatic Program Repair",
            "search_keywords": ["program repair llm", "apr llm"],
            "focus_areas": ["method", "evaluation", "repair"],
            "research_units": [
                {
                    "unit_id": "unit-1",
                    "question": "What are the core paradigms of current repair methods?",
                    "focus": "method",
                    "search_queries": ["program repair llm", "retrieval augmented program repair"],
                    "completion_definition": "Summarize main method paradigms.",
                },
            ],
        }

    # Evidence reliability assessment -- check BEFORE review since reliability prompt
    # contains "coverage_assessment" and review prompt contains "研究报告内容"
    if "reliability_level" in user_prompt and "quality_signals" in user_prompt:
        return {
            "claims": [
                {
                    "claim": "Retrieval-augmented methods improve patch correctness.",
                    "supporting_papers": ["mock-001", "mock-002"],
                    "contradicting_papers": [],
                    "evidence_count": 2,
                    "reliability_level": "strong",
                    "reliability_score": 0.85,
                    "reasoning": "Two independent studies on standard benchmarks.",
                    "quality_signals": ["2 papers used standard benchmarks", "1 paper open-sourced code"],
                },
                {
                    "claim": "Agent-based orchestration is an emerging direction.",
                    "supporting_papers": ["mock-002"],
                    "contradicting_papers": [],
                    "evidence_count": 1,
                    "reliability_level": "isolated",
                    "reliability_score": 0.4,
                    "reasoning": "Only one paper proposes this, no independent verification.",
                    "quality_signals": ["Single source, no replication"],
                },
            ],
            "coverage_assessment": "Methods are well covered, but empirical comparisons are limited.",
            "recommended_actions": ["Add more benchmark evaluation studies", "Include industry-scale validation"],
        }

    # Critic (multi-agent debate) -- check BEFORE review
    if "学术评审者" in user_prompt and "weaknesses" in user_prompt:
        return {
            "weaknesses": [
                {
                    "point": "研究笔记缺乏对不同方法定量对比的深入分析。",
                    "severity": "medium",
                    "suggestion": "补充各方法在相同基准上的性能差异。",
                },
            ],
            "overall_quality": 6,
            "pass": False,
        }

    # Writer revision (multi-agent debate)
    if "研究综合撰写者" in user_prompt and "revision_summary" in user_prompt:
        return {
            "research_note": "修订后的研究笔记：LLM-based program repair 正在从摘要级别向基于证据的科研助手演进。通过 Critic-Writer 辩论机制，确保了研究综合的严谨性。",
            "overview": "修订后的概览：LLM 在程序修复领域的应用正在快速发展。",
            "trends": ["Retrieval-augmented", "Agent-based orchestration", "Evidence-grounded comparison"],
            "gaps": ["Full-text evidence tracking still insufficient", "Lack of cross-benchmark comparison"],
            "next_actions": ["Add full-text parsing", "Enhance evidence localization", "Verify research gaps"],
            "revision_summary": "根据 Critic 意见，补充了定量对比分析并增强了证据链。",
        }

    # Unit-level synthesis (Phase 2) -- per-question小节综合
    if "本节研究问题" in user_prompt:
        return {
            "summary": "针对本研究问题，候选论文均聚焦检索增强与代理协同两类方法。",
            "key_methods": ["Retrieval-augmented generation", "Agent orchestration"],
            "consensus": ["检索证据有助于提升修复正确率"],
            "disagreements": [],
            "supporting_paper_ids": ["mock-001", "mock-002"],
            "open_questions": ["跨语言修复仍缺基准", "证据片段定位粒度不足"],
            "confidence": 0.75,
        }

    # Global synthesis (Phase 2) -- 聚合多个 unit 综合
    if "各研究问题的小节综合" in user_prompt:
        return {
            "overview": "Focuses on using LLMs to improve repair automation.",
            "trends": ["Retrieval-augmented", "Agent-based orchestration"],
            "gaps": ["Full-text evidence tracking still insufficient"],
            "ideas": [
                {
                    "title": "Evidence Graph-Driven Repair Survey",
                    "rationale": "Enhances survey credibility.",
                    "risk": "Full-text parsing cost is high.",
                }
            ],
            "research_note": "LLM-based program repair is evolving from abstract-level summaries toward evidence-based research assistants.",
            "next_actions": ["Add full-text parsing", "Enhance evidence localization", "Verify research gaps"],
        }

    # Gap detection
    if "need_follow_up" in user_prompt:
        return {
            "need_follow_up": False,
            "missing_aspects": ["Full-text evidence can still be enhanced"],
            "follow_up_queries": [],
            "reasoning": "Current abstract-level evidence is sufficient for an initial survey.",
        }

    # Evidence bundle -- check before extraction
    if "synthesized_findings" in user_prompt:
        return {
            "synthesized_findings": "Identified retrieval-augmented and agent-based as two main directions.",
            "supporting_paper_ids": ["mock-001", "mock-002"],
            "evidence_indices": [0, 1],
            "confidence": 0.8,
        }

    # Extraction (per paper)
    if "problem" in user_prompt and "innovation" in user_prompt and "摘要" in user_prompt:
        return {
            "problem": "Improving patch correctness for automatic program repair.",
            "method": "Retrieval-augmented LLM for patch generation.",
            "innovation": "Historical fix samples with evidence-conditioned generation.",
            "findings": "Improved repair effectiveness on multi-language benchmarks.",
            "limitation": "Sensitive to retrieval quality.",
            "confidence": 0.9,
            "quantitative_results": [
                {"dataset": "Defects4J", "metric": "Accuracy", "value": "78.5%", "baseline": "ChatRepair"},
            ],
            "quality_metrics": {
                "study_design": "controlled_experiment",
                "data_availability": "public",
                "reproducibility": "code_public",
                "baseline_fairness": "standard_baselines",
                "metric_type": "standard",
                "note": "Uses standard benchmarks with open-source code.",
            },
        }

    # Merged compare + write
    if "多篇论文" in user_prompt and "next_actions" in user_prompt:
        return {
            "overview": "Focuses on using LLMs to improve repair automation.",
            "trends": ["Retrieval-augmented", "Agent-based orchestration"],
            "gaps": ["Full-text evidence tracking still insufficient"],
            "ideas": [
                {
                    "title": "Evidence Graph-Driven Repair Survey",
                    "rationale": "Enhances survey credibility.",
                    "risk": "Full-text parsing cost is high.",
                }
            ],
            "research_note": "LLM-based program repair is evolving from abstract-level summaries toward evidence-based research assistants.",
            "next_actions": ["Add full-text parsing", "Enhance evidence localization", "Verify research gaps"],
        }

    # Comparison only
    if "多篇论文" in user_prompt:
        return {
            "overview": "Focuses on using LLMs to improve repair automation.",
            "trends": ["Retrieval-augmented", "Agent-based orchestration"],
            "gaps": ["Full-text evidence tracking still insufficient"],
            "ideas": [
                {
                    "title": "Evidence Graph-Driven Repair Survey",
                    "rationale": "Enhances survey credibility.",
                    "risk": "Full-text parsing cost is high.",
                }
            ],
        }

    # Review
    if "研究报告内容" in user_prompt:
        return {
            "verdict": "overall_pass",
            "strengths": ["Complete structure", "Clear trend summary"],
            "risks": ["Still abstract-level"],
            "revision_advice": ["Add full-text evidence"],
        }

    # Writer
    if "调研结果" in user_prompt:
        return {
            "research_note": "LLM-based program repair is evolving from abstract-level summaries toward evidence-based research assistants.",
            "next_actions": ["Add full-text parsing", "Enhance evidence localization", "Verify research gaps"],
        }

    # Fallback
    return {
        "research_note": "Default research note.",
        "next_actions": ["Action 1", "Action 2", "Action 3"],
    }


def _build_fake_papers(max_papers: int) -> list[Paper]:
    """Build a list of fake papers for testing."""
    papers = [
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
    return papers[:max_papers]


def _build_fake_full_text_documents(papers: list[Paper], max_papers: int) -> dict[str, FullTextDocument]:
    """Build fake full-text documents for the given papers."""
    documents: dict[str, FullTextDocument] = {}
    for idx, paper in enumerate(papers[:max_papers], start=1):
        documents[paper.paper_id] = FullTextDocument(
            paper_id=paper.paper_id,
            source=FULL_TEXT_SOURCE_PDF,
            page_count=2,
            chunks=[
                FullTextChunk(
                    text="Introduction. Retrieval-augmented repair improves patch correctness.",
                    section="Introduction",
                    page=idx,
                ),
                FullTextChunk(
                    text="Method. The model retrieves bug-fix pairs and conditions generation on evidence.",
                    section="Method",
                    page=idx + 1,
                ),
            ],
        )
    return documents


def _setup_mocks(monkeypatch, enable_full_text=False, max_full_text=2, max_papers=3):
    """Set up common mocks for LLM and Search services. Returns the monkeypatched context."""
    monkeypatch.setattr(LLMService, "ensure_enabled", lambda self: None)
    monkeypatch.setattr(LLMService, "ask_json", lambda self, system_prompt, user_prompt, **kw: _build_fake_llm_response(system_prompt, user_prompt))
    monkeypatch.setattr(
        SearchService,
        "search_by_queries",
        lambda self, queries, max_papers, topic="": _build_fake_papers(max_papers),
    )
    if enable_full_text:
        monkeypatch.setattr(
            FullTextService,
            "load_documents",
            lambda self, papers, max_papers: _build_fake_full_text_documents(papers, max_full_text),
        )


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """Tests for ReportService.generate_report (synchronous end-to-end).

    Note: generate_report_stream yields SSEEvent with data=report.model_dump() (a dict).
    generate_report returns this dict, so we wrap it in ResearchReport for assertions.
    """

    @staticmethod
    def _to_report(result) -> ResearchReport:
        """Convert the raw dict returned by generate_report into a ResearchReport."""
        if isinstance(result, dict):
            return ResearchReport(**result)
        return result

    def test_generates_report_with_mocked_pipeline(self, monkeypatch):
        """Full pipeline should produce a complete ResearchReport with all fields populated."""
        _setup_mocks(monkeypatch)
        service = ReportService()
        request = ResearchRequest(topic="LLM program repair", max_papers=3, include_memory=False)

        result = service.generate_report(request)
        report = self._to_report(result)

        assert report.request.topic == "LLM program repair"
        assert len(report.papers) == 3
        assert len(report.insights) == 3
        assert len(report.research_units) >= 1
        assert len(report.evidence_bundles) >= 1
        assert report.comparison.ideas
        assert report.synthesis_reliability is not None
        assert report.synthesis_reliability.overall_score > 0
        assert len(report.synthesis_reliability.claims) >= 1
        assert report.debate_log is not None
        debate_stage = next((stage for stage in report.stage_history if stage.stage == "debate"), None)
        assert debate_stage is not None
        assert debate_stage.status in ("completed", "skipped")
        assert report.review_report.verdict in ("overall_pass", "revision_needed")
        assert len(report.stage_history) >= 8
        assert len(report.research_note) > 0
        assert len(report.next_actions) >= 3

    def test_generates_report_without_memory(self, monkeypatch):
        """Report with include_memory=False should have memory set to None."""
        _setup_mocks(monkeypatch)
        service = ReportService()
        request = ResearchRequest(topic="test topic", max_papers=2, include_memory=False)

        result = service.generate_report(request)
        report = self._to_report(result)

        assert report.memory is None
        assert report.comparison.need_follow_up is False

    def test_generates_report_with_memory(self, monkeypatch, tmp_path):
        """Report with include_memory=True should attempt to save memory."""
        monkeypatch.setenv("MEMORY_PATH", str(tmp_path / "memory.json"))
        _setup_mocks(monkeypatch)
        service = ReportService()
        request = ResearchRequest(topic="LLM program repair", max_papers=2, include_memory=True)

        result = service.generate_report(request)
        report = self._to_report(result)

        assert report.request.topic == "LLM program repair"

    def test_generates_report_with_full_text_evidence(self, monkeypatch):
        """Full-text mode should produce reports with full text documents and full_text_used insights."""
        _setup_mocks(monkeypatch, enable_full_text=True, max_full_text=2)
        service = ReportService()
        request = ResearchRequest(
            topic="LLM program repair",
            max_papers=2,
            include_memory=False,
            enable_full_text=True,
            max_full_text_papers=2,
        )

        result = service.generate_report(request)
        report = self._to_report(result)

        assert len(report.full_text_documents) == 2
        assert any(insight.full_text_used for insight in report.insights)


# ---------------------------------------------------------------------------
# Error case tests
# ---------------------------------------------------------------------------


class TestReportServiceErrors:
    """Tests for ReportService error handling."""

    def test_raises_llm_config_error_when_not_configured(self, monkeypatch):
        """Should raise LLMConfigurationError when LLM is not configured."""
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        from app.config import get_settings
        get_settings.cache_clear()

        service = ReportService()
        request = ResearchRequest(topic="test topic", max_papers=1, include_memory=False)

        with pytest.raises(LLMConfigurationError):
            service.generate_report(request)

        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# SSE stream tests
# ---------------------------------------------------------------------------


class TestGenerateReportStream:
    """Tests for ReportService.generate_report_stream (SSE event stream)."""

    def test_stream_produces_sse_events(self, monkeypatch):
        """generate_report_stream should yield SSEEvent objects for each stage."""
        _setup_mocks(monkeypatch)
        service = ReportService()
        request = ResearchRequest(topic="test topic", max_papers=2, include_memory=False)

        events = list(service.generate_report_stream(request))

        # Should have at least stage_start + stage_complete for init, clarify, plan, research, etc.
        event_types = [e.event_type for e in events]
        assert "stage_start" in event_types
        assert "stage_complete" in event_types
        assert "final_report" in event_types

        # The final event should contain the report data
        final_event = events[-1]
        assert final_event.event_type == "final_report"
        assert final_event.data is not None

    def test_stream_reports_progress(self, monkeypatch):
        """SSE events should have increasing progress values."""
        _setup_mocks(monkeypatch)
        service = ReportService()
        request = ResearchRequest(topic="test topic", max_papers=2, include_memory=False)

        events = list(service.generate_report_stream(request))
        progresses = [e.progress for e in events if e.progress > 0]
        # Progress should be non-decreasing
        for i in range(1, len(progresses)):
            assert progresses[i] >= progresses[i - 1]


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------


class TestReportServiceHelpers:
    """Tests for ReportService internal helper methods."""

    def test_build_search_queries_deduplicates(self):
        """_build_search_queries should deduplicate and limit queries."""
        from app.models.research_models import ResearchUnit
        plan = ResearchPlan(
            normalized_topic="test",
            search_keywords=["query1", "query1", "query2"],
            focus_areas=["method"],
            output_sections=["Overview"],
        )
        units = [
            ResearchUnit(
                unit_id="unit-1",
                question="Q",
                focus="F",
                search_queries=["query2", "query3"],
            ),
        ]
        queries = ReportService._build_search_queries(plan, units)
        assert len(queries) == len(set(queries))
        assert len(queries) <= 4

    def test_ensure_research_units_creates_fallback(self):
        """_ensure_research_units should create a fallback unit when none are provided."""
        from app.models.research_models import ResearchUnit
        units = ReportService._ensure_research_units([], "test topic")
        assert len(units) == 1
        assert units[0].unit_id == "unit-1"

    def test_merge_papers_deduplicates(self):
        """_merge_papers should deduplicate papers by paper_id."""
        papers_a = [
            Paper(paper_id="p1", title="A", authors=[], summary="S.", source="arxiv"),
            Paper(paper_id="p2", title="B", authors=[], summary="S.", source="arxiv"),
        ]
        papers_b = [
            Paper(paper_id="p2", title="B", authors=[], summary="S.", source="arxiv"),
            Paper(paper_id="p3", title="C", authors=[], summary="S.", source="arxiv"),
        ]
        merged = ReportService._merge_papers(papers_a, papers_b, max_papers=10)
        ids = [p.paper_id for p in merged]
        assert len(ids) == len(set(ids))
        assert set(ids) == {"p1", "p2", "p3"}

    def test_merge_papers_respects_max_limit(self):
        """_merge_papers should truncate to max_papers."""
        papers = [
            Paper(paper_id=f"p{i}", title=f"P{i}", authors=[], summary="S.", source="arxiv")
            for i in range(10)
        ]
        merged = ReportService._merge_papers(papers, [], max_papers=3)
        assert len(merged) == 3
