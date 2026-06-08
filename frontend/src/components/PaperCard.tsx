import { useMemo, useRef } from "react";
import { BookOpen, ExternalLink, Quote, Users } from "lucide-react";

import type { Paper } from "@/types/research";
import { useInView } from "@/hooks/useInView";

function formatSourceLabel(source: string) {
  switch (source) {
    case "arxiv": return "arXiv";
    case "openalex": return "OpenAlex";
    case "semantic_scholar": return "Semantic Scholar";
    case "crossref": return "CrossRef";
    default: return source || "Unknown";
  }
}

function formatRelevanceScore(score?: number) {
  if (typeof score !== "number" || score <= 0) return "";
  return `相关 ${Math.round(score * 100)}%`;
}

// LAZY_OBSERVER_OPTIONS 提前 200px 触发，提升滚动连续性
const LAZY_OBSERVER_OPTIONS: IntersectionObserverInit = { rootMargin: "200px" };
// CARD_MIN_HEIGHT 骨架占位高度，与正常渲染近似，避免布局跳动
const CARD_MIN_HEIGHT = 220;

export function PaperCard({ paper }: { paper: Paper }) {
  // 1. 监听卡片是否进入视口（含 200px 预加载缓冲）
  const cardRef = useRef<HTMLElement>(null);
  const inView = useInView(cardRef, LAZY_OBSERVER_OPTIONS);

  // 2. 作者信息派生
  const authorText = useMemo(() => {
    if (paper.authors.length === 0) return "Unknown authors";
    return paper.authors.length <= 3
      ? paper.authors.join(", ")
      : `${paper.authors.slice(0, 3).join(", ")} +${paper.authors.length - 3}`;
  }, [paper.authors]);

  return (
    <article
      ref={cardRef}
      style={{
        background: "#ffffff",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        padding: "20px",
        transition: "box-shadow 0.15s ease",
        minHeight: CARD_MIN_HEIGHT,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 4px 12px rgba(83,58,253,0.08)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      {inView ? (
        <PaperCardBody paper={paper} authorText={authorText} />
      ) : (
        <PaperCardSkeleton />
      )}
    </article>
  );
}

// PaperCardBody 真正展示论文标题、摘要、TLDR 等内容
function PaperCardBody({ paper, authorText }: { paper: Paper; authorText: string }) {
  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4
            style={{
              color: "#0d253d",
              fontSize: "15px",
              fontWeight: 600,
              lineHeight: 1.4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
            }}
          >
            {paper.title}
          </h4>
        </div>
        {paper.pdf_url && (
          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "#533afd",
              flexShrink: 0,
              marginTop: "2px",
            }}
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3" style={{ fontSize: "12px", color: "#64748b" }}>
        <span className="flex items-center gap-1">
          <Users className="h-3.5 w-3.5" />
          {authorText}
        </span>
        <span
          style={{
            background: "#f6f9fc",
            border: "1px solid #e3e8ee",
            borderRadius: "9999px",
            padding: "1px 8px",
            fontWeight: 500,
          }}
        >
          {formatSourceLabel(paper.source)}
        </span>
        {paper.published && <span>{paper.published}</span>}
        {paper.citation_count > 0 && (
          <span className="flex items-center gap-1">
            <Quote className="h-3 w-3" />
            {paper.citation_count} cited
          </span>
        )}
        {formatRelevanceScore(paper.topic_relevance_score) && (
          <span
            title={paper.relevance_reason || "主题相关性评分"}
            style={{
              background: "#eef2ff",
              color: "#4338ca",
              border: "1px solid #c7d2fe",
              borderRadius: "9999px",
              padding: "1px 8px",
              fontWeight: 500,
            }}
          >
            {formatRelevanceScore(paper.topic_relevance_score)}
          </span>
        )}
      </div>

      <p
        style={{
          color: "#64748b",
          fontSize: "13px",
          lineHeight: 1.6,
          marginTop: "12px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          display: "-webkit-box",
          WebkitLineClamp: 3,
          WebkitBoxOrient: "vertical",
        }}
      >
        {paper.tldr || paper.summary}
      </p>

      {paper.tldr && (
        <p
          style={{
            color: "#533afd",
            fontSize: "12px",
            fontWeight: 500,
            marginTop: "8px",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          TLDR: {paper.tldr}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {paper.doi && (
          <span
            style={{
              background: "#f6f9fc",
              color: "#64748b",
              border: "1px solid #e3e8ee",
              borderRadius: "9999px",
              padding: "1px 8px",
              fontSize: "11px",
              fontFamily: "monospace",
            }}
          >
            DOI: {paper.doi}
          </span>
        )}
      </div>
    </>
  );
}

// PaperCardSkeleton 视口外占位骨架，保持卡片高度稳定
function PaperCardSkeleton() {
  return (
    <div className="animate-pulse" aria-hidden>
      <div style={{ height: "16px", width: "85%", background: "#eef2f7", borderRadius: "6px" }} />
      <div style={{ height: "12px", width: "60%", background: "#eef2f7", borderRadius: "6px", marginTop: "12px" }} />
      <div style={{ height: "10px", width: "100%", background: "#f1f5f9", borderRadius: "6px", marginTop: "16px" }} />
      <div style={{ height: "10px", width: "92%", background: "#f1f5f9", borderRadius: "6px", marginTop: "8px" }} />
      <div style={{ height: "10px", width: "80%", background: "#f1f5f9", borderRadius: "6px", marginTop: "8px" }} />
    </div>
  );
}

export function PaperListPanel({ papers }: { papers: Paper[] }) {
  if (!papers.length) return null;

  return (
    <section
      style={{
        background: "#ffffff",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        padding: "24px",
      }}
    >
      <div className="flex items-center gap-3">
        <div style={{ background: "#f6f9fc", borderRadius: "12px", padding: "12px" }}>
          <BookOpen className="h-5 w-5" style={{ color: "#533afd" }} />
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
            Papers Found
          </p>
          <h3 style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300, marginTop: "4px" }}>
            论文列表
            <span style={{ fontSize: "14px", color: "#64748b", fontWeight: 400, marginLeft: "8px" }}>
              {papers.length} papers
            </span>
          </h3>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {papers.map((paper) => (
          <PaperCard key={paper.paper_id} paper={paper} />
        ))}
      </div>
    </section>
  );
}
