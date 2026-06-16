import { useState, useEffect, FormEvent } from "react";
import { Clock, Trash2, Plus, CheckCircle, XCircle, Copy, Download, Check } from "lucide-react";

interface ScheduleItem {
  id: string; user_task: string; interval: string; enabled: boolean;
  last_run: string | null; last_result: string | null; last_success: boolean | null;
  history?: { time: string; result: string; success: boolean }[];
}

export default function SchedulePanel({ refresh, onRefresh }: { refresh: number; onRefresh: () => void }) {
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [task, setTask] = useState("");
  const [interval, setInterval] = useState("daily");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fmtLocal = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch { return ts?.slice(0, 16) || ""; }
  };

  const load = () => {
    fetch("/api/schedules")
      .then((r) => r.json())
      .then((d) => setSchedules(d.schedules || []))
      .catch(() => {});
  };
  useEffect(() => { load(); }, [refresh]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!task.trim() || busy) return;
    setBusy(true);
    try {
      await fetch("/api/schedules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_task: task.trim(), interval }) });
      setTask(""); load(); onRefresh();
    } catch {} finally { setBusy(false); }
  };

  const remove = async (id: string) => {
    await fetch(`/api/schedules/${id}`, { method: "DELETE" });
    load(); onRefresh();
  };

  return (
    <div>
      <form onSubmit={add} className="task-input" style={{ marginBottom: 16, flexDirection: "row" }}>
        <input value={task} onChange={(e) => setTask(e.target.value)}
          placeholder="每天检查京东购物车…" disabled={busy}
          className="search-input" style={{ flex: 1 }} />
        <select value={interval} onChange={(e) => setInterval(e.target.value)}
          style={{ padding: "8px 10px", background: "var(--bg-raised)", border: "1px solid var(--border)", borderRadius: "var(--radius)", color: "var(--text-primary)", fontSize: 12, fontFamily: "var(--font)" }}>
          <option value="hourly">每小时</option><option value="daily">每天</option><option value="weekly">每周</option>
        </select>
        <button type="submit" disabled={busy || !task.trim()} className="submit-btn" style={{ borderRadius: "var(--radius)" }}>
          <Plus size={18} />
        </button>
      </form>

      {!schedules.length && <div className="panel"><div className="panel-empty">暂无定时任务</div></div>}

      {schedules.length > 0 && (
        <div className="panel">
          {schedules.map((s) => (
            <div key={s.id} className="panel-item" style={{ cursor: "pointer" }} onClick={() => setExpanded(expanded === s.id ? null : s.id)}>
              <div className="panel-item-header">
                <Clock size={13} color="var(--accent)" />
                <span style={{ fontSize: 11, color: "var(--accent)", background: "var(--accent-dim)", padding: "2px 8px", borderRadius: 4, whiteSpace: "nowrap" }}>
                  {s.interval === "hourly" ? "每时" : s.interval === "daily" ? "每天" : "每周"}
                </span>
                <span className="panel-item-task">{s.user_task}</span>
                <button onClick={(e) => { e.stopPropagation(); remove(s.id); }} style={{ background: "transparent", border: "none", cursor: "pointer", padding: 4 }}>
                  <Trash2 size={14} color="var(--text-muted)" />
                </button>
              </div>
              {s.last_run && (
                <div style={{ marginTop: 4, borderTop: "1px solid var(--border)", paddingTop: 4 }}>
                  {s.last_success ? <CheckCircle size={11} color="var(--success)" style={{ display: "inline" }} /> : <XCircle size={11} color="var(--error)" style={{ display: "inline" }} />}
                  <span style={{ fontSize: 11 }}> 最近: {fmtLocal(s.last_run || "")}</span>
                  <ScheduleResult text={s.last_result || ""} />
                </div>
              )}
              {/* History detail */}
              {expanded === s.id && (
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>运行历史</div>
                  {(s.history || []).length === 0 && !s.last_run && (
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>暂未运行</div>
                  )}
                  {((s.history || []).length === 0 && s.last_run) && (
                    <div style={{ marginTop: 4, borderTop: "1px solid var(--border)", paddingTop: 4 }}>
                      {s.last_success ? <CheckCircle size={11} color="var(--success)" style={{ display: "inline" }} /> : <XCircle size={11} color="var(--error)" style={{ display: "inline" }} />}
                      <span style={{ fontSize: 11 }}> {fmtLocal(s.last_run || "")}</span>
                      <ScheduleResult text={s.last_result || ""} />
                    </div>
                  )}
                  {(s.history || []).slice().reverse().map((h, i) => (
                    <div key={i} style={{ marginTop: 4, borderTop: "1px solid var(--border)", paddingTop: 4 }}>
                      {h.success ? <CheckCircle size={10} color="var(--success)" style={{ display: "inline" }} /> : <XCircle size={10} color="var(--error)" style={{ display: "inline" }} />}
                      <span style={{ fontSize: 11 }}> {fmtLocal(h.time || "")}</span>
                      <ScheduleResult text={h.result || ""} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ScheduleResult({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };
  const handleDownload = () => {
    const blob = new Blob([`# 定时任务结果\n\n${text}\n\n---\n*由 AI Browser Agent 生成*`], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `schedule-result-${new Date().toISOString().slice(0,10)}.md`;
    a.click(); URL.revokeObjectURL(url);
  };
  return (
    <div>
      <div style={{ fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word", marginTop: 4, color: "var(--text-secondary)", lineHeight: 1.6 }}>{text}</div>
      <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
        <button className="action-btn" onClick={handleCopy} title="复制">
          {copied ? <Check size={10} /> : <Copy size={10} />}
          <span>{copied ? "已复制" : "复制"}</span>
        </button>
        <button className="action-btn" onClick={handleDownload} title="下载Markdown">
          <Download size={10} />
          <span>下载</span>
        </button>
      </div>
    </div>
  );
}
