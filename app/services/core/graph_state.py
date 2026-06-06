"""graph_state LangGraph 研究图状态模型。"""

from __future__ import annotations

from typing import List, TypedDict

from app.models.research_models import (
    ComparisonSummary,
    Contradiction,
    DebateRound,
    EvidenceBundle,
    FactCheckReport,
    FullTextDocument,
    Paper,
    PaperInsight,
    ResearchPlan,
    ResearchUnit,
    ReviewReport,
    SSEEvent,
    StageTransition,
    SynthesisReliability,
    UnitSynthesis,
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
    research_note: str
    next_actions: List[str]
    evidence_bundles: List[EvidenceBundle]
    unit_syntheses: List[UnitSynthesis]
    follow_up_queries: List[str]

    # Debate node
    debate_log: List[DebateRound]

    # Review node
    review_report: ReviewReport
    synthesis_reliability: SynthesisReliability

    # Fact check node
    fact_check_report: FactCheckReport
    contradictions: List[Contradiction]

    # Control
    search_iteration: int

    # Per-node SSE events
    events: List[SSEEvent]

    # Per-node stage transitions
    stage_history: List[StageTransition]
