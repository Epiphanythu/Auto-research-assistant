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
        <CoreMetricsTable reports={reports} />
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
              {report.comparison.gaps.length ? (
                <ul className="mt-3 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
                  {report.comparison.gaps.map((aspect, idx) => (
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

      <FactCheckDiffSection reports={reports} />
    </section>
  );
}

// CoreMetricsTable 渲染核心指标对比表格，使用 sticky 表头与 sticky 首列以便横向滚动时仍可读
function CoreMetricsTable({ reports }: { reports: ResearchReport[] }) {
  // 1. 行定义：标签 + 按报告抽取数值的方法，集中维护以便后续追加指标
  const rows: Array<{ label: string; render: (report: ResearchReport) => string }> = [
    { label: "Topic", render: (r) => r.request.topic },
    { label: "论文数", render: (r) => String(r.papers.length) },
    { label: "阶段数", render: (r) => String(r.stage_history.length) },
    {
      label: "可靠性",
      render: (r) =>
        r.synthesis_reliability ? `${Math.round(r.synthesis_reliability.overall_score * 100)}%` : "-",
    },
    {
      label: "弱/孤立结论",
      render: (r) =>
        String((r.synthesis_reliability?.weak_count ?? 0) + (r.synthesis_reliability?.isolated_count ?? 0)),
    },
    { label: "待补研究空白", render: (r) => String(r.comparison.gaps.length) },
    { label: "审查结论", render: (r) => formatVerdictLabel(r.review_report.verdict) },
  ];

  // 2. 共享单元格样式：在内联样式上保留 background:#ffffff，便于 sticky 列遮挡下层内容
  const labelCellStyle: React.CSSProperties = {
    position: "sticky",
    left: 0,
    background: "#ffffff",
    zIndex: 1,
    color: "#0d253d",
    fontSize: "13px",
    fontWeight: 600,
    padding: "10px 14px",
    borderBottom: "1px solid #e3e8ee",
    borderRight: "1px solid #e3e8ee",
    minWidth: "140px",
    textAlign: "left",
  };
  const headerCellStyle: React.CSSProperties = {
    position: "sticky",
    top: 0,
    background: "#f6f9fc",
    zIndex: 2,
    color: "#64748b",
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.2em",
    padding: "10px 14px",
    borderBottom: "1px solid #e3e8ee",
    textAlign: "left",
    minWidth: "180px",
  };
  // 首列 + 表头交叉处需要更高的 z-index，避免被普通表头遮挡
  const cornerCellStyle: React.CSSProperties = {
    ...headerCellStyle,
    ...labelCellStyle,
    background: "#f6f9fc",
    zIndex: 3,
  };
  const dataCellStyle: React.CSSProperties = {
    color: "#273951",
    fontSize: "13px",
    padding: "10px 14px",
    borderBottom: "1px solid #e3e8ee",
    background: "#ffffff",
  };

  return (
    <div
      style={{
        overflow: "auto",
        maxHeight: "70vh",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        background: "#ffffff",
      }}
    >
      <table style={{ borderCollapse: "separate", borderSpacing: 0, width: "100%" }}>
        <thead>
          <tr>
            <th style={cornerCellStyle}>指标</th>
            {reports.map((report, idx) => (
              <th key={`head-${idx}`} style={headerCellStyle}>
                Report {idx + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row" style={labelCellStyle}>
                {row.label}
              </th>
              {reports.map((report, idx) => (
                <td key={`${row.label}-${idx}`} style={dataCellStyle}>
                  {row.render(report)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// FactCheckDiffSection 计算 fact_check_report.flagged_claims 的交集 / 差集，便于看出共同高风险论断。
function FactCheckDiffSection({ reports }: { reports: ResearchReport[] }) {
  // 1. 收集每份报告的 flagged_claims（去重）
  const flaggedSets = reports.map((report) => {
    const items = report.fact_check_report?.flagged_claims ?? [];
    return new Set(items);
  });
  const hasAnyFactCheck = reports.some((report) => report.fact_check_report);
  if (!hasAnyFactCheck) {
    return null;
  }

  // 2. 计算共同高风险（所有报告交集）
  const intersection = flaggedSets.reduce<Set<string>>((acc, current, idx) => {
    if (idx === 0) {
      return new Set(current);
    }
    return new Set([...acc].filter((item) => current.has(item)));
  }, new Set<string>());

  // 3. 每份报告的独有高风险（差集）
  const exclusives = flaggedSets.map((current, idx) => {
    const others = flaggedSets.filter((_, otherIdx) => otherIdx !== idx);
    return [...current].filter((item) => !others.some((set) => set.has(item)));
  });

  return (
    <SectionCard
      title="论断校验差异"
      description="把 fact-check 报告中标红的『暂未支撑』论断按交集 / 差集对比，定位共同薄弱点和差异。"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <article
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
            共同高风险论断
          </p>
          {intersection.size ? (
            <ul className="mt-3 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
              {[...intersection].map((claim, idx) => (
                <li
                  key={idx}
                  className="px-3 py-2"
                  style={{
                    background: "#fff5f7",
                    border: "1px solid #f7c8d3",
                    borderRadius: "12px",
                  }}
                >
                  {claim}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm leading-6" style={{ color: "#64748b" }}>
              所选报告暂无共同的高风险论断。
            </p>
          )}
        </article>
        <article
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
            支撑率与 NLI 复核
          </p>
          <ul className="mt-3 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
            {reports.map((report, idx) => {
              const factCheck = report.fact_check_report;
              if (!factCheck) {
                return (
                  <li key={idx} className="px-3 py-2"
                    style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px" }}>
                    报告 {idx + 1}：未生成 fact-check 报告
                  </li>
                );
              }
              const supportRate = Math.round(factCheck.overall_score * 100);
              return (
                <li key={idx} className="px-3 py-2"
                  style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px" }}>
                  <span style={{ color: "#0d253d", fontWeight: 600 }}>报告 {idx + 1}</span>
                  ：支撑率 {supportRate}%，论断 {factCheck.total_claims} 条，
                  暂未支撑 {factCheck.unsupported_count} 条
                  {factCheck.nli_verified_count !== undefined ? `，NLI 复核 ${factCheck.nli_verified_count} 条` : ""}
                </li>
              );
            })}
          </ul>
        </article>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {reports.map((report, idx) => (
          <article
            key={`exclusive-${idx}`}
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
              报告 {idx + 1} · 独有高风险
            </p>
            {exclusives[idx].length ? (
              <ul className="mt-3 space-y-2 text-sm leading-6" style={{ color: "#273951" }}>
                {exclusives[idx].map((claim, cIdx) => (
                  <li
                    key={cIdx}
                    className="px-3 py-2"
                    style={{
                      background: "#f6f9fc",
                      border: "1px solid #e3e8ee",
                      borderRadius: "12px",
                    }}
                  >
                    {claim}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm leading-6" style={{ color: "#64748b" }}>
                与其它报告高度一致，暂无独有的高风险论断。
              </p>
            )}
          </article>
        ))}
      </div>
    </SectionCard>
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
