import type {
  ReportArchiveSummary,
  ResearchReport,
  ResearchRequest,
  TrendAnalysisResult,
  PaperRecommendation,
} from "@/types/research";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ResearchRequestError extends Error {
  title: string;
  detail: string;
  suggestion: string;

  constructor(title: string, detail: string, suggestion: string) {
    super(detail);
    this.name = "ResearchRequestError";
    this.title = title;
    this.detail = detail;
    this.suggestion = suggestion;
  }
}

type ErrorResponsePayload = {
  error_code?: string;
  title?: string;
  detail?: string;
  suggestion?: string;
};

function normalizeErrorText(message: string) {
  return message.trim() || "研究任务请求失败。";
}

async function parseErrorPayload(response: Response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as ErrorResponsePayload;
    return {
      title: payload.title?.trim() || "",
      detail: payload.detail?.trim() || "",
      suggestion: payload.suggestion?.trim() || "",
    };
  }
  const message = await response.text();
  return { title: "", detail: message.trim(), suggestion: "" };
}

function buildResponseError(
  status: number,
  payload: { title?: string; detail?: string; suggestion?: string },
) {
  const normalizedTitle = payload.title?.trim() || "";
  const normalizedMessage = normalizeErrorText(payload.detail || "");
  const normalizedSuggestion = payload.suggestion?.trim() || "";

  if (normalizedTitle) {
    return new ResearchRequestError(normalizedTitle, normalizedMessage, normalizedSuggestion || "请根据后端提示检查配置与服务状态后重试。");
  }
  if (status === 400) {
    return new ResearchRequestError("请求参数无效", normalizedMessage, "请检查研究主题、论文数量和全文解析参数后重新提交。");
  }
  if (status === 404) {
    return new ResearchRequestError("后端接口不可用", "未找到对应的接口。", "请确认 FastAPI 服务已启动。");
  }
  if (status >= 500) {
    return new ResearchRequestError("研究任务执行失败", normalizedMessage === "Internal Server Error" ? "后端已收到请求，但研究流程执行过程中发生错误。" : normalizedMessage, "请检查后端日志和模型配置。");
  }
  return new ResearchRequestError("请求未完成", normalizedMessage, "请确认后端服务状态后重试。");
}

async function requestApiJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    throw new ResearchRequestError("无法连接后端服务", error instanceof Error ? error.message : "请求未能发送到后端服务。", "请确认 FastAPI 服务已启动。");
  }
  if (!response.ok) {
    const payload = await parseErrorPayload(response);
    throw buildResponseError(response.status, payload);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// ============ Research API ============

export async function requestResearchReport(payload: ResearchRequest): Promise<ResearchReport> {
  return requestApiJson<ResearchReport>("/api/v1/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function requestReportHistory(limit = 12): Promise<ReportArchiveSummary[]> {
  return requestApiJson<ReportArchiveSummary[]>(`/api/v1/reports?limit=${limit}`);
}

export async function requestArchivedReport(reportId: string): Promise<ResearchReport> {
  return requestApiJson<ResearchReport>(`/api/v1/reports/${encodeURIComponent(reportId)}`);
}

export async function deleteArchivedReport(reportId: string): Promise<void> {
  await requestApiJson<void>(`/api/v1/reports/${encodeURIComponent(reportId)}`, { method: "DELETE" });
}

// ============ Trend Analysis API ============

export async function requestTrendAnalysis(topic: string, years = 5): Promise<TrendAnalysisResult> {
  return requestApiJson<TrendAnalysisResult>(`/api/v1/trends/${encodeURIComponent(topic)}?years=${years}`);
}

// ============ Recommendation API ============

export async function requestRecommendations(paperId: string, limit = 10): Promise<PaperRecommendation[]> {
  return requestApiJson<PaperRecommendation[]>(`/api/v1/recommendations/${encodeURIComponent(paperId)}?limit=${limit}`);
}

export async function requestTopicRecommendations(topic: string, limit = 10): Promise<PaperRecommendation[]> {
  return requestApiJson<PaperRecommendation[]>(`/api/v1/recommendations/topic?topic=${encodeURIComponent(topic)}&limit=${limit}`);
}
