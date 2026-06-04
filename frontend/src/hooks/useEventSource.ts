import { useCallback, useRef } from "react";
import { useResearchStore } from "@/store/researchStore";
import type { SSEEvent } from "@/types/research";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function useResearchStream() {
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback(async (request: Record<string, unknown>) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const { sseEvents } = useResearchStore.getState();
    useResearchStore.setState({
      sseEvents: [],
      sseConnected: true,
      sseError: null,
      sseFinalData: null,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/research/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

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
            const prev = useResearchStore.getState().sseEvents;
            const newEvents = [...prev, event];
            const finalData = event.event_type === "final_report" ? event.data ?? null : useResearchStore.getState().sseFinalData;
            useResearchStore.setState({
              sseEvents: newEvents,
              sseFinalData: finalData,
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
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    useResearchStore.setState({ sseConnected: false });
  }, []);

  const state = useResearchStore.getState();
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
    cancelStream,
    currentStage: events.length > 0 ? events[events.length - 1] : null,
    progress: events.length > 0 ? (events[events.length - 1].progress ?? 0) : 0,
  };
}
