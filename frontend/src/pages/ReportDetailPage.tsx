import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FileClock, LoaderCircle, RefreshCw, Sparkles } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { PaperListPanel } from "@/components/PaperCard";
import {
  ContradictionPanel,
  DebateLogPanel,
  FactCheckPanel,
  StageTimeline,
  UnitSynthesisPanel,
} from "@/components/ReportPanels";
import { ReportExportPanel } from "@/components/ReportExportPanel";
import { useResearchStore } from "@/store/researchStore";
import { normalizeReport } from "@/utils/normalizeReport";

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

  const safeReport = normalizeReport(report);
  const followUpQueries = safeReport.comparison.follow_up_queries.slice(0, 6);

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
      {/* Hero */}
      <section
        className="relative overflow-hidden rounded-2xl"
        style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
      >
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
              style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300 }}
            >
              {report.request.topic}
            </h1>
            <div className="mt-5 flex flex-wrap gap-3 text-xs" style={{ color: "#273951" }}>
              <MetaTag label="报告编号" value={reportId} />
              <MetaTag label="论文数" value={String(report.papers.length)} />
              <MetaTag
                label="可靠性"
                value={report.synthesis_reliability ? `${Math.round(report.synthesis_reliability.overall_score * 100)}%` : "-"}
              />
              <MetaTag label="辩论轮数" value={String(report.debate_log?.length ?? 0)} />
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
      <UnitSynthesisPanel syntheses={safeReport.unit_syntheses ?? []} papers={report.papers ?? []} />
      <FactCheckPanel report={safeReport.fact_check_report} />
      <ContradictionPanel contradictions={safeReport.contradictions ?? []} />
      <DebateLogPanel rounds={report.debate_log ?? []} />
      <StageTimeline stages={report.stage_history} />
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
