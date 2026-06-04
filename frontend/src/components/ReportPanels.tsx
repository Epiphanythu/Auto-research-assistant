import { AlertTriangle, CheckCircle2, FileText, Lightbulb, Quote, SearchCode, ShieldCheck } from "lucide-react";

import type { ClaimEvidenceRow, CitationVerificationReport, ComparisonSummary, GapReport, PaperInsight, ReviewReport, StageTransition } from "@/types/research";

export function OverviewPanel({
  overview,
  trends,
  gaps,
  ideas,
  researchNote,
  nextActions,
}: ComparisonSummary & { researchNote: string; nextActions: string[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
      <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
        <div className="flex items-center gap-3">
          <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
            <SearchCode className="h-5 w-5" style={{ color: "#533afd" }} />
          </div>
          <div>
            <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
              Review Overview
            </p>
            <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>结构化综述</h3>
          </div>
        </div>
        <p style={{ color: "#64748b", fontSize: "14px", lineHeight: 1.75, marginTop: "20px" }}>{overview}</p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <CardList title="趋势" icon={<CheckCircle2 className="h-4 w-4" />} items={trends} />
          <CardList title="研究空白" icon={<Quote className="h-4 w-4" />} items={gaps} />
        </div>
      </section>

      <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
        <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
          Research Note
        </p>
        <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "8px" }}>研究笔记</h3>
        <p style={{ color: "#64748b", fontSize: "14px", lineHeight: 1.75, marginTop: "16px" }}>{researchNote}</p>

        <div className="mt-6">
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            后续事项
          </p>
          <ul style={{ marginTop: "12px" }} className="space-y-2">
            {nextActions.map((action) => (
              <li key={action} style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "12px 16px", color: "#64748b", fontSize: "14px" }}>
                {action}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-6">
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            创新建议
          </p>
          <div className="mt-3 space-y-3">
            {ideas.map((idea) => (
              <article
                key={idea.title}
                style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "16px" }}
              >
                <div className="flex items-center gap-2" style={{ color: "#0d253d" }}>
                  <Lightbulb className="h-4 w-4" />
                  <h4 style={{ fontSize: "14px", fontWeight: 600 }}>{idea.title}</h4>
                </div>
                <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>{idea.rationale}</p>
                <p style={{ color: "#64748b", fontSize: "12px", marginTop: "8px" }}>实施注意：{idea.risk}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

export function InsightList({ insights }: { insights: PaperInsight[] }) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <FileText className="h-5 w-5" style={{ color: "#533afd" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Paper Summary
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>论文洞察</h3>
        </div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        {insights.map((insight) => (
          <article
            key={insight.paper.paper_id}
            style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "20px" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 style={{ color: "#0d253d", fontSize: "18px", fontWeight: 600 }}>{insight.paper.title}</h4>
                <p style={{ color: "#64748b", fontSize: "12px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.24em", marginTop: "8px" }}>
                  {formatSourceLabel(insight.paper.source)} · {insight.paper.published || "日期未知"}
                </p>
              </div>
              <span style={{ background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px" }}>
                参考度 {Math.round(insight.confidence * 100)}%
              </span>
            </div>
            <dl className="mt-5 grid gap-3">
              <InfoRow label="问题" value={insight.problem} />
              <InfoRow label="方法" value={insight.method} />
              <InfoRow label="创新" value={insight.innovation} />
              <InfoRow label="发现" value={insight.findings} />
              <InfoRow label="局限" value={insight.limitation} />
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

export function ReviewDecisionPanel({
  reviewReport,
}: {
  reviewReport: ReviewReport;
}) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
            <ShieldCheck className="h-5 w-5" style={{ color: "#533afd" }} />
          </div>
          <div>
            <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
              Review Decision
            </p>
            <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>结果审查</h3>
          </div>
        </div>
        <span
          style={{
            borderRadius: "9999px",
            padding: "2px 12px",
            fontSize: "12px",
            ...formatVerdictStyle(reviewReport.verdict),
          }}
        >
          {formatVerdictLabel(reviewReport.verdict)}
        </span>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <CardList
          title="当前优势"
          icon={<CheckCircle2 className="h-4 w-4" />}
          items={reviewReport.strengths}
          emptyText="暂未提供优势摘要"
        />
        <CardList
          title="主要风险"
          icon={<AlertTriangle className="h-4 w-4" />}
          items={reviewReport.risks}
          emptyText="暂未识别主要风险"
        />
        <CardList
          title="修订建议"
          icon={<Quote className="h-4 w-4" />}
          items={reviewReport.revision_advice}
          emptyText="暂未提供修订建议"
        />
      </div>
    </section>
  );
}

export function GapReportPanel({
  gapReport,
}: {
  gapReport: GapReport;
}) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
            <AlertTriangle className="h-5 w-5" style={{ color: "#533afd" }} />
          </div>
          <div>
            <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
              Research Gap
            </p>
            <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>研究空白与补充方向</h3>
          </div>
        </div>
        <span
          style={{
            borderRadius: "9999px",
            padding: "2px 12px",
            fontSize: "12px",
            ...(gapReport.need_follow_up
              ? { background: "#fef3cd", color: "#92400e", border: "1px solid #fde68a" }
              : { background: "#d1fae5", color: "#065f46", border: "1px solid #a7f3d0" }),
          }}
        >
          {gapReport.need_follow_up ? "建议继续补充" : "当前结果可用"}
        </span>
      </div>

      <div style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px", marginTop: "20px" }}>
        <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.24em" }}>
          判断说明
        </p>
        <p style={{ color: "#64748b", fontSize: "14px", lineHeight: 1.75, marginTop: "12px" }}>
          {gapReport.reasoning || "暂未提供补充说明。"}
        </p>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <CardList
          title="待补充问题"
          icon={<Quote className="h-4 w-4" />}
          items={gapReport.missing_aspects}
          emptyText="当前未记录明显空白"
        />
        <CardList
          title="建议检索方向"
          icon={<SearchCode className="h-4 w-4" />}
          items={gapReport.follow_up_queries}
          emptyText="当前无需追加检索"
        />
      </div>
    </section>
  );
}

export function ClaimTablePanel({ rows }: { rows: ClaimEvidenceRow[] }) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
        Claim Map
      </p>
      <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "8px" }}>结论证据映射</h3>
      <div className="mt-5 space-y-4">
        {rows.map((row) => (
          <article key={row.claim} style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "20px" }}>
            <div className="flex items-start justify-between gap-4">
              <h4 style={{ color: "#0d253d", fontSize: "16px", fontWeight: 600, maxWidth: "48rem" }}>{row.claim}</h4>
              <span style={{ background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px" }}>
                {formatSupportLevel(row.support_level)}
              </span>
            </div>
            <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>{row.rationale}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {row.supporting_paper_ids.map((paperId) => (
                <span key={paperId} style={{ background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px" }}>
                  {paperId}
                </span>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              {row.evidence.map((evidence, index) => (
                <div key={`${row.claim}-${index}`} style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "12px" }}>
                  <p style={{ color: "#273951", fontSize: "14px" }}>{evidence.snippet}</p>
                  <p style={{ color: "#64748b", fontSize: "12px", marginTop: "8px" }}>
                    {formatSourceLabel(evidence.source)} · {evidence.section || "未标注章节"} · 第 {evidence.page || "-"} 页
                  </p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function CitationPanel({
  report,
}: {
  report: CitationVerificationReport;
}) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
        Verification
      </p>
      <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "8px" }}>研究笔记核验</h3>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <MiniMetric label="总体支持率" value={`${Math.round(report.overall_score * 100)}%`} />
        <MiniMetric label="已支持结论" value={report.supported_count} />
        <MiniMetric label="未支持结论" value={report.unsupported_count} />
      </div>
      <div className="mt-5 space-y-3">
        {report.items.map((item) => (
          <article key={item.claim} style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "16px" }}>
            <div className="flex items-start justify-between gap-3">
              <h4 style={{ color: "#0d253d", fontSize: "14px", fontWeight: 600 }}>{item.claim}</h4>
              <span
                style={{
                  borderRadius: "9999px",
                  padding: "2px 12px",
                  fontSize: "12px",
                  ...(item.supported
                    ? { background: "#d1fae5", color: "#065f46" }
                    : { background: "#fee2e2", color: "#991b1b" }),
                }}
              >
                {formatSupportLevel(item.support_level)}
              </span>
            </div>
            <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>{item.reason}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function StageTimeline({ stages }: { stages: StageTransition[] }) {
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
        Process Record
      </p>
      <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "8px" }}>阶段轨迹</h3>
      <div className="mt-6 space-y-4">
        {stages.map((stage, index) => (
          <div key={`${stage.stage}-${index}`} className="flex gap-4">
            <div className="flex w-16 flex-col items-center">
              <div style={{ height: "12px", width: "12px", borderRadius: "9999px", background: "#533afd" }} />
              {index < stages.length - 1 ? <div style={{ marginTop: "8px", height: "100%", width: "1px", background: "#e3e8ee" }} /> : null}
            </div>
            <article style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px", flex: 1 }}>
              <div className="flex items-center justify-between gap-3">
                <h4 style={{ color: "#0d253d", fontWeight: 500 }}>{formatStageLabel(stage.stage)}</h4>
                <div className="flex items-center gap-2">
                  {stage.duration_ms != null && stage.duration_ms > 0 && (
                    <span style={{ color: "#64748b", fontSize: "11px", fontFamily: "monospace" }}>
                      {stage.duration_ms >= 1000 ? `${(stage.duration_ms / 1000).toFixed(1)}s` : `${stage.duration_ms}ms`}
                    </span>
                  )}
                  <span style={{ background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px" }}>
                    {formatStageStatus(stage.status)}
                  </span>
                </div>
              </div>
              <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>{stage.summary}</p>
            </article>
          </div>
        ))}
      </div>
    </section>
  );
}

function CardList({
  title,
  icon,
  items,
  emptyText = "暂无内容",
}: {
  title: string;
  icon: React.ReactNode;
  items: string[];
  emptyText?: string;
}) {
  return (
    <div style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px" }}>
      <div className="flex items-center gap-2" style={{ color: "#0d253d", fontSize: "14px", fontWeight: 500 }}>
        {icon}
        <span>{title}</span>
      </div>
      {items.length ? (
        <ul style={{ marginTop: "16px" }} className="space-y-2">
          {items.map((item) => (
            <li key={item} style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "12px 16px", color: "#64748b", fontSize: "14px" }}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "12px 16px", color: "#64748b", fontSize: "14px", marginTop: "16px" }}>
          {emptyText}
        </p>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "16px", padding: "12px 16px" }}>
      <dt style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>{label}</dt>
      <dd style={{ color: "#273951", fontSize: "14px", lineHeight: 1.75, marginTop: "8px" }}>{value}</dd>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.24em" }}>{label}</p>
      <p style={{ color: "#0d253d", fontSize: "28px", fontWeight: 600, marginTop: "12px" }}>{value}</p>
    </div>
  );
}

function formatSupportLevel(level: string) {
  switch (level) {
    case "supported":
      return "支持充分";
    case "partial":
      return "支持部分充分";
    case "unsupported":
      return "暂未支持";
    default:
      return level || "未标注";
  }
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

function formatVerdictStyle(verdict: string): React.CSSProperties {
  switch (verdict) {
    case "overall_pass":
      return { background: "#d1fae5", color: "#065f46", border: "1px solid #a7f3d0" };
    case "revise":
      return { background: "#fef3cd", color: "#92400e", border: "1px solid #fde68a" };
    case "blocked":
      return { background: "#fee2e2", color: "#991b1b", border: "1px solid #fca5a5" };
    default:
      return { background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee" };
  }
}

function formatSourceLabel(source: string) {
  switch (source) {
    case "pdf":
      return "正文";
    case "abstract":
      return "摘要";
    case "mock":
      return "示例";
    case "arxiv":
      return "arXiv";
    case "openalex":
      return "OpenAlex";
    default:
      return source || "未知来源";
  }
}

function formatStageLabel(stage: string) {
  switch (stage) {
    case "clarify":
      return "问题澄清";
    case "brief":
      return "研究简报";
    case "plan":
      return "研究规划";
    case "supervise":
      return "任务拆分";
    case "research":
      return "文献研究";
    case "evidence":
      return "证据整理";
    case "compare":
      return "横向比较";
    case "gap_detect":
      return "空白检查";
    case "claim_table":
      return "结论映射";
    case "write":
      return "综述撰写";
    case "verify":
      return "结论核验";
    case "review":
      return "结果审查";
    case "finalize":
      return "最终整理";
    default:
      return stage;
  }
}

function formatStageStatus(status: string) {
  switch (status) {
    case "completed":
      return "已完成";
    case "in_progress":
      return "进行中";
    case "pending":
      return "待处理";
    default:
      return status;
  }
}
