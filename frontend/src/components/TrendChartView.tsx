import { useMemo } from "react";
import type { TrendAnalysisResult } from "@/types/research";

type Props = {
  data: TrendAnalysisResult;
  className?: string;
};

/* ---- Stripe design tokens ---- */
const COLORS = {
  primary: "#533afd",
  primarySoft: "#665efd",
  primarySubdued: "#b9b9f9",
  ink: "#0d253d",
  inkMute: "#64748d",
  canvas: "#ffffff",
  canvasSoft: "#f6f9fc",
  hairline: "#e3e8ee",
  ruby: "#ea2261",
  rubySoft: "#fef2f5",
  emerald: "#0d9462",
  emeraldSoft: "#ecfdf5",
} as const;

/* ---- Shared card wrapper ---- */
function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`bg-white rounded-xl border p-5 ${className}`}
      style={{
        borderColor: COLORS.hairline,
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3
      className="text-[13px] font-normal mb-4"
      style={{ color: COLORS.ink }}
    >
      {children}
    </h3>
  );
}

/* ---- Bar chart ---- */
function YearlyBarChart({ data }: { data: TrendAnalysisResult["yearly_paper_counts"] }) {
  const maxCount = useMemo(
    () => Math.max(...data.map((p) => p.count), 1),
    [data]
  );

  return (
    <Card>
      <CardTitle>Annual Publication Volume</CardTitle>
      <div className="flex items-end gap-[6px]" style={{ height: 160 }}>
        {data.map((point) => {
          const heightPct = (point.count / maxCount) * 100;
          return (
            <div key={point.year} className="flex-1 flex flex-col items-center gap-1 min-w-0 group">
              {/* count label */}
              <span
                className="text-[10px] font-light tabular-nums opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: COLORS.inkMute }}
              >
                {point.count}
              </span>
              {/* bar */}
              <div
                className="w-full rounded-t-[3px] transition-colors duration-150"
                style={{
                  height: `${heightPct}%`,
                  minHeight: 4,
                  background: COLORS.primary,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background = COLORS.primarySoft;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background = COLORS.primary;
                }}
                title={`${point.year}: ${point.count} papers`}
              />
              {/* year label */}
              <span
                className="text-[10px] font-light"
                style={{ color: COLORS.inkMute }}
              >
                {point.year}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ---- SVG Line chart ---- */
function VelocityLineChart({ data }: { data: TrendAnalysisResult["citation_velocity"] }) {
  const maxVelocity = useMemo(
    () => Math.max(...data.map((v) => v.avg_citations_per_year), 0.1),
    [data]
  );

  const padL = 44;
  const padR = 16;
  const padT = 16;
  const padB = 24;
  const svgW = 400;
  const svgH = 160;
  const plotW = svgW - padL - padR;
  const plotH = svgH - padT - padB;

  const points = data.map((v, i) => ({
    x: padL + (i / Math.max(data.length - 1, 1)) * plotW,
    y: padT + plotH - (v.avg_citations_per_year / maxVelocity) * plotH,
    ...v,
  }));

  const linePoints = points.map((p) => `${p.x},${p.y}`).join(" ");

  /* build a subtle gradient fill under the line */
  const areaPath = [
    `M${points[0]?.x ?? 0},${padT + plotH}`,
    ...points.map((p) => `L${p.x},${p.y}`),
    `L${points[points.length - 1]?.x ?? 0},${padT + plotH}`,
    "Z",
  ].join(" ");

  return (
    <Card>
      <CardTitle>Citation Velocity</CardTitle>
      <div style={{ height: svgH }}>
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          className="w-full h-full"
          style={{ overflow: "visible" }}
        >
          <defs>
            <linearGradient id="vel-area-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.primary} stopOpacity="0.12" />
              <stop offset="100%" stopColor={COLORS.primary} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = padT + plotH - ratio * plotH;
            return (
              <line
                key={ratio}
                x1={padL}
                y1={y}
                x2={svgW - padR}
                y2={y}
                stroke={COLORS.hairline}
                strokeWidth="0.5"
              />
            );
          })}

          {/* Y-axis labels */}
          {[0, 0.5, 1].map((ratio) => {
            const y = padT + plotH - ratio * plotH;
            const val = (maxVelocity * ratio).toFixed(1);
            return (
              <text
                key={ratio}
                x={padL - 6}
                y={y + 3}
                textAnchor="end"
                fill={COLORS.inkMute}
                fontSize="9"
                fontFamily="'Inter', system-ui, sans-serif"
              >
                {val}
              </text>
            );
          })}

          {/* Area fill */}
          {points.length > 1 && <path d={areaPath} fill="url(#vel-area-fill)" />}

          {/* Line */}
          <polyline
            fill="none"
            stroke={COLORS.primary}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={linePoints}
          />

          {/* Data points + labels */}
          {points.map((p) => (
            <g key={p.year}>
              <circle cx={p.x} cy={p.y} r="3.5" fill={COLORS.canvas} stroke={COLORS.primary} strokeWidth="1.5" />
              <text
                x={p.x}
                y={padT + plotH + 14}
                textAnchor="middle"
                fill={COLORS.inkMute}
                fontSize="9"
                fontFamily="'Inter', system-ui, sans-serif"
              >
                {p.year}
              </text>
              <text
                x={p.x}
                y={p.y - 8}
                textAnchor="middle"
                fill={COLORS.primary}
                fontSize="8"
                fontFamily="'Inter', system-ui, sans-serif"
              >
                {p.avg_citations_per_year.toFixed(1)}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </Card>
  );
}

/* ---- Direction list ---- */
function DirectionList({
  title,
  items,
  accentColor,
  accentBg,
  icon,
}: {
  title: string;
  items: string[];
  accentColor: string;
  accentBg: string;
  icon: "up" | "down";
}) {
  if (items.length === 0) return null;
  return (
    <Card>
      <h3 className="text-[13px] font-normal mb-3" style={{ color: accentColor }}>
        {title}
      </h3>
      <ul className="space-y-2">
        {items.map((dir, i) => (
          <li key={i} className="flex items-start gap-2">
            <span
              className="shrink-0 mt-[3px] flex items-center justify-center w-[18px] h-[18px] rounded-full text-[10px]"
              style={{ backgroundColor: accentBg, color: accentColor }}
            >
              {icon === "up" ? "↑" : "↓"}
            </span>
            <span
              className="text-[13px] font-light leading-snug"
              style={{ color: COLORS.ink }}
            >
              {dir}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* ---- Emerging topics ---- */
function EmergingTopics({ topics }: { topics: string[] }) {
  if (topics.length === 0) return null;
  return (
    <Card>
      <CardTitle>Emerging Topics</CardTitle>
      <div className="flex flex-wrap gap-2">
        {topics.map((topic) => (
          <span
            key={topic}
            className="inline-flex items-center px-3 py-[5px] rounded-full text-[12px] font-normal"
            style={{
              backgroundColor: COLORS.canvasSoft,
              color: COLORS.primary,
              border: `1px solid ${COLORS.primarySubdued}`,
            }}
          >
            {topic}
          </span>
        ))}
      </div>
    </Card>
  );
}

/* ---- Main component ---- */

export default function TrendChartView({ data, className = "" }: Props) {
  return (
    <div className={`space-y-5 ${className}`}>
      {/* Summary */}
      {data.trend_summary && (
        <Card>
          <CardTitle>Trend Summary</CardTitle>
          <p
            className="text-[13px] font-light leading-relaxed"
            style={{ color: COLORS.inkMute }}
          >
            {data.trend_summary}
          </p>
        </Card>
      )}

      {/* Bar chart */}
      {data.yearly_paper_counts.length > 0 && (
        <YearlyBarChart data={data.yearly_paper_counts} />
      )}

      {/* Line chart */}
      {data.citation_velocity.length > 0 && (
        <VelocityLineChart data={data.citation_velocity} />
      )}

      {/* Hot & Cooling */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <DirectionList
          title="Hot Directions"
          items={data.hot_directions}
          accentColor={COLORS.ruby}
          accentBg={COLORS.rubySoft}
          icon="up"
        />
        <DirectionList
          title="Cooling Directions"
          items={data.cooling_directions}
          accentColor={COLORS.inkMute}
          accentBg={COLORS.canvasSoft}
          icon="down"
        />
      </div>

      {/* Emerging Topics */}
      <EmergingTopics topics={data.emerging_topics} />
    </div>
  );
}
