import { SSEEvent } from "../hooks/useSSE";

interface Props {
  event: SSEEvent;
  events: SSEEvent[];
}

export default function ResultDisplay({ event, events }: Props) {
  const isError = event.type === "error";
  const isDone = event.type === "done";

  const totalSteps = event.total_steps || 0;
  const successCount = event.success_count || 0;
  const failCount = event.fail_count || 0;

  return (
    <div style={{
      ...styles.card,
      borderColor: isError ? "#f85149" : "#238636",
    }}>
      <h2 style={{
        ...styles.heading,
        color: isError ? "#f85149" : "#3fb950",
      }}>
        {isError ? "❌ 执行失败" : "✅ 任务完成"}
      </h2>

      {/* Summary */}
      {event.summary && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>结果</h3>
          <p style={styles.summary}>{event.summary}</p>
        </div>
      )}

      {/* Error */}
      {event.error && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>错误信息</h3>
          <pre style={styles.errorText}>{event.error}</pre>
        </div>
      )}

      {/* Stats */}
      {isDone && (
        <div style={styles.stats}>
          <div style={styles.stat}>
            <span style={styles.statValue}>{totalSteps}</span>
            <span style={styles.statLabel}>总步骤</span>
          </div>
          <div style={styles.stat}>
            <span style={{ ...styles.statValue, color: "#3fb950" }}>{successCount}</span>
            <span style={styles.statLabel}>成功</span>
          </div>
          <div style={styles.stat}>
            <span style={{ ...styles.statValue, color: failCount > 0 ? "#f85149" : "#484f58" }}>
              {failCount}
            </span>
            <span style={styles.statLabel}>失败</span>
          </div>
          <div style={styles.stat}>
            <span style={styles.statValue}>
              {totalSteps > 0 ? Math.round((successCount / totalSteps) * 100) : 0}%
            </span>
            <span style={styles.statLabel}>成功率</span>
          </div>
        </div>
      )}

      {/* Extracted data */}
      {event.data && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>结构化数据</h3>
          <pre style={styles.jsonBlock}>
            {JSON.stringify(event.data, null, 2)}
          </pre>
        </div>
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
    fontSize: 20,
    marginBottom: 16,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    color: "#8b949e",
    marginBottom: 8,
  },
  summary: {
    fontSize: 14,
    color: "#c9d1d9",
    lineHeight: 1.6,
    whiteSpace: "pre-wrap",
  },
  errorText: {
    fontSize: 13,
    color: "#f85149",
    background: "#0d1117",
    padding: 12,
    borderRadius: 6,
    overflow: "auto",
    maxHeight: 200,
  },
  stats: {
    display: "flex",
    gap: 24,
    marginBottom: 16,
  },
  stat: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  statValue: {
    fontSize: 24,
    fontWeight: 700,
    color: "#f0f6fc",
  },
  statLabel: {
    fontSize: 12,
    color: "#8b949e",
  },
  jsonBlock: {
    fontSize: 12,
    color: "#7ee787",
    background: "#0d1117",
    padding: 12,
    borderRadius: 6,
    overflow: "auto",
    maxHeight: 300,
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  },
};
