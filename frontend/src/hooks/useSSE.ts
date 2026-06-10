import { useState, useEffect, useRef } from "react";

export interface SSEEvent {
  type: string;
  task_id?: string;
  stage?: string;
  progress_pct?: number;
  message?: string;
  step_id?: number;
  action?: string;
  description?: string;
  result_summary?: string;
  summary?: string;
  total_steps?: number;
  success_count?: number;
  fail_count?: number;
  error?: string;
  stage_failed?: string;
  data?: any;
}

export function useSSE(taskId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState<SSEEvent | null>(null);
  const [errorEvent, setErrorEvent] = useState<SSEEvent | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!taskId) return;

    // Reset state for new task
    setEvents([]);
    setConnected(false);
    setDone(null);
    setErrorEvent(null);

    const url = `/api/tasks/${taskId}/stream`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => setConnected(true);

    es.addEventListener("connected", (e) => {
      setConnected(true);
    });

    const eventTypes = [
      "stage_change", "step_start", "step_complete",
      "step_error", "extracted_data", "done", "error",
    ];

    eventTypes.forEach((type) => {
      es.addEventListener(type, (e: MessageEvent) => {
        try {
          const data: SSEEvent = JSON.parse(e.data);
          data.type = type;
          setEvents((prev) => [...prev, data]);

          if (type === "done") {
            setDone(data);
            es.close();
          }
          if (type === "error") {
            setErrorEvent(data);
            es.close();
          }
        } catch {
          // Ignore parse errors on individual events
        }
      });
    });

    es.onerror = () => {
      // EventSource will auto-reconnect; if the stream is closed
      // intentionally (done/error), it was already closed above.
      if (es.readyState === EventSource.CLOSED) {
        es.close();
      }
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [taskId]);

  return { events, connected, done, errorEvent };
}
