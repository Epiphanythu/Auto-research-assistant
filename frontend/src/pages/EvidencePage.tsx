import { EmptyState } from "@/components/EmptyState";
import { EvidenceBundlePanel } from "@/components/EvidenceBundlePanel";
import { CitationPanel, ClaimTablePanel, StageTimeline } from "@/components/ReportPanels";
import { useResearchStore } from "@/store/researchStore";

export default function EvidencePage() {
  const report = useResearchStore((state) => state.report);

  if (!report) {
    return (
      <EmptyState
        title="还没有证据整理结果"
        description="发起研究任务后，这里会集中展示正文摘录、结论映射、核验结果和阶段记录。"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <CitationPanel report={report.citation_verification} />
        <StageTimeline stages={report.stage_history} />
      </div>
      <EvidenceBundlePanel bundles={report.evidence_bundles} />
      <ClaimTablePanel rows={report.claim_evidence_table} />
    </div>
  );
}
