import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FileClock, LoaderCircle, RefreshCw, Sparkles } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { EvidenceBundlePanel } from "@/components/EvidenceBundlePanel";
import { PaperListPanel } from "@/components/PaperCard";
import { RecommendationsPanel } from "@/components/RecommendationsPanel";
import {
  CitationPanel,
  ClaimTablePanel,
  GapReportPanel,
  InsightList,
  OverviewPanel,
  ReviewDecisionPanel,
  StageTimeline,
} from "@/components/ReportPanels";
import { ReportExportPanel } from "@/components/ReportExportPanel";
import { useResearchStore } from "@/store/researchStore";

export default function ReportDetailPage() {
  const { reportId = "" } = useParams();
  const navigate = useNavigate();
  const {
    report,
    activeReportId,
    requestStatus,
    errorState,
    clearError,
    loadArchivedReport,
    prepareFollowUp,
    recommendations,
    recommendationLoading,
    fetchRecommendations,
  } = useResearchStore();

  useEffect(() => {
    if (!reportId || activeReportId === reportId) {
      return;
    }
    void loadArchivedReport(reportId);
  }, [activeReportId, loadArchivedReport, reportId]);

  if (activeReportId !== reportId && requestStatus !== "error") {
    return (
      <section
        className="rounded-xl px-6 py-12"
        style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
      >
        <div className="flex items-center gap-3" style={{ color: "#273951" }}>
          <LoaderCircle className="h-5 w-5 animate-spin" />
          <span>正在载入历史报告详情</span>
        </div>
      </section>
    );
  }

  if (errorState && activeReportId !== reportId) {
    return (
      <section
        className="rounded-xl px-6 py-8"
        style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
      >
        <p className="text-lg font-semibold" style={{ color: "#0d253d" }}>
          {errorState.title}
        </p>
        <p className="mt-3 text-sm leading-6" style={{ color: "#64748b" }}>
          {errorState.detail}
        </p>
        <p className="mt-2 text-xs leading-6" style={{ color: "#64748b" }}>
          {errorState.suggestion}
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              clearError();
              void loadArchivedReport(reportId);
            }}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition hover:opacity-80"
            style={{ background: "#533afd", color: "#ffffff", border: "none" }}
          >
            <RefreshCw className="h-4 w-4" />
            重新载入
          </button>
          <Link
            to="/"
            className="rounded-full px-4 py-2 text-sm transition hover:opacity-80"
            style={{ color: "#273951", background: "#f6f9fc", border: "1px solid #e3e8ee" }}
          >
            返回工作台
          </Link>
        </div>
      </section>
    );
  }

  if (!report || activeReportId !== reportId) {
    return (
      <EmptyState
        title="还没有历史报告详情"
        description="请先从工作台历史列表打开一份已归档报告，或刷新页面后重新载入该报告。"
      />
    );
  }

  // 1. follow-up 候选方向，优先使用 gap_report.follow_up_queries。
  const followUpQueries = report.gap_report.follow_up_queries.slice(0, 6);

  // 2. handleFollowUp 把当前报告的请求参数与指定方向带回工作台。
  const handleFollowUp = (direction: string) => {
    prepareFollowUp({
      baseRequest: report.request,
      direction,
      sourceReportId: reportId,
    });
    navigate("/");
  };

  return (
    <div className="space-y-6">
      {/* ─── Hero section: white card with subtle gradient overlay ─── */}
      <section
        className="relative overflow-hidden rounded-2xl"
        style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
      >
        {/* Subtle gradient mesh background */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.035]"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 20% 10%, #533afd 0%, transparent 60%), radial-gradient(ellipse 60% 50% at 80% 80%, #665efd 0%, transparent 50%), radial-gradient(ellipse 40% 40% at 50% 50%, #b9b9f9 0%, transparent 70%)",
          }}
        />

        <div className="relative flex flex-col gap-5 p-6 xl:flex-row xl:items-start xl:justify-between xl:p-8">
          <div>
            <p
              style={{
                color: "#64748b",
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.2em",
              }}
            >
              Archived Report
            </p>
            <h1
              className="mt-3 max-w-4xl leading-tight"
              style={{
                color: "#0d253d",
                fontSize: "24px",
                fontWeight: 300,
              }}
            >
              {report.request.topic}
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-7" style={{ color: "#64748b" }}>
              这里集中展示当前历史报告的审查结果、结构化综述、证据整理、核验记录和阶段轨迹，便于回看与复用。
            </p>
            <div className="mt-5 flex flex-wrap gap-3 text-xs" style={{ color: "#273951" }}>
              <MetaTag label="报告编号" value={reportId} />
              <MetaTag label="论文数" value={String(report.papers.length)} />
              <MetaTag
                label="支持率"
                value={`${Math.round(report.citation_verification.overall_score * 100)}%`}
              />
              <MetaTag label="阶段数" value={String(report.stage_history.length)} />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition hover:opacity-80"
              style={{ color: "#273951", background: "#f6f9fc", border: "1px solid #e3e8ee" }}
            >
              <ArrowLeft className="h-4 w-4" />
              返回工作台
            </Link>
            <button
              type="button"
              onClick={() => handleFollowUp("")}
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition hover:opacity-90"
              style={{ background: "#533afd", color: "#ffffff", border: "none" }}
            >
              <FileClock className="h-4 w-4" />
              基于当前结果继续研究
            </button>
          </div>
        </div>

        {followUpQueries.length ? (
          <div
            className="relative mx-6 mb-6 rounded-xl px-5 py-4 xl:mx-8"
            style={{ background: "#f6f9fc", border: "1px solid #e3e8ee" }}
          >
            <div className="flex items-center gap-2" style={{ color: "#0d253d" }}>
              <Sparkles className="h-4 w-4" />
              <span className="text-sm font-medium">推荐 follow-up 检索方向</span>
            </div>
            <p className="mt-2 text-xs leading-5" style={{ color: "#64748b" }}>
              这些方向来源于当前报告的研究空白分析，点击即可在工作台预填新一轮研究任务。
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {followUpQueries.map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => handleFollowUp(query)}
                  className="rounded-full px-3 py-1.5 text-xs transition hover:opacity-80"
                  style={{ color: "#0d253d", background: "#ffffff", border: "1px solid #e3e8ee" }}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <ReportExportPanel report={report} />
      <PaperListPanel papers={report.papers} />
      <ReviewDecisionPanel reviewReport={report.review_report} />
      <GapReportPanel gapReport={report.gap_report} />
      <OverviewPanel
        overview={report.comparison.overview}
        trends={report.comparison.trends}
        gaps={report.comparison.gaps}
        ideas={report.comparison.ideas}
        researchNote={report.research_note}
        nextActions={report.next_actions}
      />
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <CitationPanel report={report.citation_verification} />
        <StageTimeline stages={report.stage_history} />
      </div>
      <EvidenceBundlePanel bundles={report.evidence_bundles} />
      <ClaimTablePanel rows={report.claim_evidence_table} />
      <InsightList insights={report.insights} />
      <RecommendationsPanel
        recommendations={recommendations}
        loading={recommendationLoading}
        onLoadMore={() => void fetchRecommendations(report.plan.normalized_topic || report.request.topic)}
      />
    </div>
  );
}

function MetaTag({ label, value }: { label: string; value: string }) {
  return (
    <span
      className="rounded-full px-3 py-1"
      style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", color: "#273951" }}
    >
      {label}：{value}
    </span>
  );
}
