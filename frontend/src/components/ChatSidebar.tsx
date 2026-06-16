import { useState, useEffect } from "react";
import { Plus, Trash2, MessageSquare } from "lucide-react";

interface Session {
  id: string;
  title: string;
  updated_at: string;
}

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refresh: number;
}

export default function ChatSidebar({ activeId, onSelect, onNew, refresh }: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);

  const load = () => {
    fetch("/api/chat/sessions")
      .then((r) => r.json())
      .then((d) => setSessions(d.sessions || []))
      .catch(() => {});
  };

  useEffect(() => { load(); }, [refresh]);

  const remove = async (id: string) => {
    if (!window.confirm("确定要删除这个对话吗？")) return;
    await fetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
    load();
    if (activeId === id) onNew();
  };

  const fmtTime = (ts: string) => {
    try {
      const d = new Date(ts);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      if (diff < 86400000) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
      return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
    } catch { return ""; }
  };

  return (
    <div className="chat-sidebar">
      <button className="new-chat-btn" onClick={onNew}>
        <Plus size={16} />
        <span>新建对话</span>
      </button>

      <div className="chat-session-list">
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`chat-session-item${s.id === activeId ? " active" : ""}`}
            onClick={() => onSelect(s.id)}
          >
            <MessageSquare size={14} className="session-icon" />
            <div className="session-info">
              <div className="session-title">{s.title}</div>
              <div className="session-time">{fmtTime(s.updated_at)}</div>
            </div>
            <button
              className="session-delete"
              onClick={(e) => { e.stopPropagation(); remove(s.id); }}
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}
        {sessions.length === 0 && (
          <div className="chat-sidebar-empty">暂无对话，点击上方按钮开始</div>
        )}
      </div>
    </div>
  );
}
