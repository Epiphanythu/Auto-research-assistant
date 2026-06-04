import { EmptyState } from "@/components/EmptyState";
import {
  GapReportPanel,
  InsightList,
  OverviewPanel,
  ReviewDecisionPanel,
} from "@/components/ReportPanels";
import { ReportExportPanel } from "@/components/ReportExportPanel";
import { useResearchStore } from "@/store/researchStore";

export default function ReviewPage() {
  const report = useResearchStore((state) => state.report);

  if (!report) {
    return (
      <EmptyState
        title="还没有研究综述结果"
        description="先在工作台提交一次研究任务，这里会汇总趋势判断、研究空白、后续建议和研究笔记。"
      />
    );
  }

  return (
    <div className="space-y-6">
      <ReportExportPanel report={report} />
      <ReviewDecisionPanel reviewReport={report.review_report} />
      <GapReportPanel gapReport={report.gap_report} />
      <OverviewPanel
        overview={report.comparison.overview}
        trends={report.comparison.trends}
        gaps={report.comparison.gaps}
        ideas={report.comparison.ideas}
        researchNote={report.research_note}
        nextActions={report.next_actions}
      />
      <InsightList insights={report.insights} />
    </div>
  );
}
