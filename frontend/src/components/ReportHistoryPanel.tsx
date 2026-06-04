import { useMemo, useState } from "react";
import { GitCompareArrows, History, LoaderCircle, RefreshCcw, Search, SlidersHorizontal, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { ReportArchiveSummary } from "@/types/research";

type ReportHistoryPanelProps = {
  items: ReportArchiveSummary[];
  loading: boolean;
  onRefresh: () => Promise<void>;
  compareSelection: string[];
  onToggleCompare: (reportId: string) => void;
  onClearCompare: () => void;
};

type SortOption = "created_desc" | "created_asc" | "support_desc" | "support_asc";
type SupportFilter = "all" | "high" | "mid" | "low";

export function ReportHistoryPanel({
  items,
  loading,
  onRefresh,
  compareSelection,
  onToggleCompare,
  onClearCompare,
}: ReportHistoryPanelProps) {
  const [topicKeyword, setTopicKeyword] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [sortOption, setSortOption] = useState<SortOption>("created_desc");
  const [supportFilter, setSupportFilter] = useState<SupportFilter>("all");

  // 1. 根据搜索词、结论、支持率组合过滤历史报告。
  const filteredItems = useMemo(() => {
    const normalizedKeyword = topicKeyword.trim().toLowerCase();
    const matched = items.filter((item) => {
      const matchTopic = normalizedKeyword
        ? item.topic.toLowerCase().includes(normalizedKeyword)
        : true;
      const matchVerdict =
        verdictFilter === "all" ? true : item.verdict === verdictFilter;
      const matchSupport = matchSupportRange(item.support_score, supportFilter);
      return matchTopic && matchVerdict && matchSupport;
    });
    // 2. 根据排序选项再次排序，得到最终展示顺序。
    return [...matched].sort((a, b) => compareItems(a, b, sortOption));
  }, [items, topicKeyword, verdictFilter, supportFilter, sortOption]);

  return (
    <section
      className="rounded-[28px] p-6"
      style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div
            className="rounded-2xl p-3"
            style={{ background: "#f6f9fc", color: "#0d253d" }}
          >
            <History className="h-5 w-5" />
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
              Archive
            </p>
            <h3
             
              style={{ color: "#0d253d", fontSize: "24px", fontWeight: 300 }}
            >
              历史报告
            </h3>
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm transition"
          style={{
            background: "#f6f9fc",
            border: "1px solid #e3e8ee",
            color: "#0d253d",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#e3e8ee";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#f6f9fc";
          }}
        >
          <RefreshCcw className="h-4 w-4" />
          刷新列表
        </button>
      </div>

      <div
        className="mt-5 flex flex-col gap-3 rounded-2xl px-4 py-3 lg:flex-row lg:items-center lg:justify-between"
        style={{ background: "#f6f9fc", border: "1px solid #e3e8ee" }}
      >
        <div className="flex items-center gap-3 text-sm" style={{ color: "#273951" }}>
          <GitCompareArrows className="h-4 w-4" />
          <span>
            已选 {compareSelection.length} / 3 份报告进行比对
          </span>
          {compareSelection.length ? (
            <button
              type="button"
              onClick={onClearCompare}
              className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs transition"
              style={{
                background: "#f6f9fc",
                border: "1px solid #e3e8ee",
                color: "#64748b",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#e3e8ee";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#f6f9fc";
              }}
            >
              <Trash2 className="h-3 w-3" />
              清空选择
            </button>
          ) : null}
        </div>
        <Link
          to="/compare"
          className="rounded-full px-4 py-2 text-sm transition"
          style={
            compareSelection.length >= 2
              ? { background: "#533afd", color: "#ffffff", border: "1px solid #533afd" }
              : { background: "#f6f9fc", color: "#64748b", border: "1px solid #e3e8ee", pointerEvents: "none" as const }
          }
        >
          {compareSelection.length >= 2 ? "进入比对视图" : "至少选中 2 份才能比对"}
        </Link>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1.5fr_0.9fr_0.9fr_0.9fr_auto]">
        <label
          className="flex items-center gap-3 rounded-2xl px-4 py-3"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          <Search className="h-4 w-4" style={{ color: "#64748b" }} />
          <input
            value={topicKeyword}
            onChange={(event) => setTopicKeyword(event.target.value)}
            placeholder="按研究主题搜索历史报告"
            className="w-full bg-transparent text-sm outline-none"
            style={{ color: "#0d253d" }}
          />
        </label>

        <label
          className="flex items-center gap-3 rounded-2xl px-4 py-3"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          <SlidersHorizontal className="h-4 w-4" style={{ color: "#64748b" }} />
          <select
            value={verdictFilter}
            onChange={(event) => setVerdictFilter(event.target.value)}
            className="w-full bg-transparent text-sm outline-none"
            style={{ background: "#ffffff", border: "none", color: "#0d253d" }}
          >
            <option value="all">全部结论</option>
            <option value="overall_pass">可直接使用</option>
            <option value="revise">建议修订</option>
            <option value="blocked">暂不通过</option>
          </select>
        </label>

        <label
          className="flex items-center gap-3 rounded-2xl px-4 py-3"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          <span
            style={{
              color: "#64748b",
              fontSize: "11px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.2em",
            }}
          >
            支持率
          </span>
          <select
            value={supportFilter}
            onChange={(event) => setSupportFilter(event.target.value as SupportFilter)}
            className="w-full bg-transparent text-sm outline-none"
            style={{ background: "#ffffff", border: "none", color: "#0d253d" }}
          >
            <option value="all">全部</option>
            <option value="high">高于 80%</option>
            <option value="mid">50%-80%</option>
            <option value="low">低于 50%</option>
          </select>
        </label>

        <label
          className="flex items-center gap-3 rounded-2xl px-4 py-3"
          style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
        >
          <span
            style={{
              color: "#64748b",
              fontSize: "11px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.2em",
            }}
          >
            排序
          </span>
          <select
            value={sortOption}
            onChange={(event) => setSortOption(event.target.value as SortOption)}
            className="w-full bg-transparent text-sm outline-none"
            style={{ background: "#ffffff", border: "none", color: "#0d253d" }}
          >
            <option value="created_desc">创建时间从新到旧</option>
            <option value="created_asc">创建时间从旧到新</option>
            <option value="support_desc">支持率从高到低</option>
            <option value="support_asc">支持率从低到高</option>
          </select>
        </label>

        <button
          type="button"
          onClick={() => {
            setTopicKeyword("");
            setVerdictFilter("all");
            setSupportFilter("all");
            setSortOption("created_desc");
          }}
          className="rounded-2xl px-4 py-3 text-sm transition"
          style={{
            background: "#f6f9fc",
            border: "1px solid #e3e8ee",
            color: "#64748b",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#e3e8ee";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#f6f9fc";
          }}
        >
          清空筛选
        </button>
      </div>

      {!loading ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs" style={{ color: "#64748b" }}>
          <span>共 {items.length} 条历史记录</span>
          <span>当前显示 {filteredItems.length} 条</span>
          {topicKeyword ? <span>主题包含"{topicKeyword.trim()}"</span> : null}
          {verdictFilter !== "all" ? (
            <span>结论为"{formatVerdictLabel(verdictFilter)}"</span>
          ) : null}
          {supportFilter !== "all" ? (
            <span>支持率为"{formatSupportLabel(supportFilter)}"</span>
          ) : null}
          <span>{formatSortLabel(sortOption)}</span>
        </div>
      ) : null}

      {loading ? (
        <div
          className="mt-5 flex items-center gap-2 rounded-2xl px-4 py-4 text-sm"
          style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", color: "#64748b" }}
        >
          <LoaderCircle className="h-4 w-4 animate-spin" />
          正在加载历史报告
        </div>
      ) : filteredItems.length ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {filteredItems.map((item) => (
            <article
              key={item.report_id}
              className="rounded-[24px] p-5"
              style={{ background: "#ffffff", border: "1px solid #e3e8ee" }}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="text-base font-semibold" style={{ color: "#0d253d" }}>
                    {item.topic}
                  </h4>
                  <p
                    className="mt-2"
                    style={{
                      color: "#64748b",
                      fontSize: "11px",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.2em",
                    }}
                  >
                    {formatArchiveTime(item.created_at)}
                  </p>
                </div>
                <span
                  className="rounded-full px-3 py-1 text-xs"
                  style={formatVerdictPillStyle(item.verdict)}
                >
                  {formatVerdictLabel(item.verdict)}
                </span>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <MiniMetric label="论文数" value={item.paper_count} />
                <MiniMetric label="阶段数" value={item.stage_count} />
                <MiniMetric
                  label="支持率"
                  value={`${Math.round(item.support_score * 100)}%`}
                />
              </div>

              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="truncate text-xs" style={{ color: "#64748b" }}>
                  {item.report_id}
                </p>
                <div className="flex items-center gap-3">
                  <label
                    className="inline-flex cursor-pointer items-center gap-2 rounded-full px-3 py-1.5 text-xs transition"
                    style={{
                      background: "#f6f9fc",
                      border: "1px solid #e3e8ee",
                      color: "#273951",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "#e3e8ee";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "#f6f9fc";
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={compareSelection.includes(item.report_id)}
                      onChange={() => onToggleCompare(item.report_id)}
                      className="h-3.5 w-3.5"
                      style={{ accentColor: "#533afd" }}
                    />
                    加入比对
                  </label>
                  <Link
                    to={`/reports/${item.report_id}`}
                    className="rounded-full px-4 py-2 text-sm text-white transition"
                    style={{ background: "#533afd", border: "1px solid #533afd" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "#4529d4";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "#533afd";
                    }}
                  >
                    打开报告
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : items.length ? (
        <div
          className="mt-5 rounded-2xl px-4 py-5 text-sm"
          style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", color: "#64748b" }}
        >
          当前筛选条件下没有匹配的历史报告，请调整主题关键词、结论或支持率筛选项。
        </div>
      ) : (
        <div
          className="mt-5 rounded-2xl px-4 py-5 text-sm"
          style={{ background: "#f6f9fc", border: "1px solid #e3e8ee", color: "#64748b" }}
        >
          当前还没有历史报告，先提交一次研究任务即可自动归档。
        </div>
      )}
    </section>
  );
}

function MiniMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div
      className="rounded-2xl px-4 py-3"
      style={{ background: "#f6f9fc", border: "1px solid #e3e8ee" }}
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
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold" style={{ color: "#0d253d" }}>
        {value}
      </p>
    </div>
  );
}

// matchSupportRange 根据支持率筛选项判断当前条目是否符合。
function matchSupportRange(supportScore: number, filter: SupportFilter) {
  switch (filter) {
    case "high":
      return supportScore >= 0.8;
    case "mid":
      return supportScore >= 0.5 && supportScore < 0.8;
    case "low":
      return supportScore < 0.5;
    default:
      return true;
  }
}

// compareItems 按选中的排序方式比较两个历史归档条目。
function compareItems(
  a: ReportArchiveSummary,
  b: ReportArchiveSummary,
  option: SortOption,
) {
  switch (option) {
    case "created_asc":
      return safeTimestamp(a.created_at) - safeTimestamp(b.created_at);
    case "support_desc":
      return b.support_score - a.support_score;
    case "support_asc":
      return a.support_score - b.support_score;
    case "created_desc":
    default:
      return safeTimestamp(b.created_at) - safeTimestamp(a.created_at);
  }
}

// safeTimestamp 将归档时间转换为可比较的数值，无效值视为 0。
function safeTimestamp(value: string) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function formatArchiveTime(createdAt: string) {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return createdAt || "时间未知";
  }
  return date.toLocaleString("zh-CN");
}

function formatVerdictLabel(verdict: string) {
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

function formatVerdictPillStyle(verdict: string): React.CSSProperties {
  const base: React.CSSProperties = {
    borderRadius: "9999px",
    border: "1px solid #e3e8ee",
    background: "#f6f9fc",
    color: "#533afd",
    padding: "2px 12px",
    fontSize: "12px",
  };
  switch (verdict) {
    case "overall_pass":
      return { ...base, background: "#ecfdf5", color: "#059669", borderColor: "#a7f3d0" };
    case "revise":
      return { ...base, background: "#fffbeb", color: "#d97706", borderColor: "#fde68a" };
    case "blocked":
      return { ...base, background: "#fef2f2", color: "#dc2626", borderColor: "#fecaca" };
    default:
      return base;
  }
}

function formatSupportLabel(filter: SupportFilter) {
  switch (filter) {
    case "high":
      return "高于 80%";
    case "mid":
      return "50%-80%";
    case "low":
      return "低于 50%";
    default:
      return "全部";
  }
}

function formatSortLabel(option: SortOption) {
  switch (option) {
    case "created_asc":
      return "创建时间从旧到新";
    case "support_desc":
      return "支持率从高到低";
    case "support_asc":
      return "支持率从低到高";
    case "created_desc":
    default:
      return "创建时间从新到旧";
  }
}
