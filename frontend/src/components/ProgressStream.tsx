import { motion, AnimatePresence } from "framer-motion";
import { Brain, Globe, Database, FileText, CheckCircle, Circle, XCircle, Clock } from "lucide-react";
import { SSEEvent } from "../hooks/useSSE";

interface Props {
  events: SSEEvent[];
}

const STAGES = [
  { key: "parsing", label: "解析", Icon: Brain },
  { key: "operating", label: "执行", Icon: Globe },
  { key: "extracting", label: "提取", Icon: Database },
  { key: "summarizing", label: "总结", Icon: FileText },
];

export default function ProgressStream({ events }: Props) {
  const stageEvents = events.filter((e) => e.type === "stage_change");
  const currentStage = stageEvents.slice(-1)[0]?.stage || "parsing";
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  const stepEvents = events.filter(
    (e) => e.type === "step_start" || e.type === "step_complete" || e.type === "step_error"
  );

  return (
    <div className="progress-card">
      <div className="stage-row">
        {STAGES.map(({ key, label, Icon }, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div key={key} className={`stage-item${done ? " done" : ""}`}>
              <div className={`stage-circle${active ? " active" : ""}${done ? " done" : ""}`}>
                {done ? (
                  <CheckCircle size={16} />
                ) : active ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                  >
                    <Icon size={16} />
                  </motion.div>
                ) : (
                  <Icon size={16} />
                )}
              </div>
              <span className={`stage-label${active ? " active" : ""}${done ? " done" : ""}`}>
                {label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="step-list">
        <AnimatePresence initial={false}>
          {stepEvents.map((ev, i) => {
            const isStart = ev.type === "step_start";
            const isDone = ev.type === "step_complete";
            const isErr = ev.type === "step_error";

            return (
              <motion.div
                key={`${ev.type}-${i}`}
                className="step-row"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
              >
                <span className="step-icon">
                  {isStart && <Circle size={14} color="var(--text-muted)" />}
                  {isDone && <CheckCircle size={14} color="var(--success)" />}
                  {isErr && <XCircle size={14} color="var(--error)" />}
                </span>
                <div className="step-body">
                  <div className="step-action" style={{ color: isErr ? "var(--error)" : isDone ? "var(--success)" : undefined }}>
                    {ev.action}
                  </div>
                  {ev.description && <div className="step-desc">{ev.description}</div>}
                  {ev.error && <div className="step-desc" style={{ color: "var(--error)" }}>{ev.error.slice(0, 80)}</div>}
                </div>
                <div className="step-meta">
                  <Clock size={10} style={{ display: "inline", marginRight: 2 }} />
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
