import { create } from "zustand";

import type {
  ReportArchiveSummary,
  ResearchReport,
  ResearchRequest,
  TrendAnalysisResult,
  PaperRecommendation,
  SSEEvent,
} from "@/types/research";
import {
  ResearchRequestError,
  requestArchivedReport,
  requestReportHistory,
  requestTopicRecommendations,
} from "@/utils/api";

type RequestStatus = "idle" | "loading" | "success" | "error";
type HistoryStatus = "idle" | "loading" | "success" | "error";
type ErrorState = {
  title: string;
  detail: string;
  suggestion: string;
};

type FollowUpContext = {
  baseTopic: string;
  direction: string;
  sourceReportId: string | null;
};

type ResearchStore = {
  requestStatus: RequestStatus;
  report: ResearchReport | null;
  activeReportId: string | null;
  errorState: ErrorState | null;
  lastRequest: ResearchRequest | null;
  historyStatus: HistoryStatus;
  reportHistory: ReportArchiveSummary[];
  pendingFollowUp: FollowUpContext | null;
  compareSelection: string[];
  // Trends
  trendData: TrendAnalysisResult | null;
  trendLoading: boolean;
  // Recommendations
  recommendations: PaperRecommendation[];
  recommendationLoading: boolean;
  // SSE streaming state (persisted so navigation doesn't lose progress)
  sseEvents: SSEEvent[];
  sseConnected: boolean;
  sseError: string | null;
  sseFinalData: Record<string, unknown> | null;
  // Actions
  runResearch: (payload: ResearchRequest) => Promise<void>;
  fetchReportHistory: () => Promise<void>;
  loadArchivedReport: (reportId: string) => Promise<void>;
  prepareFollowUp: (params: {
    baseRequest: ResearchRequest;
    direction: string;
    sourceReportId: string | null;
  }) => void;
  clearFollowUp: () => void;
  toggleCompareSelection: (reportId: string) => void;
  clearCompareSelection: () => void;
  clearError: () => void;
  setReportFromStream: (report: ResearchReport) => void;
  fetchRecommendations: (topic: string) => Promise<void>;
};

export const useResearchStore = create<ResearchStore>((set) => ({
  requestStatus: "idle",
  report: null,
  activeReportId: null,
  errorState: null,
  lastRequest: null,
  historyStatus: "idle",
  reportHistory: [],
  pendingFollowUp: null,
  compareSelection: [],
  trendData: null,
  trendLoading: false,
  recommendations: [],
  recommendationLoading: false,
  sseEvents: [],
  sseConnected: false,
  sseError: null,
  sseFinalData: null,

  runResearch: async (payload) => {
    set({
      requestStatus: "loading",
      errorState: null,
      lastRequest: payload,
      pendingFollowUp: null,
    });
    try {
      // Use streaming endpoint
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
      const response = await fetch(`${API_BASE_URL}/api/v1/research/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ResearchRequestError(
          errorData.title || "请求失败",
          errorData.detail || `HTTP ${response.status}`,
          errorData.suggestion || "请检查后端服务。",
        );
      }

      // For non-streaming fallback, try regular endpoint
      // The SSE stream is handled by useResearchStream hook
      // This path is used as fallback
    } catch (error) {
      const normalizedError =
        error instanceof ResearchRequestError
          ? { title: error.title, detail: error.detail, suggestion: error.suggestion }
          : {
              title: "研究任务执行失败",
              detail: error instanceof Error ? error.message : "研究报告请求失败",
              suggestion: "请检查后端服务状态与模型配置后重试。",
            };
      set({ requestStatus: "error", errorState: normalizedError });
    }
  },

  fetchReportHistory: async () => {
    set({ historyStatus: "loading" });
    try {
      const reportHistory = await requestReportHistory();
      set({ historyStatus: "success", reportHistory });
    } catch (error) {
      const normalizedError =
        error instanceof ResearchRequestError
          ? { title: error.title, detail: error.detail, suggestion: error.suggestion }
          : {
              title: "历史记录读取失败",
              detail: error instanceof Error ? error.message : "历史记录读取失败",
              suggestion: "请检查后端服务状态后重试。",
            };
      set({ historyStatus: "error", errorState: normalizedError });
    }
  },

  loadArchivedReport: async (reportId) => {
    set({ requestStatus: "loading", errorState: null });
    try {
      const report = await requestArchivedReport(reportId);
      set({
        report,
        activeReportId: reportId,
        requestStatus: "success",
        lastRequest: report.request,
      });
    } catch (error) {
      const normalizedError =
        error instanceof ResearchRequestError
          ? { title: error.title, detail: error.detail, suggestion: error.suggestion }
          : {
              title: "历史报告读取失败",
              detail: error instanceof Error ? error.message : "历史报告读取失败",
              suggestion: "请刷新历史记录后重试。",
            };
      set({ requestStatus: "error", errorState: normalizedError });
    }
  },

  clearError: () => set({ errorState: null }),

  setReportFromStream: (report: ResearchReport) => {
    set({
      report,
      activeReportId: null,
      requestStatus: "success",
      lastRequest: report.request,
    });
  },

  prepareFollowUp: ({ baseRequest, direction, sourceReportId }) => {
    const trimmedDirection = direction.trim();
    const composedTopic = trimmedDirection
      ? `${baseRequest.topic}（补充方向：${trimmedDirection}）`
      : baseRequest.topic;
    set({
      lastRequest: { ...baseRequest, topic: composedTopic },
      pendingFollowUp: { baseTopic: baseRequest.topic, direction: trimmedDirection, sourceReportId },
    });
  },

  clearFollowUp: () => set({ pendingFollowUp: null }),

  toggleCompareSelection: (reportId) =>
    set((state) => {
      const exists = state.compareSelection.includes(reportId);
      if (exists) {
        return { compareSelection: state.compareSelection.filter((id) => id !== reportId) };
      }
      const limited = [...state.compareSelection, reportId].slice(-3);
      return { compareSelection: limited };
    }),

  clearCompareSelection: () => set({ compareSelection: [] }),

  fetchRecommendations: async (topic) => {
    set({ recommendationLoading: true });
    try {
      const recommendations = await requestTopicRecommendations(topic);
      set({ recommendations, recommendationLoading: false });
    } catch {
      set({ recommendationLoading: false });
    }
  },
}));
