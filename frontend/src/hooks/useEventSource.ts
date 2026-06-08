import { useCallback, useRef } from "react";
import { useResearchStore } from "@/store/researchStore";
import type { SSEEvent } from "@/types/research";
import { normalizeReport } from "@/utils/normalizeReport";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

type StartOptions = {
  resumeTaskId?: string;
  resumeCursor?: number;
};

export function useResearchStream() {
  const abortRef = useRef<AbortController | null>(null);

  const consumeStream = useCallback(
    async (url: string, init: RequestInit, opts: StartOptions) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // 续连模式不重置 sseEvents，仅清错；首连模式清空旧进度
      if (opts.resumeTaskId) {
        useResearchStore.setState({ sseConnected: true, sseError: null, sseFinalData: null });
      } else {
        useResearchStore.setState({
          sseEvents: [],
          sseConnected: true,
          sseError: null,
          sseFinalData: null,
          activeTaskId: null,
          activeTaskCursor: 0,
        });
      }

      try {
        const response = await fetch(url, { ...init, signal: controller.signal });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          useResearchStore.setState({
            sseConnected: false,
            sseError: errorData.detail || `HTTP ${response.status}`,
          });
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          useResearchStore.setState({ sseConnected: false, sseError: "No response body" });
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;
            try {
              const event: SSEEvent = JSON.parse(raw);
              // 处理 task_created：保存 task_id 以便刷新后续连
              if (event.event_type === "task_created") {
                const data = (event.data as Record<string, unknown> | null) ?? {};
                const taskId = typeof data.task_id === "string" ? data.task_id : null;
                if (taskId) {
                  useResearchStore.setState({ activeTaskId: taskId, activeTaskCursor: 0 });
                }
                continue;
              }
              // 心跳事件仅用于保活长连接，不计入 sseEvents 也不影响 UI
              if (event.event_type === "heartbeat") {
                continue;
              }
              const prev = useResearchStore.getState().sseEvents;
              const newEvents = [...prev, event];
              const finalData =
                event.event_type === "final_report"
                  ? normalizeReport(event.data as Parameters<typeof normalizeReport>[0])
                  : useResearchStore.getState().sseFinalData;
              useResearchStore.setState({
                sseEvents: newEvents,
                sseFinalData: finalData,
                activeTaskCursor: newEvents.length,
                sseConnected: event.event_type !== "final_report" && event.event_type !== "error",
                sseError: event.event_type === "error" ? event.message : null,
              });
            } catch {
              // skip malformed events
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        useResearchStore.setState({
          sseConnected: false,
          sseError: err instanceof Error ? err.message : "Stream error",
        });
      }
    },
    [],
  );

  const startStream = useCallback(
    async (request: Record<string, unknown>) => {
      await consumeStream(
        `${API_BASE_URL}/api/v1/research/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        },
        {},
      );
    },
    [consumeStream],
  );

  const resumeStream = useCallback(
    async (taskId: string, cursor: number) => {
      const safeCursor = Number.isFinite(cursor) && cursor > 0 ? Math.floor(cursor) : 0;
      const url = `${API_BASE_URL}/api/v1/research/tasks/${encodeURIComponent(taskId)}/stream?cursor=${safeCursor}`;
      await consumeStream(url, { method: "GET" }, { resumeTaskId: taskId, resumeCursor: cursor });
    },
    [consumeStream],
  );

  const cancelStream = useCallback(async () => {
    const taskId = useResearchStore.getState().activeTaskId;
    if (taskId) {
      try {
        await fetch(`${API_BASE_URL}/api/v1/research/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
      } catch {
        // 取消失败时仅断开本地连接
      }
    }
    abortRef.current?.abort();
    useResearchStore.setState({ sseConnected: false });
  }, []);

  const events = useResearchStore((s) => s.sseEvents);
  const isConnected = useResearchStore((s) => s.sseConnected);
  const error = useResearchStore((s) => s.sseError);
  const finalData = useResearchStore((s) => s.sseFinalData);

  return {
    events,
    isConnected,
    error,
    finalData,
    startStream,
    resumeStream,
    cancelStream,
    currentStage: events.length > 0 ? events[events.length - 1] : null,
    progress: events.length > 0 ? (events[events.length - 1].progress ?? 0) : 0,
  };
}
