import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, GitCompareArrows, LoaderCircle, RefreshCw } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import type { ResearchReport } from "@/types/research";
import { ResearchRequestError, requestArchivedReport } from "@/utils/api";
import { useResearchStore } from "@/store/researchStore";

type LoadStatus = "idle" | "loading" | "success" | "error";

type LoadedReport = {
  reportId: string;
  status: LoadStatus;
  report: ResearchReport | null;
  errorMessage: string | null;
};

export default function ReportComparePage() {
  const { compareSelection, clearCompareSelection } = useResearchStore();
  const [reports, setReports] = useState<LoadedReport[]>([]);

  // 1. 选中变化时按需加载报告，避免重复拉取已加载的报告。
  useEffect(() => {
    let cancelled = false;
    const ensure = async () => {
      const next: LoadedReport[] = compareSelection.map((reportId) => {
        const existing = reports.find((item) => item.reportId === reportId);
        return (
          existing ?? {
            reportId,
            status: "loading",
            report: null,
            errorMessage: null,
          }
        );
      });
      if (!cancelled) {
        setReports(next);
      }
      // 2. 拉取尚未加载完成的报告。
      const pending = next.filter((item) => item.status !== "success");
      await Promise.all(
        pending.map(async (item) => {
          try {
            const report = await requestArchivedReport(item.reportId);
            if (cancelled) {
              return;
            }
            setReports((current) =>
              current.map((entry) =>
                entry.reportId === item.reportId
                  ? { ...entry, status: "success", report, errorMessage: null }
                  : entry,
              ),
            );
          } catch (error) {
            if (cancelled) {
              return;
            }
            const message =
              error instanceof ResearchRequestError
                ? `${error.title}：${error.detail}`
                : error instanceof Error
                ? error.message
                : "历史报告读取失败";
            setReports((current) =>
              current.map((entry) =>
                entry.reportId === item.reportId
                  ? { ...entry, status: "error", errorMessage: message }
                  : entry,
              ),
            );
          }
        }),
      );
    };
    void ensure();
    return () => {
      cancelled = true;
    };
    // 仅依赖 selection；reports 在内部以函数式更新维护，避免重复刷新。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareSelection]);

  // 3. 把已加载成功的报告整理出来，作为对比视图的数据基础。
  const loadedReports = useMemo(
    () => reports.filter((item) => item.status === "success" && item.report),
    [reports],
  );

  if (!compareSelection.length) {
    return (
      <EmptyState
        title="还没有选中要比对的报告"
        description="请回到工作台，从历史归档中勾选 2 至 3 份报告后再进入比对视图。"
      />
    );
  }

  if (compareSelection.length < 2) {
    return (
      <EmptyState
        title="至少需要 2 份报告才能比对"
        description="比对视图依赖多份归档报告之间的差异，请回到工作台再补充选择。"
      />
    );
  }

  const isLoading = reports.some((item) => item.status === "loading");
  const errorReports = reports.filter((item) => item.status === "error");

  return (
    <div className="space-y-6">
      <section
        className="rounded-[30px] p-6"
        style={{
          background: "#ffffff",
          border: "1px solid #e3e8ee",
          borderRadius: "30px",
          boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
        }}
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
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
              Compare Reports
            </p>
            <h1
              className="mt-3 max-w-3xl leading-tight"
              style={{ color: "#0d253d", fontSize: "36px", fontWeight: 300 }}
            >
              历史报告横向比对
            </h1>
            <p
              className="mt-4 max-w-3xl text-sm leading-7"
              style={{ color: "#64748b" }}
            >
              选中 2 至 3 份归档报告，在同一视图中比较它们的研究主题、综述结论、研究空白、核验支持率与阶段轨迹差异。
            </p>
            <div className="mt-5 flex flex-wrap gap-3 text-xs" style={{ color: "#64748b" }}>
              <MetaTag label="选中数量" value={String(compareSelection.length)} />
              <MetaTag
                label="加载状态"
                value={isLoading ? "加载中" : errorReports.length ? "部分失败" : "已就绪"}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition"
              style={{
                color: "#273951",
                border: "1px solid #e3e8ee",
                borderRadius: "9999px",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#f6f9fc";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
              }}
            >
              <ArrowLeft className="h-4 w-4" />
              返回工作台
            </Link>
            <button
              type="button"
              onClick={clearCompareSelection}
              className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition"
              style={{
                color: "#273951",
                background: "#f6f9fc",
                border: "1px solid #e3e8ee",
                borderRadius: "9999px",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#edf1f7";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#f6f9fc";
              }}
            >
              <RefreshCw className="h-4 w-4" />
              清空选择
            </button>
          </div>
        </div>
      </section>

      {errorReports.length ? (
        <section
          className="rounded-2xl px-5 py-4 text-sm"
          style={{
            background: "#fff5f7",
            border: "1px solid #e3e8ee",
            borderLeft: "3px solid #ea2261",
          }}
        >
          <p className="font-medium" style={{ color: "#0d253d" }}>
            部分历史报告读取失败
          </p>
          <ul className="mt-2 space-y-1 text-xs leading-5" style={{ color: "#64748b" }}>
            {errorReports.map((item) => (
              <li key={item.reportId}>
                {item.reportId}：{item.errorMessage}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {isLoading && !loadedReports.length ? (
        <section
          className="rounded-[28px] px-6 py-10"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          <div className="flex items-center gap-3" style={{ color: "#273951" }}>
            <LoaderCircle className="h-5 w-5 animate-spin" />
            <span>正在并发载入选中的历史报告</span>
          </div>
        </section>
      ) : null}

      {loadedReports.length ? (
        <CompareMatrix reports={loadedReports.map((item) => item.report!)} />
      ) : null}
    </div>
  );
}

function CompareMatrix({ reports }: { reports: ResearchReport[] }) {
  return (
    <section className="space-y-6">
      <SectionCard
        icon={<GitCompareArrows className="h-4 w-4" />}
        title="核心指标对比"
        description="一眼看到不同报告在论文数、阶段数、支持率、研究空白和审查结论上的差异。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {reports.map((report) => (
            <article
              key={report.request.topic + report.research_note.length}
              className="p-5"
              style={{
                background: "#ffffff",
                border: "1px solid #e3e8ee",
                borderRadius: "12px",
              }}
            >
              <p
                style={{
                  color: "#64748b",
                  fontSize: "11px",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.2em",
                }}
              >
                Topic
              </p>
              <h3 className="mt-2 text-base font-semibold" style={{ color: "#0d253d" }}>
                {report.request.topic}
              </h3>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <Metric label="论文数" value={String(report.papers.length)} />
                <Metric
                  label="阶段数"
                  value={String(report.stage_history.length)}
                />
                <Metric
                  label="支持率"
                  value={`${Math.round(report.citation_verification.overall_score * 100)}%`}
                />
                <Metric
                  label="未支持结论"
                  value={String(report.citation_verification.unsupported_count)}
                />
                <Metric
                  label="待补研究空白"
                  value={String(report.gap_report.missing_aspects.length)}
                />
                <Metric
                  label="审查结论"
                  value={formatVerdictLabel(report.review_report.verdict)}
                />
              </div>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="结构化综述差异"
        description="对比每份报告对该方向的总体判断，便于快速看出立场和重点的演进。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {reports.map((report, index) => (
            <article
              key={`overview-${index}`}
              className="p-5"
              style={{
                background: "#ffffff",
                border: "1px solid #e3e8ee",
                borderRadius: "12px",
              }}
            >
              <p
                style={{
                  color: "#64748b",
                  fontSize: "11px",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.2em",
                }}
              >
                Overview · {index + 1}
              </p>
              <p className="mt-3 text-sm leading-7" style={{ color: "#273951" }}>
                {report.comparison.overview || "当前报告暂未提供综述总览。"}
              </p>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="研究空白对比"
        description="按报告并列展示当前仍未覆盖的研究问题，找出共同空白与独有空白。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {reports.map((report, index) => (
            <article
              key={`gap-${index}`}
              className="p-5"
              style={{
                background: "#ffffff",
                border: "1px solid #e3e8ee",
                borderRadius: "12px",
              }}
            >
              <p
                style={{
                  color: "#64748b",
                  fontSize: "11px",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.2em",
                }}
              >
                Gap · {index + 1}
              </p>
              {report.gap_report.missing_aspects.length ? (
                <ul className="mt-3 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
                  {report.gap_report.missing_aspects.map((aspect, idx) => (
                    <li
                      key={idx}
                      className="px-3 py-2"
                      style={{
                        background: "#f6f9fc",
                        border: "1px solid #e3e8ee",
                        borderRadius: "12px",
                      }}
                    >
                      {aspect}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm leading-6" style={{ color: "#64748b" }}>
                  当前报告未列出待补研究空白。
                </p>
              )}
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="审查与建议对比"
        description="对照每份报告的审查结论、风险与修订建议，便于沉淀稳定的研究判断。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {reports.map((report, index) => (
            <article
              key={`review-${index}`}
              className="p-5"
              style={{
                background: "#ffffff",
                border: "1px solid #e3e8ee",
                borderRadius: "12px",
              }}
            >
              <p
                style={{
                  color: "#64748b",
                  fontSize: "11px",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.2em",
                }}
              >
                Review · {index + 1}
              </p>
              <p className="mt-2 text-sm font-semibold" style={{ color: "#0d253d" }}>
                {formatVerdictLabel(report.review_report.verdict)}
              </p>
              <ListBlock label="主要风险" items={report.review_report.risks} />
              <ListBlock label="修订建议" items={report.review_report.revision_advice} />
            </article>
          ))}
        </div>
      </SectionCard>
    </section>
  );
}

function SectionCard({
  icon,
  title,
  description,
  children,
}: {
  icon?: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="p-6"
      style={{
        background: "#ffffff",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
      }}
    >
      <div className="flex items-start gap-3">
        {icon ? (
          <div
            className="rounded-2xl p-3"
            style={{ background: "#f6f9fc", color: "#533afd" }}
          >
            {icon}
          </div>
        ) : null}
        <div>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300 }}>
            {title}
          </h3>
          <p className="mt-2 text-sm leading-6" style={{ color: "#64748b" }}>
            {description}
          </p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="px-3 py-2"
      style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px" }}
    >
      <p
        style={{
          color: "#64748b",
          fontSize: "11px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.2em",
        }}
      >
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold" style={{ color: "#0d253d" }}>
        {value}
      </p>
    </div>
  );
}

function ListBlock({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="mt-4">
      <p
        style={{
          color: "#64748b",
          fontSize: "11px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.2em",
        }}
      >
        {label}
      </p>
      {items.length ? (
        <ul className="mt-2 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
          {items.map((entry, index) => (
            <li
              key={index}
              className="px-3 py-2"
              style={{
                background: "#f6f9fc",
                border: "1px solid #e3e8ee",
                borderRadius: "12px",
              }}
            >
              {entry}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm leading-6" style={{ color: "#64748b" }}>
          暂未列出。
        </p>
      )}
    </div>
  );
}

function MetaTag({ label, value }: { label: string; value: string }) {
  return (
    <span
      className="px-3 py-1"
      style={{
        color: "#273951",
        background: "#f6f9fc",
        border: "1px solid #e3e8ee",
        borderRadius: "9999px",
        fontSize: "12px",
      }}
    >
      {label}：{value}
    </span>
  );
}

function formatVerdictLabel(verdict: string) {
  switch (verdict) {
    case "overall_pass":
      return "可直接使用";
    case "revise":
      return "建议修订";
    case "blocked":
      return "暂不通过";
    default:
      return verdict || "未标注";
  }
}
