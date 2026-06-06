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
import ProgressPanel from "@/components/ProgressPanel";
import { useResearchStore } from "@/store/researchStore";
import { useResearchStream } from "@/hooks/useEventSource";
import type { ResearchReport, ResearchRequest } from "@/types/research";
import { deleteArchivedReport, requestArchivedReport, requestReportHistory } from "@/utils/api";
import { normalizeReport } from "@/utils/normalizeReport";

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
  const sseEvents = useResearchStore((s) => s.sseEvents);
  const sseConnected = useResearchStore((s) => s.sseConnected);

  // 页面挂载：刷新后优先尝试用 task_id 续连后端事件流；失败则保留进度+轮询归档
  useEffect(() => {
    // 1. 始终拉一次最新历史
    void fetchReportHistory();
    // 2. 若上次任务还在跑且持久化了 task_id，则尝试续连
    const { activeTaskId, activeTaskCursor } = useResearchStore.getState();
    if (requestStatus === "loading" && activeTaskId && !sseConnected) {
      void stream.resumeStream(activeTaskId, activeTaskCursor ?? sseEvents.length);
    } else if (requestStatus === "loading" && sseEvents.length > 0 && !sseConnected) {
      useResearchStore.setState({
        sseConnected: false,
        sseError: "页面刷新已中断 SSE 连接，正在等待后端归档报告...",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 流中断后定时轮询归档报告：命中同主题报告则自动载入
  useEffect(() => {
    if (requestStatus !== "loading" || sseConnected) return;
    if (sseEvents.length === 0) return;
    const targetTopic = lastRequest?.topic ?? "";
    const interval = window.setInterval(async () => {
      try {
        const history = await requestReportHistory();
        if (history.length === 0) return;
        // 1. 优先匹配同主题最新归档；无主题则取最新
        const matched = targetTopic
          ? history.find((item) => item.topic === targetTopic) ?? null
          : history[0];
        if (!matched) return;
        const archived = await requestArchivedReport(matched.report_id);
        useResearchStore.setState({
          report: normalizeReport(archived),
          activeReportId: matched.report_id,
          requestStatus: "success",
          lastRequest: archived.request,
          sseEvents: [],
          sseError: null,
        });
      } catch {
        // 静默：下次轮询继续尝试
      }
    }, 5000);
    return () => window.clearInterval(interval);
  }, [requestStatus, sseConnected, sseEvents.length, lastRequest]);

  // Handle SSE stream completing with final report
  useEffect(() => {
    if (sseFinalData && requestStatus === "loading") {
      try {
        const report = normalizeReport(sseFinalData as Parameters<typeof normalizeReport>[0]);
        useResearchStore.setState({
          report,
          activeReportId: null,
          requestStatus: "success",
          lastRequest: report.request,
        });
        void fetchReportHistory();
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
                text="6节点 LangGraph"
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
                label="可靠性评分"
                value={
                  report?.synthesis_reliability
                    ? `${Math.round(report.synthesis_reliability.overall_score * 100)}%`
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
          <div className="mb-3 flex items-center justify-between">
            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-[#f6f9fc]">
              <div
                className="h-full rounded-full bg-[#533afd] transition-all duration-500"
                style={{ width: `${Math.min(stream.progress * 100, 100)}%` }}
              />
            </div>
            {sseConnected ? (
              <button
                type="button"
                onClick={() => {
                  void stream.cancelStream();
                  useResearchStore.setState({
                    requestStatus: "idle",
                    errorState: {
                      title: "研究任务已取消",
                      detail: "已请求后端取消当前流水线。",
                      suggestion: "可重新提交新的研究任务。",
                    },
                  });
                }}
                className="ml-3 inline-flex items-center gap-1 rounded-[9999px] border border-[#ea2261]/30 bg-white px-3 py-1 text-[11px] font-medium text-[#ea2261] transition hover:bg-[#fff5f7]"
              >
                <X className="h-3 w-3" />
                取消任务
              </button>
            ) : null}
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
          onDelete={async (reportId) => {
            await deleteArchivedReport(reportId);
            await fetchReportHistory();
            const { report, activeReportId } = useResearchStore.getState();
            if (report && activeReportId === reportId) {
              useResearchStore.setState({ report: null, activeReportId: null, requestStatus: "idle" });
            }
          }}
        />
      </section>

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
