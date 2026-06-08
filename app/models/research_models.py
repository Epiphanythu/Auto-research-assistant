"""research_models 数据模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.constant.paper_constant import (
    DEFAULT_COMPARISON_DIMENSIONS,
    DEFAULT_MAX_FULL_TEXT_PAPER_COUNT,
    FULL_TEXT_SOURCE_ABSTRACT,
)


class ResearchRequest(BaseModel):
    """ResearchRequest 调研请求。"""

    topic: str = Field(..., description="研究主题")
    max_papers: int = Field(default=5, ge=1, le=20, description="最多返回论文数")
    include_memory: bool = Field(default=True, description="是否启用历史记忆")
    enable_full_text: bool = Field(default=False, description="是否启用 PDF 全文解析")
    max_full_text_papers: int = Field(
        default=DEFAULT_MAX_FULL_TEXT_PAPER_COUNT,
        ge=0,
        le=10,
        description="最多执行全文解析的论文数",
    )

    def get_topic(self) -> str:
        """get_topic 获取研究主题。"""
        return self.topic.strip()

    def get_max_papers(self) -> int:
        """get_max_papers 获取论文数量。"""
        return self.max_papers

    def is_full_text_enabled(self) -> bool:
        """is_full_text_enabled 判断是否开启全文解析。"""
        return self.enable_full_text

    def get_max_full_text_papers(self) -> int:
        """get_max_full_text_papers 获取全文解析论文数。"""
        return self.max_full_text_papers


class ResearchPlan(BaseModel):
    """ResearchPlan 调研规划。"""

    normalized_topic: str
    search_keywords: List[str]
    focus_areas: List[str]
    output_sections: List[str]


class ResearchUnit(BaseModel):
    """ResearchUnit 并行研究单元。"""

    unit_id: str
    question: str
    focus: str
    search_queries: List[str] = Field(default_factory=list)
    completion_definition: str = ""
    status: str = "pending"


class Paper(BaseModel):
    """Paper 论文基础信息。"""

    paper_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    summary: str
    published: str = ""
    pdf_url: str = ""
    source: str = "arxiv"
    citation_count: int = 0
    tldr: str = ""
    doi: str = ""
    affiliations: List[str] = Field(default_factory=list)
    topic_relevance_score: float = 0.0
    relevance_reason: str = ""

    def get_summary(self) -> str:
        """get_summary 获取摘要。"""
        return self.summary or ""

    def get_title(self) -> str:
        """get_title 获取标题。"""
        return self.title

    def get_relevance_score(self) -> float:
        """get_relevance_score 获取论文与当前主题的相关性分数。"""
        return self.topic_relevance_score


class EvidenceSnippet(BaseModel):
    """EvidenceSnippet 证据片段。"""

    snippet: str
    reason: str
    source: str = FULL_TEXT_SOURCE_ABSTRACT
    section: str = ""
    section_kind: str = ""
    page: int = 0


class FullTextChunk(BaseModel):
    """FullTextChunk 全文分块。"""

    text: str
    section: str = ""
    section_kind: str = "other"  # abstract/introduction/related_work/method/experiment/result/discussion/conclusion/other
    page: int = 0


class FullTextDocument(BaseModel):
    """FullTextDocument 全文解析结果。"""

    paper_id: str
    source: str = ""
    page_count: int = 0
    chunks: List[FullTextChunk] = Field(default_factory=list)
    tables: List["QuantitativeResult"] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    """EvidenceBundle 证据包。"""

    unit_id: str
    question: str
    synthesized_findings: str
    supporting_paper_ids: List[str] = Field(default_factory=list)
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    confidence: float = 0.5


class UnitSynthesis(BaseModel):
    """UnitSynthesis 单个研究单元的小节级综合结果（Phase 2 引入）。"""

    unit_id: str
    question: str
    summary: str = ""                            # 该研究问题的综合回答（一段中文）
    key_methods: List[str] = Field(default_factory=list)   # 与此问题相关的核心方法
    consensus: List[str] = Field(default_factory=list)     # 各论文达成共识的结论
    disagreements: List[str] = Field(default_factory=list) # 各论文之间的矛盾或差异
    supporting_paper_ids: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list) # 尚未解决的问题
    confidence: float = 0.5


class QuantitativeResult(BaseModel):
    """QuantitativeResult 定量实验结果。"""

    dataset: str = ""
    metric: str = ""
    value: str = ""
    baseline: str = ""


# ─── 证据可靠性评估框架（三层） ───


class PaperQualityMetrics(BaseModel):
    """PaperQualityMetrics 论文方法学质量评估（第一层：论文级）。"""

    study_design: str = ""          # controlled_experiment / ablation / observational / theoretical / benchmark
    data_availability: str = ""     # public / private / synthetic / unspecified
    reproducibility: str = ""       # code_public / code_partial / code_unavailable / unspecified
    baseline_fairness: str = ""     # standard_baselines / weak_baselines / no_comparison / unspecified
    metric_type: str = ""           # standard / custom / mixed / unspecified
    overall_score: float = 0.5      # 0~1 综合质量分
    note: str = ""


class ClaimReliability(BaseModel):
    """ClaimReliability 结论级证据可靠性（第二层：结论级）。"""

    claim: str
    supporting_papers: List[str] = Field(default_factory=list)
    contradicting_papers: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    reliability_level: str = "moderate"  # strong / moderate / weak / isolated
    reliability_score: float = 0.5
    reasoning: str = ""
    quality_signals: List[str] = Field(default_factory=list)


class SynthesisReliability(BaseModel):
    """SynthesisReliability 综合级自评估（第三层：综合级）。"""

    claims: List[ClaimReliability] = Field(default_factory=list)
    overall_score: float = 0.5
    strong_count: int = 0
    moderate_count: int = 0
    weak_count: int = 0
    isolated_count: int = 0
    coverage_assessment: str = ""
    recommended_actions: List[str] = Field(default_factory=list)


class PaperInsight(BaseModel):
    """PaperInsight 单篇论文洞察。"""

    paper: Paper
    problem: str
    method: str
    innovation: str
    findings: str
    limitation: str
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    confidence: float = 0.5
    full_text_used: bool = False
    quantitative_results: List[QuantitativeResult] = Field(default_factory=list)
    quality_metrics: Optional[PaperQualityMetrics] = None


# ─── Multi-Agent Debate ───


class CriticWeakness(BaseModel):
    """CriticWeakness Critic 发现的弱点。"""

    point: str
    severity: str = "medium"  # high / medium / low
    suggestion: str = ""


class DebateRound(BaseModel):
    """DebateRound 一轮辩论。"""

    round_number: int = 1
    critic_weaknesses: List[CriticWeakness] = Field(default_factory=list)
    critic_quality_score: int = 0
    passed: bool = False
    revision_summary: str = ""


# ─── Fact Check (Phase 3 引入) ───


class ClaimFactCheck(BaseModel):
    """ClaimFactCheck research_note 中单个论断的事实校验结果。"""

    claim: str                                      # 论断原文
    supported: bool = False                          # 是否找到证据支撑
    support_level: str = "unsupported"               # strong / moderate / weak / unsupported
    matched_paper_ids: List[str] = Field(default_factory=list)
    matched_evidence: List[EvidenceSnippet] = Field(default_factory=list)
    keyword_overlap_score: float = 0.0               # 0~1 的关键词重叠分
    reason: str = ""                                  # 评估理由
    nli_verdict: Optional[str] = None                # LLM NLI 二次校验：entailment / contradiction / neutral
    nli_rationale: str = ""                          # NLI 校验给出的简短说明


class FactCheckReport(BaseModel):
    """FactCheckReport research_note 整体的事实校验报告。"""

    total_claims: int = 0
    supported_count: int = 0
    weak_count: int = 0
    unsupported_count: int = 0
    overall_score: float = 0.0                       # supported / total
    items: List[ClaimFactCheck] = Field(default_factory=list)
    flagged_claims: List[str] = Field(default_factory=list)  # 严重缺乏证据支撑的论断列表
    nli_verified_count: int = 0                      # 通过 LLM NLI 二次校验的弱论断数


class Contradiction(BaseModel):
    """Contradiction 跨论文论断矛盾对。"""

    topic: str = ""                                   # 简短主题描述
    claim_a: str = ""                                 # 论断 A 原文
    claim_b: str = ""                                 # 论断 B 原文
    paper_id_a: str = ""                              # 论断 A 来源论文 ID
    paper_id_b: str = ""                              # 论断 B 来源论文 ID
    rationale: str = ""                               # 矛盾解释


# ─── Legacy models (kept for internal pipeline compatibility) ───


class ClaimEvidenceRow(BaseModel):
    """ClaimEvidenceRow 结论与证据映射行（内部使用）。"""

    claim: str
    supporting_unit_ids: List[str] = Field(default_factory=list)
    supporting_paper_ids: List[str] = Field(default_factory=list)
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    support_level: str = "partial"
    rationale: str = ""


class CitationVerificationItem(BaseModel):
    """CitationVerificationItem 单条结论核验结果（内部使用）。"""

    claim: str
    supported: bool = False
    support_level: str = "unsupported"
    matched_claim_indices: List[int] = Field(default_factory=list)
    reason: str = ""
    evidence: List[EvidenceSnippet] = Field(default_factory=list)


class CitationVerificationReport(BaseModel):
    """CitationVerificationReport 引文核验结果（内部使用）。"""

    overall_score: float = 0.0
    supported_count: int = 0
    unsupported_count: int = 0
    items: List[CitationVerificationItem] = Field(default_factory=list)


class InnovationIdea(BaseModel):
    """InnovationIdea 创新建议。"""

    title: str
    rationale: str
    risk: str


class ComparisonSummary(BaseModel):
    """ComparisonSummary 多论文比较结果（含研究空白）。"""

    dimensions: List[str] = Field(default_factory=lambda: list(DEFAULT_COMPARISON_DIMENSIONS))
    overview: str
    trends: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    ideas: List[InnovationIdea] = Field(default_factory=list)
    need_follow_up: bool = False
    follow_up_queries: List[str] = Field(default_factory=list)
    gap_reasoning: str = ""


class ResearchMemory(BaseModel):
    """ResearchMemory 调研记忆。"""

    topic: str
    seen_paper_ids: List[str] = Field(default_factory=list)
    preferred_keywords: List[str] = Field(default_factory=list)
    latest_summary: str = ""


class ReviewReport(BaseModel):
    """ReviewReport 审查结果。"""

    verdict: str
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    revision_advice: List[str] = Field(default_factory=list)


class StageTransition(BaseModel):
    """StageTransition 状态机阶段轨迹。"""

    stage: str
    status: str
    summary: str
    duration_ms: int = 0


class ResearchReport(BaseModel):
    """ResearchReport 最终调研报告。"""

    request: ResearchRequest
    plan: ResearchPlan
    memory: Optional[ResearchMemory] = None
    research_units: List[ResearchUnit] = Field(default_factory=list)
    papers: List[Paper] = Field(default_factory=list)
    full_text_documents: List[FullTextDocument] = Field(default_factory=list)
    insights: List[PaperInsight] = Field(default_factory=list)
    evidence_bundles: List[EvidenceBundle] = Field(default_factory=list)
    unit_syntheses: List[UnitSynthesis] = Field(default_factory=list)
    comparison: ComparisonSummary
    review_report: ReviewReport
    synthesis_reliability: Optional[SynthesisReliability] = None
    stage_history: List[StageTransition] = Field(default_factory=list)
    research_note: str
    next_actions: List[str] = Field(default_factory=list)
    debate_log: List[DebateRound] = Field(default_factory=list)
    fact_check_report: Optional["FactCheckReport"] = None
    contradictions: List[Contradiction] = Field(default_factory=list)
    llm_call_stats: Dict[str, Any] = Field(default_factory=dict)


class ReportArchiveSummary(BaseModel):
    """ReportArchiveSummary 报告归档摘要。"""

    report_id: str
    topic: str
    created_at: str
    paper_count: int = 0
    stage_count: int = 0
    support_score: float = 0.0
    verdict: str = ""


# ============ 趋势分析 ============

class TopicTrendPoint(BaseModel):
    """TopicTrendPoint 趋势数据点。"""

    year: int
    count: int = 0
    metric: str = ""


class CitationVelocity(BaseModel):
    """CitationVelocity 引用速度。"""

    year: int
    avg_citations_per_year: float = 0.0
    total_citations: int = 0
    paper_count: int = 0


class TrendAnalysisResult(BaseModel):
    """TrendAnalysisResult 趋势分析结果。"""

    topic: str
    year_range: str = ""
    yearly_paper_counts: List[TopicTrendPoint] = Field(default_factory=list)
    citation_velocity: List[CitationVelocity] = Field(default_factory=list)
    keyword_trends: Dict[str, List[TopicTrendPoint]] = Field(default_factory=dict)
    emerging_topics: List[str] = Field(default_factory=list)
    trend_summary: str = ""
    hot_directions: List[str] = Field(default_factory=list)
    cooling_directions: List[str] = Field(default_factory=list)


# ============ 新增模型：论文推荐 ============

class PaperRecommendation(BaseModel):
    """PaperRecommendation 论文推荐。"""

    paper_id: str = ""
    title: str = ""
    authors: List[str] = Field(default_factory=list)
    abstract: str = ""
    tldr: str = ""
    year: Optional[int] = None
    citation_count: int = 0
    pdf_url: str = ""
    reason: str = ""


# ============ 新增模型：SSE 事件 ============

class SSEEvent(BaseModel):
    """SSEEvent 服务端推送事件。"""

    event_type: str  # stage_start, stage_complete, progress, paper_found, final_report, error
    stage: str = ""
    message: str = ""
    progress: float = 0.0
    data: Optional[Dict[str, Any]] = None
