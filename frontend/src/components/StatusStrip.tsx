import { AlertTriangle, BookOpenText, FileCheck2, Files, Gauge } from "lucide-react";

type StatusStripProps = {
  paperCount: number;
  evidenceBundleCount: number;
  claimCount: number;
  supportScore: number;
  unsupportedCount: number;
};

export function StatusStrip({
  paperCount,
  evidenceBundleCount,
  claimCount,
  supportScore,
  unsupportedCount,
}: StatusStripProps) {
  const cards = [
    { label: "论文数量", value: paperCount, icon: Files },
    { label: "证据包", value: evidenceBundleCount, icon: BookOpenText },
    { label: "结论映射", value: claimCount, icon: FileCheck2 },
    { label: "支持率", value: `${Math.round(supportScore * 100)}%`, icon: Gauge },
    { label: "未支持结论", value: unsupportedCount, icon: AlertTriangle },
  ];

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <article
            key={card.label}
            className="rounded-xl p-4"
            style={{
              border: "1px solid #e3e8ee",
              background: "#ffffff",
            }}
          >
            <div className="flex items-start justify-between">
              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-[0.2em]"
                  style={{ color: "#64748b" }}
                >
                  {card.label}
                </p>
                <p
                  className="mt-3 text-3xl font-semibold"
                  style={{ color: "#0d253d" }}
                >
                  {card.value}
                </p>
              </div>
              <div
                className="rounded-xl p-3"
                style={{ background: "#f6f9fc", color: "#533afd" }}
              >
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
