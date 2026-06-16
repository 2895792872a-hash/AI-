import { useState, FormEvent } from "react";
import { Send, Loader } from "lucide-react";
import { createTask } from "../api/client";
import { SSEEvent } from "../hooks/useSSE";

interface Props {
  onTaskCreated: (taskId: string) => void;
  onEvents: (events: SSEEvent[]) => void;
  onDone: (event: SSEEvent) => void;
  onError: (event: SSEEvent) => void;
  onRunning: (running: boolean) => void;
  disabled: boolean;
}

export default function TaskInput({
  onTaskCreated, onEvents, onDone, onError, onRunning, disabled,
}: Props) {
  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (text: string) => {
    if (!text.trim() || disabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await createTask(text.trim());
      onTaskCreated(result.task_id);
      const es = new EventSource(`/api/tasks/${result.task_id}/stream`);
      onRunning(true);
      const events: SSEEvent[] = [];
      ["stage_change", "step_start", "step_complete", "step_error", "screenshot_update"].forEach((t) => {
        es.addEventListener(t, (e: MessageEvent) => {
          try { const d: SSEEvent = JSON.parse(e.data); d.type = t; events.push(d); onEvents([...events]); } catch {}
        });
      });
      es.addEventListener("done", (e: MessageEvent) => {
        try { const d: SSEEvent = JSON.parse(e.data); d.type = "done"; onDone(d); } catch {}
        es.close();
      });
      es.addEventListener("error", (e: MessageEvent) => {
        try { const d: SSEEvent = JSON.parse(e.data); d.type = "error"; onError(d); } catch {}
        es.close();
      });
    } catch (err: any) {
      setError(err.message || "请求失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(task);
  };

  return (
    <div className="task-input">
      <form onSubmit={handleSubmit}>
        <div className="input-wrap">
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="描述你想让浏览器做什么…"
            className="task-textarea"
            rows={2}
            disabled={disabled}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(task);
              }
            }}
          />
          <button type="submit" disabled={disabled || loading || !task.trim()} className="submit-btn">
            {loading ? <Loader size={18} className="spin" /> : <Send size={18} />}
          </button>
        </div>
      </form>
      {error && <p className="task-error">{error}</p>}
    </div>
  );
}
