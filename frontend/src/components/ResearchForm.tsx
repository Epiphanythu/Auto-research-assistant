import { useEffect, useState } from "react";
import { LoaderCircle, Play, Sparkles, X } from "lucide-react";

import type { ResearchRequest } from "@/types/research";

type FollowUpSummary = {
  baseTopic: string;
  direction: string;
  sourceReportId: string | null;
};

type ResearchFormProps = {
  loading: boolean;
  initialRequest?: ResearchRequest | null;
  followUp?: FollowUpSummary | null;
  onClearFollowUp?: () => void;
  onSubmit: (request: ResearchRequest) => Promise<void>;
};

const defaultRequest: ResearchRequest = {
  topic: "代码大模型自动程序修复",
  max_papers: 3,
  include_memory: true,
  enable_full_text: true,
  max_full_text_papers: 2,
};

export function ResearchForm({
  loading,
  initialRequest,
  followUp,
  onClearFollowUp,
  onSubmit,
}: ResearchFormProps) {
  const [formState, setFormState] = useState<ResearchRequest>(defaultRequest);

  useEffect(() => {
    if (!initialRequest) return;
    setFormState(initialRequest);
  }, [initialRequest]);

  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        await onSubmit(formState);
      }}
    >
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: "#64748b" }}
          >
            Task Setup
          </p>
          <h2
            className="mt-2 text-2xl font-light tracking-tight"
            style={{ color: "#0d253d" }}
          >
            配置研究任务
          </h2>
          <p
            className="mt-3 max-w-2xl text-sm leading-6"
            style={{ color: "#64748b" }}
          >
            输入研究主题并设置检索范围和全文解析参数。提交后可查看综述结果、证据片段和结论支撑情况。
          </p>
          {initialRequest ? (
            <p className="mt-3 text-xs leading-6" style={{ color: "#64748b" }}>
              已自动载入最近一次请求参数，可直接在此基础上继续补充研究。
            </p>
          ) : null}
          {followUp ? (
            <div
              className="mt-4 inline-flex items-center gap-3 rounded-xl px-4 py-3 text-xs"
              style={{
                border: "1px solid #e3e8ee",
                background: "#f6f9fc",
                color: "#273951",
              }}
            >
              <Sparkles className="h-4 w-4" style={{ color: "#533afd" }} />
              <div>
                <p className="text-sm font-medium" style={{ color: "#0d253d" }}>
                  正在围绕历史报告继续研究
                </p>
                <p className="mt-1 text-xs leading-5" style={{ color: "#64748b" }}>
                  基础主题：{followUp.baseTopic}
                  {followUp.direction
                    ? ` · 补充方向：${followUp.direction}`
                    : " · 暂无指定补充方向"}
                </p>
              </div>
              {onClearFollowUp ? (
                <button
                  type="button"
                  onClick={onClearFollowUp}
                  className="rounded-full p-1 transition"
                  style={{ color: "#64748b", border: "1px solid #e3e8ee" }}
                  aria-label="取消 follow-up 关联"
                >
                  <X className="h-3 w-3" />
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        <div
          className="hidden rounded-full px-4 py-2 text-xs lg:flex lg:items-center lg:gap-2"
          style={{
            border: "1px solid #e3e8ee",
            color: "#533afd",
            background: "#f6f9fc",
          }}
        >
          <Sparkles className="h-4 w-4" />
          综述、证据与核验
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[2.4fr_1fr_1fr]">
        <label className="space-y-2">
          <span
            className="text-xs uppercase tracking-[0.24em]"
            style={{ color: "#64748b" }}
          >
            研究主题
          </span>
          <textarea
            value={formState.topic}
            rows={4}
            onChange={(event) =>
              setFormState((current) => ({ ...current, topic: event.target.value }))
            }
            className="w-full rounded-xl px-4 py-3 text-sm outline-none transition"
            style={{
              border: "1px solid #e3e8ee",
              color: "#0d253d",
              background: "#ffffff",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#533afd";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(83,58,253,0.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e3e8ee";
              e.currentTarget.style.boxShadow = "none";
            }}
            placeholder="例如：面向软件工程的自动文献综述"
          />
        </label>

        <label className="space-y-2">
          <span
            className="text-xs uppercase tracking-[0.24em]"
            style={{ color: "#64748b" }}
          >
            论文数量
          </span>
          <input
            type="number"
            min={1}
            max={10}
            value={formState.max_papers}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                max_papers: Number(event.target.value),
              }))
            }
            className="h-[58px] rounded-xl px-4 text-sm outline-none transition"
            style={{
              border: "1px solid #e3e8ee",
              color: "#0d253d",
              background: "#ffffff",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#533afd";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(83,58,253,0.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e3e8ee";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
        </label>

        <label className="space-y-2">
          <span
            className="text-xs uppercase tracking-[0.24em]"
            style={{ color: "#64748b" }}
          >
            全文论文数
          </span>
          <input
            type="number"
            min={0}
            max={5}
            value={formState.max_full_text_papers}
            onChange={(event) =>
              setFormState((current) => ({
                ...current,
                max_full_text_papers: Number(event.target.value),
              }))
            }
            className="h-[58px] rounded-xl px-4 text-sm outline-none transition"
            style={{
              border: "1px solid #e3e8ee",
              color: "#0d253d",
              background: "#ffffff",
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = "#533afd";
              e.currentTarget.style.boxShadow = "0 0 0 3px rgba(83,58,253,0.12)";
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = "#e3e8ee";
              e.currentTarget.style.boxShadow = "none";
            }}
          />
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        {[
          { key: "include_memory" as const, label: "启用记忆" },
          { key: "enable_full_text" as const, label: "正文解析" },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() =>
              setFormState((current) => ({
                ...current,
                [item.key]: !current[item.key],
              }))
            }
            className="rounded-full px-4 py-2 text-sm transition"
            style={{
              border: `1px solid ${formState[item.key] ? "#533afd" : "#e3e8ee"}`,
              background: formState[item.key] ? "#f6f9fc" : "#ffffff",
              color: formState[item.key] ? "#533afd" : "#64748b",
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between gap-4">
        <p className="text-xs leading-5" style={{ color: "#64748b" }}>
          提交后会请求后端 /api/v1/research，并返回当前研究任务的结构化结果。
        </p>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium text-white transition disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: "#533afd" }}
          onMouseEnter={(e) => {
            if (!e.currentTarget.disabled) e.currentTarget.style.background = "#4434d4";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#533afd";
          }}
        >
          {loading ? (
            <>
              <LoaderCircle className="h-4 w-4 animate-spin" />
              处理中
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              开始分析
            </>
          )}
        </button>
      </div>
    </form>
  );
}
