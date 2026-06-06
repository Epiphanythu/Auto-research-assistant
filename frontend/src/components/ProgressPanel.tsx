import { useEffect, useRef, useState } from "react";

import type { LLMCallStats, SSEEvent } from "@/types/research";

type Props = {
  events: SSEEvent[];
  progress: number;
  isConnected: boolean;
  className?: string;
  llmCallStats?: LLMCallStats | null;
};

const STAGE_LABELS: Record<string, string> = {
  init: "Initialization",
  clarify: "Clarifying Research Scope",
  brief: "Building Research Brief",
  plan: "Planning Search Strategy",
  supervise: "Decomposing Research Units",
  research: "Multi-source Paper Search",
  evidence: "Building Evidence Bundles",
  compare: "Cross-paper Comparison",
  gap_detect: "Detecting Research Gaps",
  follow_up: "Follow-up Research",
  claim_table: "Building Claim-Evidence Table",
  write: "Writing Research Note",
  debate: "Critic-Writer Debate",
  reliability: "Evidence Reliability Assessment",
  verify: "Citation Verification",
  review: "Quality Review",
  finalize: "Finalizing",
};

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] || stage;
}

/* ---- tiny inline SVG icons ---- */

function CheckmarkIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="7" cy="7" r="7" fill="#533afd" />
      <path
        d="M4 7.25L6.25 9.5L10 5"
        stroke="#fff"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ArrowIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="7" cy="7" r="7" fill="#665efd" />
      <path
        d="M5 4.5L9 7L5 9.5"
        stroke="#fff"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PaperIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <rect x="2" y="1" width="10" height="12" rx="1.5" fill="#f6f9fc" stroke="#533afd" strokeWidth="1" />
      <line x1="4.5" y1="4.5" x2="9.5" y2="4.5" stroke="#b9b9f9" strokeWidth="0.75" strokeLinecap="round" />
      <line x1="4.5" y1="6.5" x2="9.5" y2="6.5" stroke="#b9b9f9" strokeWidth="0.75" strokeLinecap="round" />
      <line x1="4.5" y1="8.5" x2="7.5" y2="8.5" stroke="#b9b9f9" strokeWidth="0.75" strokeLinecap="round" />
    </svg>
  );
}

/* ---- keyframes injected once ---- */

const pulseStyle = `
@keyframes stripe-pulse {
  0%   { transform: scale(1);   opacity: 0.7; }
  70%  { transform: scale(2.2); opacity: 0; }
  100% { transform: scale(2.2); opacity: 0; }
}
`;

export default function ProgressPanel({
  events,
  progress,
  isConnected,
  className = "",
  llmCallStats = null,
}: Props) {
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  const startTimeRef = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  // Track elapsed time since first event
  useEffect(() => {
    if (events.length > 0 && startTimeRef.current === null) {
      startTimeRef.current = Date.now();
    }
    if (!isConnected || progress >= 1) return;
    const timer = setInterval(() => {
      if (startTimeRef.current) {
        setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [events.length, isConnected, progress]);

  const formatElapsed = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  /* Build an ordered list of unique stages that appeared */
  const seenStages = new Set<string>();
  const timelineStages: Array<{ stage: string; completed: boolean }> = [];
  for (const e of events) {
    if (e.event_type === "stage_complete" && !seenStages.has(e.stage)) {
      seenStages.add(e.stage);
      timelineStages.push({ stage: e.stage, completed: true });
    }
  }
  /* If the latest event is a stage_start that hasn't completed yet */
  if (
    latestEvent &&
    latestEvent.event_type === "stage_start" &&
    !seenStages.has(latestEvent.stage)
  ) {
    timelineStages.push({ stage: latestEvent.stage, completed: false });
  }

  const paperEvents = events.filter((e) => e.event_type === "paper_found");

  // 1. 优先使用外部显式传入的统计；否则尝试从 final_report 事件中读取
  const finalReportEvent = events.find((event) => event.event_type === "final_report");
  const finalStats = (finalReportEvent?.data as { llm_call_stats?: LLMCallStats } | undefined)
    ?.llm_call_stats;
  const stats: LLMCallStats | null = llmCallStats ?? finalStats ?? null;

  return (
    <>
      <style>{pulseStyle}</style>

      <div
        className={`bg-white rounded-xl border border-[#e3e8ee] ${className}`}
        style={{ fontFamily: "'Inter', system-ui, sans-serif" }}
      >
        {/* ---- Header row ---- */}
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2">
              {isConnected && (
                <span className="relative flex h-[7px] w-[7px]">
                  <span
                    className="absolute inset-0 rounded-full bg-emerald-500"
                    style={{ animation: "stripe-pulse 1.5s cubic-bezier(0,0,0.2,1) infinite" }}
                  />
                  <span className="relative inline-flex rounded-full h-[7px] w-[7px] bg-emerald-500" />
                </span>
              )}
              <span
                className="text-[13px] font-normal truncate"
                style={{ color: "#0d253d" }}
              >
                {latestEvent ? stageLabel(latestEvent.stage) : "Preparing…"}
              </span>
            </div>
            <span className="text-xs font-normal tabular-nums" style={{ color: "#64748d" }}>
              {Math.round(progress * 100)}%{elapsed > 0 ? ` · ${formatElapsed(elapsed)}` : ""}
            </span>
          </div>

          {/* ---- Progress bar ---- */}
          <div
            className="h-[6px] rounded-full overflow-hidden"
            style={{ backgroundColor: "#f6f9fc" }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(progress * 100, 0)}%`,
                background: "linear-gradient(90deg, #533afd 0%, #665efd 100%)",
                transition: "width 0.5s cubic-bezier(0.4,0,0.2,1)",
              }}
            />
          </div>

          {/* ---- LLM call stats（t8/t9 实时统计）---- */}
          {stats && (stats.call_count ?? 0) > 0 ? (
            <div
              className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] tabular-nums"
              style={{ color: "#64748d" }}
            >
              <span>调用 {stats.call_count ?? 0} 次</span>
              {(stats.cache_hit_count ?? 0) > 0 ? (
                <span style={{ color: "#16a34a" }}>缓存命中 {stats.cache_hit_count}</span>
              ) : null}
              <span>tokens {stats.total_tokens ?? 0}</span>
              {(stats.prompt_tokens ?? 0) + (stats.completion_tokens ?? 0) > 0 ? (
                <span>
                  (in {stats.prompt_tokens ?? 0} / out {stats.completion_tokens ?? 0})
                </span>
              ) : null}
              {(stats.total_elapsed_ms ?? 0) > 0 ? (
                <span>LLM 耗时 {Math.round((stats.total_elapsed_ms ?? 0) / 1000)}s</span>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* ---- Divider ---- */}
        <div className="h-px" style={{ backgroundColor: "#e3e8ee" }} />

        {/* ---- Stage timeline ---- */}
        <div className="px-5 py-4 max-h-72 overflow-y-auto">
          <ul className="space-y-2.5">
            {timelineStages.map(({ stage, completed }) => (
              <li key={stage} className="flex items-center gap-2.5">
                {completed ? (
                  <CheckmarkIcon className="shrink-0" />
                ) : (
                  <ArrowIcon className="shrink-0" />
                )}
                <span
                  className="text-[13px] font-light leading-snug"
                  style={{ color: completed ? "#0d253d" : "#665efd" }}
                >
                  {stageLabel(stage)}
                </span>
              </li>
            ))}

            {paperEvents.map((event, i) => (
              <li key={`paper-${i}`} className="flex items-start gap-2.5">
                <PaperIcon className="shrink-0 mt-px" />
                <span
                  className="text-[13px] font-light leading-snug"
                  style={{ color: "#64748d" }}
                >
                  {event.message}
                </span>
              </li>
            ))}
          </ul>

          {timelineStages.length === 0 && paperEvents.length === 0 && (
            <p className="text-[13px] font-light" style={{ color: "#64748d" }}>
              Waiting for events&hellip;
            </p>
          )}
        </div>
      </div>
    </>
  );
}
