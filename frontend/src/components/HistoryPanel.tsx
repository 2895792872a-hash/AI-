import { useState, useEffect, useMemo } from "react";
import { CheckCircle, XCircle } from "lucide-react";

interface HistoryItem {
  task: string; summary: string; success: boolean; timestamp: string;
}

export default function HistoryPanel({ refresh }: { refresh: number }) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "success" | "fail">("all");

  useEffect(() => {
    setLoading(true);
    fetch("/api/history?limit=50")
      .then((r) => r.json())
      .then((d) => setItems(d.history || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [refresh]);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (filter === "success" && !item.success) return false;
      if (filter === "fail" && item.success) return false;
      if (search && !item.task.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [items, search, filter]);

  return (
    <div className="panel">
      <div className="panel-toolbar">
        <input
          className="search-input"
          placeholder="搜索历史任务…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {(["all", "success", "fail"] as const).map((f) => (
          <button
            key={f}
            className={`filter-btn${filter === f ? " active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "全部" : f === "success" ? "成功" : "失败"}
          </button>
        ))}
      </div>

      {loading ? (
        <div>
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton skeleton-line" style={{ width: `${80 + i * 10}%` }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel-empty">
          {search ? "没有匹配的任务" : "暂无历史记录"}
        </div>
      ) : (
        filtered.map((item, i) => (
          <div key={i} className="panel-item">
            <div className="panel-item-header">
              {item.success ? (
                <CheckCircle size={14} color="var(--success)" />
              ) : (
                <XCircle size={14} color="var(--error)" />
              )}
              <span className="panel-item-task">{item.task}</span>
              <span className="panel-item-time">
                {item.timestamp?.slice(0, 16).replace("T", " ")}
              </span>
            </div>
            {item.summary && (
              <div className="panel-item-result">{item.summary.slice(0, 150)}</div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
