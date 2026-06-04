"""graph_state LangGraph 研究图状态模型。"""

from __future__ import annotations

from typing import List, TypedDict

from app.models.research_models import (
    ComparisonSummary,
    EvidenceBundle,
    FullTextDocument,
    GapReport,
    Paper,
    PaperInsight,
    ResearchPlan,
    ResearchUnit,
    ReviewReport,
    SSEEvent,
    StageTransition,
    SynthesisReliability,
)


class GraphState(TypedDict, total=False):
    """GraphState LangGraph 研究图状态。"""

    # Input
    topic: str
    max_papers: int
    enable_full_text: bool
    max_full_text_papers: int
    include_memory: bool

    # Plan node
    clarified_topic: str
    search_keywords: List[str]
    research_units: List[ResearchUnit]
    plan: ResearchPlan

    # Search node
    papers: List[Paper]
    full_text_documents: List[FullTextDocument]
    insights: List[PaperInsight]

    # Synthesize node
    comparison: ComparisonSummary
    gap_report: GapReport
    research_note: str
    next_actions: List[str]
    evidence_bundles: List[EvidenceBundle]
    follow_up_queries: List[str]
    synthesis_reliability: SynthesisReliability

    # Review node
    review_report: ReviewReport

    # Control
    search_iteration: int

    # Per-node SSE events
    events: List[SSEEvent]

    # Per-node stage transitions
    stage_history: List[StageTransition]
