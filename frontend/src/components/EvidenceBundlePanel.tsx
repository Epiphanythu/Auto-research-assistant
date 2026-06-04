import type { EvidenceBundle } from "@/types/research";

// formatSourceLabel 统一证据来源展示文案
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

export function EvidenceBundlePanel({
  bundles,
}: {
  bundles: EvidenceBundle[];
}) {
  return (
    <section
      style={{
        background: "#ffffff",
        border: "1px solid #e3e8ee",
        borderRadius: "12px",
        padding: "24px",
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
        Evidence Notes
      </p>
      <h3
        style={{
          color: "#0d253d",
          fontSize: "24px",
          fontWeight: 300,
          marginTop: "8px",
        }}
      >
        正文证据面板
      </h3>
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        {bundles.map((bundle) => (
          <article
            key={bundle.unit_id}
            style={{
              background: "#ffffff",
              border: "1px solid #e3e8ee",
              borderRadius: "12px",
              padding: "20px",
            }}
          >
            <div className="flex items-start justify-between gap-3">
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
                  {bundle.unit_id}
                </p>
                <h4
                  style={{
                    color: "#0d253d",
                    fontSize: "18px",
                    fontWeight: 600,
                    marginTop: "8px",
                  }}
                >
                  {bundle.question}
                </h4>
              </div>
              <span
                style={{
                  background: "#f6f9fc",
                  border: "1px solid #e3e8ee",
                  borderRadius: "9999px",
                  padding: "4px 12px",
                  fontSize: "12px",
                  color: "#273951",
                }}
              >
                参考度 {Math.round(bundle.confidence * 100)}%
              </span>
            </div>
            <p
              style={{
                color: "#64748b",
                fontSize: "14px",
                lineHeight: "24px",
                marginTop: "12px",
              }}
            >
              {bundle.synthesized_findings}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {bundle.supporting_paper_ids.map((paperId) => (
                <span
                  key={paperId}
                  style={{
                    background: "#f6f9fc",
                    borderRadius: "9999px",
                    padding: "4px 12px",
                    fontSize: "12px",
                    color: "#64748b",
                  }}
                >
                  {paperId}
                </span>
              ))}
            </div>
            <div className="mt-4 space-y-3">
              {bundle.evidence.map((evidence, index) => (
                <div
                  key={`${bundle.unit_id}-${index}`}
                  style={{
                    background: "#f6f9fc",
                    border: "1px solid #e3e8ee",
                    borderRadius: "12px",
                    padding: "16px",
                  }}
                >
                  <p
                    style={{
                      color: "#273951",
                      fontSize: "14px",
                      lineHeight: "24px",
                    }}
                  >
                    {evidence.snippet}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span
                      style={{
                        background: "#f6f9fc",
                        borderRadius: "9999px",
                        padding: "4px 12px",
                        fontSize: "12px",
                        color: "#273951",
                      }}
                    >
                      {formatSourceLabel(evidence.source)}
                    </span>
                    <span
                      style={{
                        color: "#64748b",
                        fontSize: "12px",
                      }}
                    >
                      {evidence.section || "未标注章节"}
                    </span>
                    <span
                      style={{
                        color: "#64748b",
                        fontSize: "12px",
                      }}
                    >
                      第 {evidence.page || "-"} 页
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
