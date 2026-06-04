import { useState } from "react";
import { Braces, Download, FileText } from "lucide-react";

import type { ResearchReport } from "@/types/research";
import { exportReportAsJson, exportReportAsMarkdown } from "@/utils/reportExport";

type ReportExportPanelProps = {
  report: ResearchReport;
  compact?: boolean;
};

export function ReportExportPanel({
  report,
  compact = false,
}: ReportExportPanelProps) {
  const [statusText, setStatusText] = useState("");

  // handleExport 执行导出并给出轻量反馈。
  function handleExport(type: "markdown" | "json") {
    if (type === "markdown") {
      exportReportAsMarkdown(report);
      setStatusText("已导出 Markdown");
      return;
    }
    exportReportAsJson(report);
    setStatusText("已导出 JSON");
  }

  return (
    <section
      className={["rounded-[28px] p-6", compact ? "p-5" : ""].join(" ")}
      style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
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
            Export
          </p>
          <h3
           
            style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300 }}
          >
            导出当前报告
          </h3>
          <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "#64748b" }}>
            将当前研究结果导出为结构化交付文件，便于汇报展示、归档保存或继续编辑。
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => handleExport("markdown")}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition"
            style={{
              border: "1px solid #e3e8ee",
              background: "#f6f9fc",
              color: "#273951",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#e3e8ee";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#f6f9fc";
            }}
          >
            <FileText className="h-4 w-4" />
            导出 Markdown
          </button>
          <button
            type="button"
            onClick={() => handleExport("json")}
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm text-white transition"
            style={{
              background: "#533afd",
              color: "#ffffff",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#6942f7";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#533afd";
            }}
          >
            <Braces className="h-4 w-4" />
            导出 JSON
          </button>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3 text-xs" style={{ color: "#64748b" }}>
        <span
          className="inline-flex items-center gap-2 rounded-full px-3 py-1"
          style={{ border: "1px solid #e3e8ee", background: "#f6f9fc" }}
        >
          <Download className="h-3.5 w-3.5" />
          {report.request.topic}
        </span>
        {statusText ? <span>{statusText}</span> : <span>支持交付与归档使用</span>}
      </div>
    </section>
  );
}
