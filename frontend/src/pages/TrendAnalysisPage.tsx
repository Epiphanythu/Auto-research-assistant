import { useState } from "react";
import type { TrendAnalysisResult } from "@/types/research";
import TrendChartView from "@/components/TrendChartView";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export default function TrendAnalysisPage() {
  const [topic, setTopic] = useState("");
  const [years, setYears] = useState(5);
  const [data, setData] = useState<TrendAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

      {/* Trend chart */}
      {data && <TrendChartView data={data} />}

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
