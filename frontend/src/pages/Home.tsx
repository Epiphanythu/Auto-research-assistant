import { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Orbit,
  ShieldEllipsis,
  TrendingUp,
  X,
} from "lucide-react";

import { ReportExportPanel } from "@/components/ReportExportPanel";
import { ReportHistoryPanel } from "@/components/ReportHistoryPanel";
import { ResearchForm } from "@/components/ResearchForm";
import { StatusStrip } from "@/components/StatusStrip";
import ProgressPanel from "@/components/ProgressPanel";
import { useResearchStore } from "@/store/researchStore";
import { useResearchStream } from "@/hooks/useEventSource";
import type { ResearchReport, ResearchRequest } from "@/types/research";

export default function Home() {
  const {
    report,
    requestStatus,
    errorState,
    runResearch,
    clearError,
    lastRequest,
    historyStatus,
    reportHistory,
    fetchReportHistory,
    pendingFollowUp,
    clearFollowUp,
    compareSelection,
    toggleCompareSelection,
    clearCompareSelection,
    setReportFromStream,
  } = useResearchStore();

  const stream = useResearchStream();
  const sseFinalData = useResearchStore((s) => s.sseFinalData);
  const sseError = useResearchStore((s) => s.sseError);

  useEffect(() => {
    void fetchReportHistory();
  }, [fetchReportHistory]);

  useEffect(() => {
    if (sseFinalData && requestStatus === "loading") {
      try {
        const report = sseFinalData as ResearchReport;
        useResearchStore.setState({
          report,
          activeReportId: null,
          requestStatus: "success",
          lastRequest: report.request,
        });
        fetchReportHistory();
      } catch {
        // ignore parse errors
      }
    }
  }, [sseFinalData, requestStatus, fetchReportHistory]);

  useEffect(() => {
    if (sseError && requestStatus === "loading") {
      useResearchStore.setState({
        requestStatus: "error",
        errorState: {
          title: "研究任务执行失败",
          detail: sseError,
          suggestion: "请检查后端服务状态与模型配置后重试。",
        },
      });
    }
  }, [sseError, requestStatus]);

  const handleSubmit = async (payload: ResearchRequest) => {
    useResearchStore.setState({
      requestStatus: "loading",
      errorState: null,
      lastRequest: payload,
      pendingFollowUp: null,
    });
    stream.startStream(payload);
  };

  const sseEvents = useResearchStore((s) => s.sseEvents);
  const sseConnected = useResearchStore((s) => s.sseConnected);

  const showProgress = (requestStatus === "loading" || sseConnected) && sseEvents.length > 0;

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      {/* ─── Stripe-style Hero ─── */}
      <section className="relative overflow-hidden rounded-2xl border border-[#e3e8ee] bg-white">
        {/* Subtle gradient mesh background */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.035]"
          style={{
            background:
              "radial-gradient(ellipse 80% 60% at 20% 10%, #533afd 0%, transparent 60%), radial-gradient(ellipse 60% 50% at 80% 80%, #665efd 0%, transparent 50%), radial-gradient(ellipse 40% 40% at 50% 50%, #b9b9f9 0%, transparent 70%)",
          }}
        />

        <div className="relative grid gap-8 p-8 lg:p-12 lg:grid-cols-[1.2fr_0.8fr]">
          {/* Left column: headline */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#64748b]">
              Research Workspace
            </p>

            <h1
              className="mt-5 max-w-3xl text-[48px] leading-[1.1] tracking-[-1.4px] font-light text-[#0d253d]"
              style={{ fontFamily: "Inter, system-ui, sans-serif" }}
            >
              自动科研助手
              <span className="block text-[#273951]">多智能体研究工作台</span>
            </h1>

            <p className="mt-6 max-w-2xl text-[15px] leading-7 text-[#64748b]">
              多源并行检索、实时流式进度、研究趋势分析、论文推荐引擎。
            </p>

            {/* Feature badges — pill-tag-soft style */}
            <div className="mt-8 flex flex-wrap gap-3">
              <FeatureBadge
                icon={<Orbit className="h-3.5 w-3.5" />}
                text="5节点 LangGraph"
              />
              <FeatureBadge
                icon={<ShieldEllipsis className="h-3.5 w-3.5" />}
                text="证据链可追踪"
              />
              <FeatureBadge
                icon={<TrendingUp className="h-3.5 w-3.5" />}
                text="趋势分析"
              />
            </div>
          </div>

          {/* Right column: overview card */}
          <div className="rounded-xl border border-[#e3e8ee] bg-[#f6f9fc] p-6">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#64748b]">
              当前概览
            </p>

            <dl className="mt-5 grid gap-3">
              <OverviewRow
                label="当前状态"
                value={formatRequestStatus(requestStatus)}
              />
              <OverviewRow
                label="研究报告"
                value={report ? "已生成" : "尚未生成"}
              />
              <OverviewRow
                label="核验分数"
                value={
                  report
                    ? `${Math.round(report.citation_verification.overall_score * 100)}%`
                    : "-"
                }
              />
              <OverviewRow label="论文来源" value="4源并行" />
            </dl>

            <div className="mt-6 flex gap-3">
              <Link
                to="/review"
                className="inline-flex items-center gap-1.5 rounded-[9999px] border border-[#e3e8ee] bg-white px-4 py-2 text-[13px] font-normal text-[#273951] transition hover:border-[#b9b9f9] hover:text-[#533afd]"
              >
                查看综述
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Research Form ─── */}
      <section className="rounded-2xl border border-[#e3e8ee] bg-white p-6 shadow-sm">
        <ResearchForm
          loading={requestStatus === "loading"}
          initialRequest={lastRequest}
          followUp={pendingFollowUp}
          onClearFollowUp={clearFollowUp}
          onSubmit={handleSubmit}
        />
      </section>

      {/* ─── SSE Progress Panel ─── */}
      {showProgress && (
        <section className="rounded-2xl border border-[#e3e8ee] bg-white p-6 shadow-sm">
          <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-[#f6f9fc]">
            <div
              className="h-full rounded-full bg-[#533afd] transition-all duration-500"
              style={{ width: `${Math.min(stream.progress * 100, 100)}%` }}
            />
          </div>
          <ProgressPanel
            events={sseEvents}
            progress={stream.progress}
            isConnected={sseConnected}
          />
        </section>
      )}

      {/* ─── Error Alert Card ─── */}
      {errorState ? (
        <section className="rounded-2xl border border-[#ea2261]/20 bg-[#fff5f7] px-6 py-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-[#ea2261]/10 p-2 text-[#ea2261]">
                <AlertCircle className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-[#0d253d]">
                  {errorState.title}
                </p>
                <p className="mt-1.5 text-sm leading-6 text-[#273951]">
                  {errorState.detail}
                </p>
                <p className="mt-1 text-xs leading-5 text-[#64748b]">
                  {errorState.suggestion}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={clearError}
              className="rounded-[9999px] border border-[#e3e8ee] bg-white p-1.5 text-[#64748b] transition hover:border-[#ea2261]/30 hover:text-[#ea2261]"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </section>
      ) : null}

      {/* ─── Report Export Panel ─── */}
      {report ? (
        <section className="rounded-2xl border border-[#e3e8ee] bg-white p-6 shadow-sm">
          <ReportExportPanel report={report} compact />
        </section>
      ) : null}

      {/* ─── Report History Panel ─── */}
      <section className="rounded-2xl border border-[#e3e8ee] bg-white p-6 shadow-sm">
        <ReportHistoryPanel
          items={reportHistory}
          loading={historyStatus === "loading"}
          onRefresh={fetchReportHistory}
          compareSelection={compareSelection}
          onToggleCompare={toggleCompareSelection}
          onClearCompare={clearCompareSelection}
        />
      </section>

      {/* ─── Status Strip ─── */}
      <StatusStrip
        paperCount={report?.papers.length ?? 0}
        evidenceBundleCount={report?.evidence_bundles.length ?? 0}
        claimCount={report?.claim_evidence_table.length ?? 0}
        supportScore={report?.citation_verification.overall_score ?? 0}
        unsupportedCount={report?.citation_verification.unsupported_count ?? 0}
        stageCount={report?.stage_history.length ?? 0}
      />
    </div>
  );
}

/* ────────────────────────────────────────────
   Sub-components
   ──────────────────────────────────────────── */

function FeatureBadge({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[9999px] bg-[#b9b9f9]/25 px-3.5 py-1.5 text-[12px] font-medium text-[#4434d4]">
      {icon}
      <span>{text}</span>
    </span>
  );
}

function OverviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-[#e3e8ee] bg-white px-4 py-2.5">
      <dt className="text-[13px] text-[#64748b]">{label}</dt>
      <dd className="text-[13px] font-medium text-[#0d253d]">{value}</dd>
    </div>
  );
}

function formatRequestStatus(status: string) {
  switch (status) {
    case "idle":
      return "待提交";
    case "loading":
      return "处理中";
    case "success":
      return "已完成";
    case "error":
      return "请求失败";
    default:
      return status;
  }
}
