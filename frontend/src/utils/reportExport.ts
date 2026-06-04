import type { ResearchReport } from "@/types/research";

const JSON_EXPORT_TYPE = "application/json;charset=utf-8";
const MARKDOWN_EXPORT_TYPE = "text/markdown;charset=utf-8";

// sanitizeFileName 清理导出文件名中的特殊字符。
function sanitizeFileName(input: string) {
  return input.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-").replace(/\s+/g, "-").slice(0, 80);
}

// buildBaseName 生成统一的导出文件名前缀。
function buildBaseName(report: ResearchReport) {
  const topic = report.request.topic || "research-report";
  return sanitizeFileName(topic.toLowerCase()) || "research-report";
}

// downloadText 通过浏览器下载文本内容。
function downloadText(content: string, fileName: string, contentType: string) {
  const blob = new Blob([content], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

// formatList 将列表转为 Markdown 条目。
function formatList(items: string[]) {
  if (!items.length) {
    return "- 暂无";
  }
  return items.map((item) => `- ${item}`).join("\n");
}

// formatSupportLevel 规整支持度文案。
function formatSupportLevel(level: string) {
  switch (level) {
    case "supported":
      return "支持充分";
    case "partial":
      return "支持部分充分";
    case "unsupported":
      return "暂未支持";
    default:
      return level || "未标注";
  }
}

// formatVerdict 规整审查结论文案。
function formatVerdict(verdict: string) {
  switch (verdict) {
    case "overall_pass":
      return "可直接使用";
    case "revise":
      return "建议修订";
    case "blocked":
      return "暂不通过";
    default:
      return verdict || "未标注";
  }
}

// buildMarkdownContent 将研究报告整理为 Markdown 交付内容。
function buildMarkdownContent(report: ResearchReport) {
  const claimLines = report.claim_evidence_table.length
    ? report.claim_evidence_table
        .map(
          (row, index) =>
            `${index + 1}. ${row.claim}\n   - 支持度：${formatSupportLevel(row.support_level)}\n   - 说明：${row.rationale || "暂无说明"}`,
        )
        .join("\n")
    : "- 暂无";

  const citationLines = report.citation_verification.items.length
    ? report.citation_verification.items
        .map(
          (item, index) =>
            `${index + 1}. ${item.claim}\n   - 结果：${formatSupportLevel(item.support_level)}\n   - 说明：${item.reason || "暂无说明"}`,
        )
        .join("\n")
    : "- 暂无";

  const paperLines = report.insights.length
    ? report.insights
        .map(
          (insight, index) =>
            `### ${index + 1}. ${insight.paper.title}\n- 问题：${insight.problem}\n- 方法：${insight.method}\n- 创新：${insight.innovation}\n- 发现：${insight.findings}\n- 局限：${insight.limitation}`,
        )
        .join("\n\n")
    : "暂无论文洞察。";

  return [
    `# ${report.request.topic} 研究报告`,
    "",
    `生成时间：${new Date().toLocaleString("zh-CN")}`,
    "",
    "## 审查结论",
    `- 结论：${formatVerdict(report.review_report.verdict)}`,
    `- 当前优势：${report.review_report.strengths.join("；") || "暂无"}`,
    `- 主要风险：${report.review_report.risks.join("；") || "暂无"}`,
    `- 修订建议：${report.review_report.revision_advice.join("；") || "暂无"}`,
    "",
    "## 研究空白",
    `- 是否建议补充：${report.gap_report.need_follow_up ? "是" : "否"}`,
    `- 判断说明：${report.gap_report.reasoning || "暂无说明"}`,
    "- 待补充问题：",
    formatList(report.gap_report.missing_aspects),
    "- 建议检索方向：",
    formatList(report.gap_report.follow_up_queries),
    "",
    "## 结构化综述",
    report.comparison.overview,
    "",
    "### 趋势",
    formatList(report.comparison.trends),
    "",
    "### 研究空白摘要",
    formatList(report.comparison.gaps),
    "",
    "### 创新建议",
    report.comparison.ideas.length
      ? report.comparison.ideas
          .map((idea, index) => `${index + 1}. ${idea.title}：${idea.rationale}（实施注意：${idea.risk}）`)
          .join("\n")
      : "- 暂无",
    "",
    "## 研究笔记",
    report.research_note || "暂无研究笔记。",
    "",
    "## 后续事项",
    formatList(report.next_actions),
    "",
    "## 结论证据映射",
    claimLines,
    "",
    "## 核验结果",
    `- 总体支持率：${Math.round(report.citation_verification.overall_score * 100)}%`,
    `- 已支持结论：${report.citation_verification.supported_count}`,
    `- 未支持结论：${report.citation_verification.unsupported_count}`,
    citationLines,
    "",
    "## 论文洞察",
    paperLines,
  ].join("\n");
}

// exportReportAsJson 导出 JSON 报告。
export function exportReportAsJson(report: ResearchReport) {
  const fileName = `${buildBaseName(report)}.json`;
  downloadText(JSON.stringify(report, null, 2), fileName, JSON_EXPORT_TYPE);
}

// exportReportAsMarkdown 导出 Markdown 报告。
export function exportReportAsMarkdown(report: ResearchReport) {
  const fileName = `${buildBaseName(report)}.md`;
  downloadText(buildMarkdownContent(report), fileName, MARKDOWN_EXPORT_TYPE);
}
