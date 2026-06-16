import { Activity, CheckCircle, XCircle, Loader } from "lucide-react";

interface Props {
  status: "idle" | "running" | "done" | "error";
  message?: string;
}

export default function StatusBar({ status, message }: Props) {
  const labels: Record<string, string> = {
    idle: "就绪",
    running: "正在执行任务…",
    done: "任务完成",
    error: "执行失败",
  };

  return (
    <div className={`status-bar ${status}`}>
      <span className={`status-dot ${status}`} />
      <span style={{ flex: 1 }}>{message || labels[status]}</span>
      {status === "running" && <Loader size={14} className="spin" />}
    </div>
  );
}
