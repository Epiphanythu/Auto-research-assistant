import { ExternalLink, Lightbulb, LoaderCircle, Quote, Users } from "lucide-react";

import type { PaperRecommendation } from "@/types/research";

export function RecommendationsPanel({
  recommendations,
  loading,
  onLoadMore,
}: {
  recommendations: PaperRecommendation[];
  loading: boolean;
  onLoadMore: () => void;
}) {
  if (!loading && !recommendations.length) return null;

  return (
    <section
      style={{
        background: "#ffffff",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        padding: "24px",
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
            <Lightbulb className="h-5 w-5" style={{ color: "#533afd" }} />
          </div>
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
              Recommendations
            </p>
            <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>
              相关论文推荐
              <span style={{ fontSize: "14px", color: "#64748b", fontWeight: 400, marginLeft: "8px" }}>
                {recommendations.length} papers
              </span>
            </h3>
          </div>
        </div>
        <button
          type="button"
          onClick={onLoadMore}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition hover:opacity-80"
          style={{ color: "#533afd", background: "#f6f9fc", border: "1px solid #e3e8ee" }}
        >
          {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Lightbulb className="h-4 w-4" />}
          {loading ? "加载中..." : "获取推荐"}
        </button>
      </div>

      {loading && !recommendations.length ? (
        <div className="mt-6 flex items-center gap-3" style={{ color: "#64748b", fontSize: "14px" }}>
          <LoaderCircle className="h-4 w-4 animate-spin" />
          <span>正在获取相关论文推荐...</span>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {recommendations.map((rec) => (
            <RecommendationCard key={rec.paper_id} recommendation={rec} />
          ))}
        </div>
      )}
    </section>
  );
}

function RecommendationCard({ recommendation }: { recommendation: PaperRecommendation }) {
  const authorText = recommendation.authors.length > 0
    ? recommendation.authors.length <= 3
      ? recommendation.authors.join(", ")
      : `${recommendation.authors.slice(0, 3).join(", ")} +${recommendation.authors.length - 3}`
    : "";

  return (
    <article
      style={{
        background: "#f6f9fc",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        padding: "16px",
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <h4
          style={{
            color: "#0d253d",
            fontSize: "14px",
            fontWeight: 600,
            lineHeight: 1.4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            flex: 1,
          }}
        >
          {recommendation.title}
        </h4>
        {recommendation.pdf_url && (
          <a
            href={recommendation.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#533afd", flexShrink: 0 }}
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2" style={{ fontSize: "11px", color: "#64748b" }}>
        {authorText && (
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            {authorText}
          </span>
        )}
        {recommendation.year && <span>{recommendation.year}</span>}
        {recommendation.citation_count > 0 && (
          <span className="flex items-center gap-1">
            <Quote className="h-3 w-3" />
            {recommendation.citation_count}
          </span>
        )}
      </div>

      {recommendation.abstract && (
        <p
          style={{
            color: "#64748b",
            fontSize: "12px",
            lineHeight: 1.5,
            marginTop: "8px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
          }}
        >
          {recommendation.tldr || recommendation.abstract}
        </p>
      )}

      {recommendation.reason && (
        <p style={{ color: "#533afd", fontSize: "11px", marginTop: "8px" }}>
          {recommendation.reason}
        </p>
      )}
    </article>
  );
}
