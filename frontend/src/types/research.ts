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

export type ClaimEvidenceRow = {
  claim: string;
  supporting_unit_ids: string[];
  supporting_paper_ids: string[];
  evidence: EvidenceSnippet[];
  support_level: string;
  rationale: string;
};

export type CitationVerificationItem = {
  claim: string;
  supported: boolean;
  support_level: string;
  matched_claim_indices: number[];
  reason: string;
  evidence: EvidenceSnippet[];
};

export type CitationVerificationReport = {
  overall_score: number;
  supported_count: number;
  unsupported_count: number;
  items: CitationVerificationItem[];
};

export type FullTextDocument = {
  paper_id: string;
  source: string;
  page_count: number;
  chunks: Array<{
    text: string;
    section: string;
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
};

export type ReviewReport = {
  verdict: string;
  strengths: string[];
  risks: string[];
  revision_advice: string[];
};

export type GapReport = {
  need_follow_up: boolean;
  missing_aspects: string[];
  follow_up_queries: string[];
  reasoning: string;
};

export type StageTransition = {
  stage: string;
  status: string;
  summary: string;
  duration_ms?: number;
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

export type ResearchReport = {
  request: ResearchRequest;
  clarification: {
    clarified_topic: string;
    research_goal: string;
    scope: string;
    constraints: string[];
    deliverable: string;
    output_language: string;
  };
  brief: {
    topic: string;
    objective: string;
    key_questions: string[];
    search_strategy: string[];
    success_criteria: string[];
    writing_plan: string[];
  };
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
  claim_evidence_table: ClaimEvidenceRow[];
  gap_report: GapReport;
  comparison: ComparisonSummary;
  citation_verification: CitationVerificationReport;
  review_report: ReviewReport;
  stage_history: StageTransition[];
  research_note: string;
  next_actions: string[];
};

// ============ 新增类型：SSE 事件 ============

export type SSEEvent = {
  event_type: string;
  stage: string;
  message: string;
  progress: number;
  data?: Record<string, unknown>;
};

// ============ 新增类型：趋势分析 ============

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

// ============ 新增类型：论文推荐 ============

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
