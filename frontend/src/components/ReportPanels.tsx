import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Lightbulb, MessageSquare, Quote, ScanSearch, SearchCode, ShieldCheck } from "lucide-react";
import DOMPurify from "dompurify";
import { marked } from "marked";

import type { ClaimFactCheck, ComparisonSummary, Contradiction, DebateRound, FactCheckReport, Paper, PaperInsight, ReviewReport, StageTransition, SynthesisReliability, UnitSynthesis } from "@/types/research";

// sanitizeMarkdownHTML 清洗 marked 渲染结果，避免报告内容中的脚本、事件属性和危险链接协议执行。
function sanitizeMarkdownHTML(raw: string): string {
  // 1. DOMPurify 负责解析 HTML 语义，比正则清洗更不容易漏掉 SVG、未引号属性等边界场景。
  return DOMPurify.sanitize(raw, {
    USE_PROFILES: { html: true },
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
  });
}

export function OverviewPanel({
  overview,
  trends,
  gaps,
  ideas,
  researchNote,
  nextActions,
}: {
  overview: string;
  trends: string[];
  gaps: string[];
  ideas: ComparisonSummary["ideas"];
  researchNote: string;
  nextActions: string[];
}) {
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
        <ResearchNoteView researchNote={researchNote} />

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

// ResearchNoteView 提供 Markdown 渲染 / 原文双 Tab，默认渲染 marked 解析后的 HTML
function ResearchNoteView({ researchNote }: { researchNote: string }) {
  // 1. 本地 Tab 状态：渲染（默认）/ 原文
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");
  // 2. 解析 Markdown 并清洗 <script> 等危险节点；marked.parse 在同步模式下返回 string
  const html = useMemo(() => {
    const parsed = marked.parse(researchNote ?? "", { async: false }) as string;
    return sanitizeMarkdownHTML(parsed);
  }, [researchNote]);

  return (
    <div style={{ marginTop: "16px" }}>
      {/* 1. Tab 切换栏 */}
      <div className="flex items-center gap-2" style={{ marginBottom: "12px" }}>
        <TabButton active={mode === "rendered"} onClick={() => setMode("rendered")} label="渲染" />
        <TabButton active={mode === "raw"} onClick={() => setMode("raw")} label="原文" />
      </div>
      {/* 2. 渲染模式：注入清洗后的 HTML，prose 样式仅作基础排版 */}
      {mode === "rendered" ? (
        <div
          className="prose prose-sm max-w-none"
          style={{ color: "#273951", fontSize: "14px", lineHeight: 1.75 }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre
          style={{
            color: "#64748b",
            fontSize: "13px",
            lineHeight: 1.7,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            background: "#f6f9fc",
            border: "1px solid #e3e8ee",
            borderRadius: "12px",
            padding: "12px 16px",
            margin: 0,
            fontFamily: "inherit",
          }}
        >
          {researchNote}
        </pre>
      )}
    </div>
  );
}

function TabButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "4px 12px",
        borderRadius: "9999px",
        fontSize: "12px",
        fontWeight: 500,
        border: "1px solid",
        cursor: "pointer",
        background: active ? "#533afd" : "#ffffff",
        color: active ? "#ffffff" : "#64748b",
        borderColor: active ? "#533afd" : "#e3e8ee",
        transition: "all 0.15s ease",
      }}
    >
      {label}
    </button>
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
            {insight.evidence.length > 0 && (
              <div className="mt-4" style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "12px 14px" }}>
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>
                  证据片段
                </p>
                <ul className="mt-2 space-y-2">
                  {insight.evidence.slice(0, 2).map((item, index) => (
                    <li key={`${insight.paper.paper_id}-evidence-${index}`} style={{ color: "#273951", fontSize: "12px", lineHeight: 1.65 }}>
                      <span style={{ color: "#533afd", fontWeight: 600 }}>
                        {item.section_kind || item.source || "evidence"}
                      </span>
                      ：{item.snippet}
                      {item.reason ? (
                        <span style={{ color: "#64748b" }}>（{item.reason}）</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )}
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
  comparison,
}: {
  comparison: ComparisonSummary;
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
            ...(comparison.need_follow_up
              ? { background: "#fef3cd", color: "#92400e", border: "1px solid #fde68a" }
              : { background: "#d1fae5", color: "#065f46", border: "1px solid #a7f3d0" }),
          }}
        >
          {comparison.need_follow_up ? "建议继续补充" : "当前结果可用"}
        </span>
      </div>

      <div style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px", marginTop: "20px" }}>
        <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.24em" }}>
          判断说明
        </p>
        <p style={{ color: "#64748b", fontSize: "14px", lineHeight: 1.75, marginTop: "12px" }}>
          {comparison.gap_reasoning || "暂未提供补充说明。"}
        </p>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <CardList
          title="待补充问题"
          icon={<Quote className="h-4 w-4" />}
          items={comparison.gaps}
          emptyText="当前未记录明显空白"
        />
        <CardList
          title="建议检索方向"
          icon={<SearchCode className="h-4 w-4" />}
          items={comparison.follow_up_queries}
          emptyText="当前无需追加检索"
        />
      </div>
    </section>
  );
}

export function DebateLogPanel({ rounds }: { rounds: DebateRound[] }) {
  if (!rounds || rounds.length === 0) return null;
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <MessageSquare className="h-5 w-5" style={{ color: "#533afd" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Multi-Agent Debate
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>Critic-Writer 辩论记录</h3>
        </div>
      </div>
      <div className="mt-6 space-y-4">
        {rounds.map((round) => (
          <article key={round.round_number} style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "20px" }}>
            <div className="flex items-center justify-between gap-4">
              <h4 style={{ color: "#0d253d", fontSize: "16px", fontWeight: 600 }}>
                第 {round.round_number} 轮
              </h4>
              <div className="flex items-center gap-3">
                <span style={{ background: "#f6f9fc", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px" }}>
                  质量分 {round.critic_quality_score}/10
                </span>
                <span
                  style={{
                    borderRadius: "9999px",
                    padding: "2px 12px",
                    fontSize: "12px",
                    ...(round.passed
                      ? { background: "#d1fae5", color: "#065f46", border: "1px solid #a7f3d0" }
                      : { background: "#fef3cd", color: "#92400e", border: "1px solid #fde68a" }),
                  }}
                >
                  {round.passed ? "质量达标" : "需要修订"}
                </span>
              </div>
            </div>
            {round.critic_weaknesses.length > 0 && (
              <div className="mt-4 space-y-2">
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>
                  Critic 发现的弱点
                </p>
                {round.critic_weaknesses.map((w, i) => (
                  <div key={i} style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "12px 16px" }}>
                    <div className="flex items-start gap-2">
                      <span
                        style={{
                          borderRadius: "9999px",
                          padding: "1px 8px",
                          fontSize: "11px",
                          flexShrink: 0,
                          ...(w.severity === "high"
                            ? { background: "#fee2e2", color: "#991b1b" }
                            : w.severity === "medium"
                            ? { background: "#fef3cd", color: "#92400e" }
                            : { background: "#f6f9fc", color: "#64748b" }),
                        }}
                      >
                        {w.severity}
                      </span>
                      <div>
                        <p style={{ color: "#273951", fontSize: "14px" }}>{w.point}</p>
                        {w.suggestion && (
                          <p style={{ color: "#533afd", fontSize: "13px", marginTop: "6px" }}>建议：{w.suggestion}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {round.revision_summary && (
              <div className="mt-4" style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "12px 16px" }}>
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>
                  Writer 修订说明
                </p>
                <p style={{ color: "#273951", fontSize: "14px", marginTop: "6px" }}>{round.revision_summary}</p>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

export function ReliabilityPanel({ reliability }: { reliability: SynthesisReliability }) {
  if (!reliability) return null;
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <ShieldCheck className="h-5 w-5" style={{ color: "#533afd" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Evidence Reliability
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>证据可靠性评估</h3>
        </div>
      </div>
      <div className="mt-6 grid gap-3 md:grid-cols-4">
        <MiniMetric label="总体评分" value={`${Math.round(reliability.overall_score * 100)}%`} />
        <MiniMetric label="强证据" value={reliability.strong_count} />
        <MiniMetric label="中等证据" value={reliability.moderate_count} />
        <MiniMetric label="弱/孤立" value={reliability.weak_count + reliability.isolated_count} />
      </div>
      {reliability.claims.length > 0 && (
        <div className="mt-5 space-y-3">
          {reliability.claims.map((c, i) => (
            <article key={i} style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px" }}>
              <div className="flex items-start justify-between gap-3">
                <h4 style={{ color: "#0d253d", fontSize: "14px", fontWeight: 600, flex: 1 }}>{c.claim}</h4>
                <span
                  style={{
                    borderRadius: "9999px",
                    padding: "2px 12px",
                    fontSize: "12px",
                    flexShrink: 0,
                    ...(c.reliability_level === "strong"
                      ? { background: "#d1fae5", color: "#065f46" }
                      : c.reliability_level === "moderate"
                      ? { background: "#dbeafe", color: "#1e40af" }
                      : c.reliability_level === "weak"
                      ? { background: "#fef3cd", color: "#92400e" }
                      : { background: "#f6f9fc", color: "#64748b" }),
                  }}
                >
                  {c.reliability_level}
                </span>
              </div>
              <p style={{ color: "#64748b", fontSize: "14px", marginTop: "8px" }}>{c.reasoning}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {c.quality_signals.map((s, j) => (
                  <span key={j} style={{ background: "#ffffff", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "1px 10px", fontSize: "11px" }}>
                    {s}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
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
    case "unit_synthesis":
      return "分小节综合";
    case "gap_detect":
      return "空白检查";
    case "claim_table":
      return "结论映射";
    case "write":
      return "综述撰写";
    case "debate":
      return "多轮辩论";
    case "reliability":
      return "可靠性评估";
    case "verify":
      return "结论核验";
    case "review":
      return "结果审查";
    case "fact_check":
      return "论断校验";
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

// ─── Phase 2: 按 ResearchUnit 小节展示 ───

export function UnitSynthesisPanel({ syntheses, papers = [] }: { syntheses: UnitSynthesis[]; papers?: Paper[] }) {
  if (!syntheses || syntheses.length === 0) return null;
  // 1. 构建 paper_id → 标题映射，避免前端只显示晦涩的 OpenAlex/arXiv ID
  const paperTitleMap = new Map<string, string>();
  for (const p of papers) {
    if (p && p.paper_id) {
      paperTitleMap.set(p.paper_id, p.title || p.paper_id);
    }
  }
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <FileText className="h-5 w-5" style={{ color: "#533afd" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Per-question Synthesis
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>按研究问题分小节</h3>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {syntheses.map((unit) => (
          <article
            key={unit.unit_id}
            style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "20px" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>
                  {unit.unit_id}
                </p>
                <h4 style={{ color: "#0d253d", fontSize: "16px", fontWeight: 600, marginTop: "6px" }}>{unit.question}</h4>
              </div>
              <span style={{ background: "#ffffff", color: "#533afd", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "2px 12px", fontSize: "12px", flexShrink: 0 }}>
                置信度 {Math.round(unit.confidence * 100)}%
              </span>
            </div>

            {unit.summary && (
              <p style={{ color: "#273951", fontSize: "14px", lineHeight: 1.75, marginTop: "12px" }}>{unit.summary}</p>
            )}

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <UnitSubList title="核心方法" items={unit.key_methods} />
              <UnitSubList title="一致性结论" items={unit.consensus} />
              <UnitSubList title="分歧或矛盾" items={unit.disagreements} />
              <UnitSubList title="开放问题" items={unit.open_questions} />
            </div>

            {unit.supporting_paper_ids.length > 0 && (
              <div className="mt-4">
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>
                  引用论文
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {unit.supporting_paper_ids.map((pid) => {
                    const title = paperTitleMap.get(pid);
                    return (
                      <span
                        key={pid}
                        title={pid}
                        style={{ background: "#ffffff", color: "#273951", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "1px 10px", fontSize: "11px", maxWidth: "420px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                      >
                        {title ?? pid}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function UnitSubList({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "12px 16px" }}>
      <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.22em" }}>{title}</p>
      <ul className="mt-2 space-y-1">
        {items.map((item, idx) => (
          <li key={`${title}-${idx}`} style={{ color: "#273951", fontSize: "13px", lineHeight: 1.65 }}>
            · {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Phase 3: 论断校验展示 ───

export function FactCheckPanel({ report }: { report: FactCheckReport | null }) {
  if (!report || report.total_claims === 0) return null;
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <ScanSearch className="h-5 w-5" style={{ color: "#533afd" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Claim Fact Check
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>论断证据校验</h3>
        </div>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-4">
        <MiniMetric label="整体支撑率" value={`${Math.round(report.overall_score * 100)}%`} />
        <MiniMetric label="有支撑" value={report.supported_count} />
        <MiniMetric label="弱支撑" value={report.weak_count} />
        <MiniMetric label="无证据" value={report.unsupported_count} />
      </div>

      <div className="mt-5 space-y-3">
        {report.items.map((item, idx) => (
          <FactCheckItemCard key={`fc-${idx}`} item={item} />
        ))}
      </div>
    </section>
  );
}

export function ContradictionPanel({ contradictions }: { contradictions: Contradiction[] }) {
  // 1. 没有矛盾时不渲染该面板，避免空白噪音
  if (!contradictions || contradictions.length === 0) return null;
  return (
    <section style={{ background: "#ffffff", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "24px" }}>
      <div className="flex items-center gap-3">
        <div style={{ background: "#fff5f5", borderRadius: "12px", padding: "12px" }}>
          <AlertTriangle className="h-5 w-5" style={{ color: "#dc2626" }} />
        </div>
        <div>
          <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.2em" }}>
            Cross-Paper Contradictions
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>
            跨论文矛盾（{contradictions.length}）
          </h3>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {contradictions.map((item, idx) => (
          <article
            key={`contra-${idx}`}
            style={{ background: "#fff5f5", border: "1px solid #fecaca", borderRadius: "12px", padding: "16px" }}
          >
            <p style={{ color: "#0d253d", fontSize: "14px", fontWeight: 600 }}>
              {item.topic || `矛盾 ${idx + 1}`}
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, marginBottom: "4px" }}>
                  论断 A · {item.paper_id_a}
                </p>
                <p style={{ color: "#0d253d", fontSize: "13px", lineHeight: 1.6 }}>{item.claim_a}</p>
              </div>
              <div>
                <p style={{ color: "#64748b", fontSize: "11px", fontWeight: 600, marginBottom: "4px" }}>
                  论断 B · {item.paper_id_b}
                </p>
                <p style={{ color: "#0d253d", fontSize: "13px", lineHeight: 1.6 }}>{item.claim_b}</p>
              </div>
            </div>
            {item.rationale && (
              <p style={{ color: "#7f1d1d", fontSize: "12px", marginTop: "10px", lineHeight: 1.6 }}>
                ⚠ {item.rationale}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function FactCheckItemCard({ item }: { item: ClaimFactCheck }) {
  return (
    <article style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", borderRadius: "12px", padding: "16px" }}>
      <div className="flex items-start justify-between gap-3">
        <p style={{ color: "#0d253d", fontSize: "14px", lineHeight: 1.65, flex: 1 }}>{item.claim}</p>
        <span
          style={{
            borderRadius: "9999px",
            padding: "2px 12px",
            fontSize: "12px",
            flexShrink: 0,
            ...formatSupportLevelStyle(item.support_level),
          }}
        >
          {formatSupportLevelLabel(item.support_level)}
        </span>
      </div>
      <p style={{ color: "#64748b", fontSize: "12px", marginTop: "8px" }}>
        {item.reason}（重叠分 {item.keyword_overlap_score.toFixed(2)}）
      </p>
      {item.matched_paper_ids.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {item.matched_paper_ids.map((pid) => (
            <span key={pid} style={{ background: "#ffffff", color: "#273951", border: "1px solid #e3e8ee", borderRadius: "9999px", padding: "1px 10px", fontSize: "11px", fontFamily: "monospace" }}>
              {pid}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function formatSupportLevelLabel(level: string) {
  switch (level) {
    case "strong":
      return "强支撑";
    case "moderate":
      return "中等支撑";
    case "weak":
      return "弱支撑";
    case "unsupported":
      return "无证据";
    default:
      return level || "未标注";
  }
}

function formatSupportLevelStyle(level: string): React.CSSProperties {
  switch (level) {
    case "strong":
      return { background: "#d1fae5", color: "#065f46", border: "1px solid #a7f3d0" };
    case "moderate":
      return { background: "#dbeafe", color: "#1e40af", border: "1px solid #bfdbfe" };
    case "weak":
      return { background: "#fef3cd", color: "#92400e", border: "1px solid #fde68a" };
    case "unsupported":
      return { background: "#fee2e2", color: "#991b1b", border: "1px solid #fca5a5" };
    default:
      return { background: "#f6f9fc", color: "#64748b", border: "1px solid #e3e8ee" };
  }
}
