export type ResearchRequest = {
  topic: string;
  max_papers: number;
  include_memory: boolean;
  enable_full_text: boolean;
  max_full_text_papers: number;
};

export type EvidenceSnippet = {
  snippet: string;
  reason: string;
  source: string;
  section: string;
  section_kind?: string;
  page: number;
};

export type ResearchUnit = {
  unit_id: string;
  question: string;
  focus: string;
  search_queries: string[];
  completion_definition: string;
  status: string;
};

export type Paper = {
  paper_id: string;
  title: string;
  authors: string[];
  summary: string;
  published: string;
  pdf_url: string;
  source: string;
  citation_count: number;
  tldr: string;
  doi: string;
  topic_relevance_score?: number;
  relevance_reason?: string;
};

export type PaperInsight = {
  paper: Paper;
  problem: string;
  method: string;
  innovation: string;
  findings: string;
  limitation: string;
  evidence: EvidenceSnippet[];
  confidence: number;
  full_text_used: boolean;
};

export type EvidenceBundle = {
  unit_id: string;
  question: string;
  synthesized_findings: string;
  supporting_paper_ids: string[];
  evidence: EvidenceSnippet[];
  confidence: number;
};

export type FullTextDocument = {
  paper_id: string;
  source: string;
  page_count: number;
  chunks: Array<{
    text: string;
    section: string;
    section_kind?: string;
    page: number;
  }>;
};

export type ComparisonIdea = {
  title: string;
  rationale: string;
  risk: string;
};

export type ComparisonSummary = {
  overview: string;
  trends: string[];
  gaps: string[];
  ideas: ComparisonIdea[];
  need_follow_up: boolean;
  follow_up_queries: string[];
  gap_reasoning: string;
};

export type ReviewReport = {
  verdict: string;
  strengths: string[];
  risks: string[];
  revision_advice: string[];
};

// ─── Multi-Agent Debate ───

export type CriticWeakness = {
  point: string;
  severity: string;
  suggestion: string;
};

export type DebateRound = {
  round_number: number;
  critic_weaknesses: CriticWeakness[];
  critic_quality_score: number;
  passed: boolean;
  revision_summary: string;
};

// ─── Evidence Reliability ───

export type ClaimReliability = {
  claim: string;
  supporting_papers: string[];
  contradicting_papers: string[];
  evidence_count: number;
  reliability_level: string;
  reliability_score: number;
  reasoning: string;
  quality_signals: string[];
};

export type SynthesisReliability = {
  claims: ClaimReliability[];
  overall_score: number;
  strong_count: number;
  moderate_count: number;
  weak_count: number;
  isolated_count: number;
  coverage_assessment: string;
  recommended_actions: string[];
};

export type StageTransition = {
  stage: string;
  status: string;
  summary: string;
  duration_ms?: number;
};

// ─── Unit Synthesis (Phase 2) ───

export type UnitSynthesis = {
  unit_id: string;
  question: string;
  summary: string;
  key_methods: string[];
  consensus: string[];
  disagreements: string[];
  supporting_paper_ids: string[];
  open_questions: string[];
  confidence: number;
};

// ─── Fact Check (Phase 3) ───

export type ClaimFactCheck = {
  claim: string;
  supported: boolean;
  support_level: string;
  matched_paper_ids: string[];
  matched_evidence: EvidenceSnippet[];
  keyword_overlap_score: number;
  reason: string;
  nli_verdict?: string | null;
  nli_rationale?: string;
};

export type FactCheckReport = {
  total_claims: number;
  supported_count: number;
  weak_count: number;
  unsupported_count: number;
  overall_score: number;
  items: ClaimFactCheck[];
  flagged_claims: string[];
  nli_verified_count?: number;
};

export type Contradiction = {
  topic: string;
  claim_a: string;
  claim_b: string;
  paper_id_a: string;
  paper_id_b: string;
  rationale: string;
};

export type ReportArchiveSummary = {
  report_id: string;
  topic: string;
  created_at: string;
  paper_count: number;
  stage_count: number;
  support_score: number;
  verdict: string;
};

// ─── LLM 调用统计（t8/t9） ───

export type LLMCallStats = {
  call_count?: number;
  cache_hit_count?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  total_elapsed_ms?: number;
};

export type ResearchReport = {
  request: ResearchRequest;
  plan: {
    normalized_topic: string;
    search_keywords: string[];
    focus_areas: string[];
    output_sections: string[];
  };
  research_units: ResearchUnit[];
  papers: Paper[];
  full_text_documents: FullTextDocument[];
  insights: PaperInsight[];
  evidence_bundles: EvidenceBundle[];
  comparison: ComparisonSummary;
  review_report: ReviewReport;
  synthesis_reliability: SynthesisReliability | null;
  stage_history: StageTransition[];
  research_note: string;
  next_actions: string[];
  debate_log: DebateRound[];
  unit_syntheses: UnitSynthesis[];
  fact_check_report: FactCheckReport | null;
  contradictions?: Contradiction[];
  llm_call_stats?: LLMCallStats;
};

// ============ SSE 事件 ============

export type SSEEvent = {
  event_type: string;
  stage: string;
  message: string;
  progress: number;
  data?: Record<string, unknown>;
};

// ============ 趋势分析 ============

export type TopicTrendPoint = {
  year: number;
  count: number;
  metric: string;
};

export type CitationVelocity = {
  year: number;
  avg_citations_per_year: number;
  total_citations: number;
  paper_count: number;
};

export type TrendAnalysisResult = {
  topic: string;
  year_range: string;
  yearly_paper_counts: TopicTrendPoint[];
  citation_velocity: CitationVelocity[];
  keyword_trends: Record<string, TopicTrendPoint[]>;
  emerging_topics: string[];
  trend_summary: string;
  hot_directions: string[];
  cooling_directions: string[];
};

// ============ 论文推荐 ============

export type PaperRecommendation = {
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  tldr: string;
  year: number | null;
  citation_count: number;
  pdf_url: string;
  reason: string;
};
