import { useEffect } from "react";
import { SSEEvent, useSSE } from "../hooks/useSSE";

interface Props {
  taskId: string;
  onEvents: (events: SSEEvent[]) => void;
  onDone: (event: SSEEvent) => void;
  onError: (event: SSEEvent) => void;
  onRunning: (running: boolean) => void;
}

const STAGE_LABELS: Record<string, string> = {
  parsing: "🧠 任务解析",
  operating: "🌐 浏览器操作",
  extracting: "📊 信息提取",
  summarizing: "📝 结果总结",
  done: "✅ 完成",
  error: "❌ 出错",
};

const STAGE_ORDER = ["parsing", "operating", "extracting", "summarizing", "done"];

export default function ProgressStream({ taskId, onEvents, onDone, onError, onRunning }: Props) {
  const { events, connected, done, errorEvent } = useSSE(taskId);

  useEffect(() => {
    onEvents(events);
  }, [events]);

  useEffect(() => {
    if (done) { onDone(done); onRunning(false); }
  }, [done]);

  useEffect(() => {
    if (errorEvent) { onError(errorEvent); onRunning(false); }
  }, [errorEvent]);

  useEffect(() => {
    onRunning(true);
  }, []);

  const currentStage = events
    .filter((e) => e.type === "stage_change")
    .slice(-1)[0]?.stage || "parsing";

  const stepEvents = events.filter(
    (e) => e.type === "step_start" || e.type === "step_complete" || e.type === "step_error"
  );

  const stageIdx = STAGE_ORDER.indexOf(currentStage);

  return (
    <div style={styles.card}>
      <h2 style={styles.heading}>
        {connected ? "🟢 实时执行中" : "⏳ 连接中..."}
      </h2>

      {/* Stage progress dots */}
      <div style={styles.stages}>
        {STAGE_ORDER.slice(0, -1).map((stage, i) => (
          <div key={stage} style={styles.stageItem}>
            <div
              style={{
                ...styles.dot,
                background: i < stageIdx ? "#238636" : i === stageIdx ? "#58a6ff" : "#30363d",
                borderColor: i <= stageIdx ? "#58a6ff" : "#30363d",
              }}
            >
              {i < stageIdx ? "✓" : i === stageIdx ? "●" : ""}
            </div>
            <span
              style={{
                ...styles.stageLabel,
                color: i <= stageIdx ? "#f0f6fc" : "#484f58",
              }}
            >
              {STAGE_LABELS[stage]}
            </span>
            {i < 3 && <div style={{
              ...styles.connector,
              background: i < stageIdx ? "#238636" : "#30363d",
            }} />}
          </div>
        ))}
      </div>

      {/* Step list */}
      {stepEvents.length > 0 && (
        <div style={styles.stepList}>
          <h3 style={styles.stepHeading}>执行步骤</h3>
          {stepEvents.map((ev, i) => (
            <div key={i} style={styles.stepItem}>
              <span style={styles.stepIcon}>
                {ev.type === "step_start" ? "⏳"
                  : ev.type === "step_complete" ? "✅"
                  : "❌"}
              </span>
              <span style={styles.stepText}>
                {ev.type === "step_start"
                  ? `[${ev.action}] ${ev.description || ""}`
                  : ev.type === "step_complete"
                  ? `[${ev.action}] 完成 — ${ev.result_summary || ""}`
                  : `[${ev.action}] 失败 — ${ev.error || ""}`}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Current stage indicator */}
      {!done && !errorEvent && (
        <p style={styles.currentStage}>
          {STAGE_LABELS[currentStage] || currentStage}...
        </p>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: 8,
    padding: 20,
  },
  heading: {
    fontSize: 18,
    marginBottom: 16,
    color: "#f0f6fc",
  },
  stages: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
    gap: 0,
  },
  stageItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    position: "relative",
  },
  dot: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 12,
    color: "#fff",
    border: "2px solid",
    fontWeight: 700,
  },
  stageLabel: {
    fontSize: 11,
    marginTop: 4,
    whiteSpace: "nowrap",
  },
  connector: {
    position: "absolute",
    top: 14,
    left: 28,
    width: 40,
    height: 2,
  },
  stepList: {
    borderTop: "1px solid #21262d",
    paddingTop: 12,
    maxHeight: 300,
    overflowY: "auto",
  },
  stepHeading: {
    fontSize: 13,
    color: "#8b949e",
    marginBottom: 8,
  },
  stepItem: {
    display: "flex",
    gap: 8,
    padding: "4px 0",
    fontSize: 13,
    color: "#c9d1d9",
  },
  stepIcon: {
    flexShrink: 0,
    width: 20,
  },
  stepText: {
    wordBreak: "break-all",
  },
  currentStage: {
    fontSize: 13,
    color: "#58a6ff",
    textAlign: "center",
    animation: "pulse 1.5s infinite",
  },
};
