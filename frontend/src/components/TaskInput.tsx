import { useState, FormEvent } from "react";
import { createTask } from "../api/client";

interface Props {
  onTaskCreated: (taskId: string) => void;
  disabled: boolean;
}

const EXAMPLES = [
  "在百度搜索今天的天气",
  "Find the price of iPhone 15 on Amazon",
  "打开 GitHub Trending 页面，列出前3个项目名称",
];

export default function TaskInput({ onTaskCreated, disabled }: Props) {
  const [task, setTask] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!task.trim() || disabled) return;

    setLoading(true);
    setError(null);

    try {
      const result = await createTask(task.trim());
      onTaskCreated(result.task_id);
    } catch (err: any) {
      setError(err.message || "Failed to create task");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.card}>
      <h2 style={styles.heading}>📝 输入你的任务</h2>
      <form onSubmit={handleSubmit} style={styles.form}>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="描述你想让浏览器帮你做什么...&#10;例如: 在京东搜索机械键盘，列出前5个的价格"
          style={styles.textarea}
          rows={4}
          disabled={disabled || loading}
        />
        <div style={styles.actions}>
          <button
            type="submit"
            disabled={disabled || loading || !task.trim()}
            style={{
              ...styles.button,
              opacity: disabled || loading || !task.trim() ? 0.5 : 1,
            }}
          >
            {loading ? "⏳ 提交中..." : "🚀 开始执行"}
          </button>
        </div>
        {error && <p style={styles.error}>❌ {error}</p>}
      </form>
      <div style={styles.examples}>
        <span style={styles.examplesLabel}>快速示例：</span>
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            style={styles.exampleBtn}
            onClick={() => setTask(ex)}
            disabled={disabled}
          >
            {ex}
          </button>
        ))}
      </div>
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
    marginBottom: 12,
    color: "#f0f6fc",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  textarea: {
    width: "100%",
    padding: 12,
    background: "#0d1117",
    border: "1px solid #30363d",
    borderRadius: 6,
    color: "#c9d1d9",
    fontSize: 14,
    fontFamily: "inherit",
    resize: "vertical",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
  },
  button: {
    padding: "10px 24px",
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  error: {
    color: "#f85149",
    fontSize: 13,
  },
  examples: {
    marginTop: 16,
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    alignItems: "center",
  },
  examplesLabel: {
    fontSize: 12,
    color: "#8b949e",
  },
  exampleBtn: {
    padding: "4px 10px",
    background: "#21262d",
    border: "1px solid #30363d",
    borderRadius: 4,
    color: "#58a6ff",
    fontSize: 12,
    cursor: "pointer",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: 280,
  },
};
