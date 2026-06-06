import { useEffect, useMemo, useState } from "react";
import type { TrendAnalysisResult } from "@/types/research";
import TrendChartView from "@/components/TrendChartView";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

// DEFAULT_TOP_KEYWORDS 默认按总频次取前 N 个关键词参与趋势绘制
const DEFAULT_TOP_KEYWORDS = 5;

export default function TrendAnalysisPage() {
  const [topic, setTopic] = useState("");
  const [years, setYears] = useState(5);
  const [data, setData] = useState<TrendAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 1. 年份窗口与关键词选中状态：拉取新数据后会被重置为合理默认值
  const [fromYear, setFromYear] = useState<number | null>(null);
  const [toYear, setToYear] = useState<number | null>(null);
  const [activeKeywords, setActiveKeywords] = useState<string[]>([]);

  // 2. 计算原始数据中的可用年份区间
  const yearBounds = useMemo(() => {
    if (!data) return null;
    const allYears = new Set<number>();
    data.yearly_paper_counts.forEach((p) => allYears.add(p.year));
    Object.values(data.keyword_trends).forEach((points) => {
      points.forEach((p) => allYears.add(p.year));
    });
    if (allYears.size === 0) return null;
    const sorted = [...allYears].sort((a, b) => a - b);
    return { min: sorted[0], max: sorted[sorted.length - 1] };
  }, [data]);

  // 3. 关键词总频次排序，便于选择默认 Top N
  const keywordTotals = useMemo(() => {
    if (!data) return [] as Array<{ keyword: string; total: number }>;
    return Object.entries(data.keyword_trends)
      .map(([keyword, points]) => ({
        keyword,
        total: points.reduce((sum, p) => sum + p.count, 0),
      }))
      .sort((a, b) => b.total - a.total);
  }, [data]);

  // 4. 加载新数据后重置年份窗口与默认 Top 关键词
  useEffect(() => {
    if (!data || !yearBounds) {
      setFromYear(null);
      setToYear(null);
      setActiveKeywords([]);
      return;
    }
    setFromYear(yearBounds.min);
    setToYear(yearBounds.max);
    setActiveKeywords(keywordTotals.slice(0, DEFAULT_TOP_KEYWORDS).map((item) => item.keyword));
  }, [data, yearBounds, keywordTotals]);

  // 5. 在原始数据基础上按年份窗口与选中关键词过滤，得到给图表展示的数据视图
  const filteredData = useMemo<TrendAnalysisResult | null>(() => {
    if (!data) return null;
    const lo = fromYear ?? yearBounds?.min ?? Number.NEGATIVE_INFINITY;
    const hi = toYear ?? yearBounds?.max ?? Number.POSITIVE_INFINITY;
    const inRange = (year: number) => year >= lo && year <= hi;
    const filteredKeywordTrends: Record<string, typeof data.keyword_trends[string]> = {};
    activeKeywords.forEach((keyword) => {
      const points = data.keyword_trends[keyword];
      if (points) {
        filteredKeywordTrends[keyword] = points.filter((p) => inRange(p.year));
      }
    });
    return {
      ...data,
      yearly_paper_counts: data.yearly_paper_counts.filter((p) => inRange(p.year)),
      citation_velocity: data.citation_velocity.filter((p) => inRange(p.year)),
      keyword_trends: filteredKeywordTrends,
    };
  }, [data, fromYear, toYear, yearBounds, activeKeywords]);

  // toggleKeyword 切换关键词在图表中的显示
  const toggleKeyword = (keyword: string) => {
    setActiveKeywords((prev) =>
      prev.includes(keyword) ? prev.filter((k) => k !== keyword) : [...prev, keyword],
    );
  };

  const analyzeTrends = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/trends/${encodeURIComponent(
          topic.trim()
        )}?years=${years}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const result: TrendAnalysisResult = await res.json();
      setData(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to analyze trends"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1
          className="text-2xl font-light tracking-tight"
          style={{ color: "#0d253d" }}
        >
          Research Trend Analysis
        </h1>
        <p className="mt-1 text-sm font-light" style={{ color: "#64748b" }}>
          Analyze publication volume, citation velocity, emerging topics, and
          research direction trends over time.
        </p>
      </div>

      {/* Controls card */}
      <div
        className="rounded-xl p-5"
        style={{
          background: "#ffffff",
          border: "1px solid #e3e8ee",
        }}
      >
        <div className="flex items-center gap-3">
          {/* Topic input */}
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Enter a research topic (e.g., large language model, transformer)"
            onKeyDown={(e) => e.key === "Enter" && analyzeTrends()}
            className="flex-1 rounded-md px-4 py-2.5 text-sm outline-none transition-all"
            style={{
              border: "1px solid #e3e8ee",
              color: "#0d253d",
              fontFamily: "Inter, system-ui, sans-serif",
              fontWeight: 400,
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#533afd";
              e.currentTarget.style.boxShadow =
                "0 0 0 3px rgba(83,58,253,0.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e3e8ee";
              e.currentTarget.style.boxShadow = "none";
            }}
          />

          {/* Years selector */}
          <select
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            className="rounded-md px-3 py-2.5 text-sm outline-none transition-all appearance-none cursor-pointer"
            style={{
              border: "1px solid #e3e8ee",
              color: "#0d253d",
              background: "#ffffff",
              fontFamily: "Inter, system-ui, sans-serif",
              fontWeight: 400,
              minWidth: "120px",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#533afd";
              e.currentTarget.style.boxShadow =
                "0 0 0 3px rgba(83,58,253,0.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e3e8ee";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            {[3, 5, 7, 10].map((y) => (
              <option key={y} value={y}>
                Last {y} years
              </option>
            ))}
          </select>

          {/* Analyze — pill button */}
          <button
            onClick={analyzeTrends}
            disabled={loading || !topic.trim()}
            className="shrink-0 rounded-full px-6 py-2.5 text-sm font-medium text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: "#533afd",
              fontFamily: "Inter, system-ui, sans-serif",
            }}
            onMouseEnter={(e) => {
              if (!e.currentTarget.disabled)
                e.currentTarget.style.background = "#4434d4";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#533afd";
            }}
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Analyzing…
              </span>
            ) : (
              "Analyze"
            )}
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div
          className="rounded-xl px-4 py-3 text-sm"
          style={{
            background: "#fff5f7",
            border: "1px solid #e3e8ee",
            borderLeftWidth: "3px",
            borderLeftColor: "#ea2261",
            color: "#ea2261",
            fontFamily: "Inter, system-ui, sans-serif",
          }}
        >
          <span className="font-medium">Error:</span> {error}
        </div>
      )}

      {/* 交互筛选区：年份窗口 + 关键词选择 */}
      {data && yearBounds && filteredData ? (
        <div
          className="rounded-xl p-5 space-y-4"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          {/* 1. 年份窗口控制 */}
          <div className="flex items-center gap-4 flex-wrap">
            <span
              className="text-[12px] font-medium"
              style={{ color: "#0d253d", letterSpacing: "0.04em" }}
            >
              Year window
            </span>
            <YearNumberInput
              label="From"
              min={yearBounds.min}
              max={toYear ?? yearBounds.max}
              value={fromYear ?? yearBounds.min}
              onChange={(v) => setFromYear(v)}
            />
            <YearNumberInput
              label="To"
              min={fromYear ?? yearBounds.min}
              max={yearBounds.max}
              value={toYear ?? yearBounds.max}
              onChange={(v) => setToYear(v)}
            />
            <button
              type="button"
              onClick={() => {
                setFromYear(yearBounds.min);
                setToYear(yearBounds.max);
              }}
              className="text-[12px] rounded-full px-3 py-1 transition"
              style={{
                color: "#533afd",
                border: "1px solid #e3e8ee",
                background: "#ffffff",
              }}
            >
              Reset
            </button>
          </div>

          {/* 2. 关键词 chip 列表：点击切换是否参与趋势绘制 */}
          {keywordTotals.length > 0 && (
            <div>
              <div className="flex items-center justify-between gap-2">
                <span
                  className="text-[12px] font-medium"
                  style={{ color: "#0d253d", letterSpacing: "0.04em" }}
                >
                  Pinned keywords
                </span>
                <span className="text-[11px]" style={{ color: "#64748b" }}>
                  Default: top {DEFAULT_TOP_KEYWORDS} by total frequency
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {keywordTotals.map(({ keyword, total }) => {
                  const active = activeKeywords.includes(keyword);
                  return (
                    <button
                      key={keyword}
                      type="button"
                      onClick={() => toggleKeyword(keyword)}
                      className="rounded-full px-3 py-1 text-[12px] transition"
                      style={{
                        background: active ? "#533afd" : "#f6f9fc",
                        color: active ? "#ffffff" : "#273951",
                        border: `1px solid ${active ? "#533afd" : "#e3e8ee"}`,
                        cursor: "pointer",
                      }}
                    >
                      {keyword}
                      <span
                        className="ml-2 text-[10px]"
                        style={{ color: active ? "rgba(255,255,255,0.8)" : "#64748b" }}
                      >
                        {total}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* Trend chart */}
      {filteredData && <TrendChartView data={filteredData} />}

      {/* Empty state */}
      {!data && !loading && (
        <div
          className="rounded-xl p-16 text-center"
          style={{
            background: "#f6f9fc",
            border: "1px solid #e3e8ee",
          }}
        >
          <div
            className="text-sm font-light"
            style={{ color: "#64748b", fontFamily: "Inter, system-ui, sans-serif" }}
          >
            Enter a research topic to analyze its trends over time.
          </div>
        </div>
      )}
    </div>
  );
}

// YearNumberInput 渲染年份数字输入框，并在变更时回写父组件状态
function YearNumberInput({
  label,
  min,
  max,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-[12px]" style={{ color: "#64748b" }}>
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const next = Number(e.target.value);
          if (Number.isNaN(next)) return;
          // 钳制范围以避免父级 from > to 的非法窗口
          onChange(Math.min(Math.max(next, min), max));
        }}
        className="rounded-md px-2 py-1 text-[12px] outline-none"
        style={{
          border: "1px solid #e3e8ee",
          color: "#0d253d",
          background: "#ffffff",
          width: "84px",
        }}
      />
    </label>
  );
}
