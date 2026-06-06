import type {
  ResearchReport,
  ComparisonSummary,
} from "@/types/research";

type LegacyGapReport = {
  missing_aspects?: string[];
  follow_up_queries?: string[];
  need_follow_up?: boolean;
  gap_reasoning?: string;
};

type LegacyComparison = ComparisonSummary & {
  follow_up_queries?: string[];
  need_follow_up?: boolean;
  gap_reasoning?: string;
};

type RawReport = ResearchReport & {
  gap_report?: LegacyGapReport;
  comparison?: LegacyComparison;
};

export function normalizeReport(raw: RawReport): ResearchReport {
  const gap = raw.gap_report;
  const comp = raw.comparison;

  const merged: ComparisonSummary = {
    overview: comp?.overview ?? "",
    trends: comp?.trends ?? [],
    gaps: comp?.gaps ?? gap?.missing_aspects ?? [],
    ideas: comp?.ideas ?? [],
    need_follow_up: comp?.need_follow_up ?? gap?.need_follow_up ?? false,
    follow_up_queries: comp?.follow_up_queries ?? gap?.follow_up_queries ?? [],
    gap_reasoning: comp?.gap_reasoning ?? gap?.gap_reasoning ?? "",
  };

  return {
    request: raw.request,
    plan: raw.plan,
    research_units: raw.research_units ?? [],
    papers: raw.papers ?? [],
    full_text_documents: raw.full_text_documents ?? [],
    insights: raw.insights ?? [],
    evidence_bundles: raw.evidence_bundles ?? [],
    comparison: merged,
    review_report: raw.review_report,
    synthesis_reliability: raw.synthesis_reliability ?? null,
    stage_history: raw.stage_history ?? [],
    research_note: raw.research_note ?? "",
    next_actions: raw.next_actions ?? [],
    debate_log: raw.debate_log ?? [],
    unit_syntheses: raw.unit_syntheses ?? [],
    fact_check_report: raw.fact_check_report ?? null,
    contradictions: raw.contradictions ?? [],
  };
}
