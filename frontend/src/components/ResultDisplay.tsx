import { useState } from "react";
import { CheckCircle, XCircle, Copy, Check } from "lucide-react";
import { SSEEvent } from "../hooks/useSSE";

interface Props {
  event: SSEEvent;
}

function formatText(text: string): string {
  return text
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>");
}

function parseTable(text: string): { headers: string[]; rows: string[][] } | null {
  const lines = text.split("\n");
  const tableLines = lines.filter((l) => l.includes("|"));
  if (tableLines.length < 2) return null;

  const dataRows = tableLines
    .filter((l) => !l.includes("---"))
    .map((l) =>
      l
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean)
    );
  if (dataRows.length < 2) return null;

  return { headers: dataRows[0], rows: dataRows.slice(1) };
}

export default function ResultDisplay({ event }: Props) {
  const [copied, setCopied] = useState(false);
  const isError = event.type === "error";

  const summary = event.summary || "";
  const tableData = parseTable(summary);

  const handleCopy = () => {
    navigator.clipboard.writeText(summary).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`result-card ${isError ? "error" : "success"}`}>
      <div className="result-header">
        <span className="result-icon">
          {isError ? (
            <XCircle size={16} color="var(--error)" />
          ) : (
            <CheckCircle size={16} color="var(--success)" />
          )}
        </span>
        <span className="result-status" style={{ color: isError ? "var(--error)" : "var(--success)" }}>
          {isError ? "执行失败" : "任务完成"}
        </span>
      </div>

      {summary && (
        <div className="result-body">
          {tableData ? (
            <table>
              <thead>
                <tr>{tableData.headers.map((h, i) => <th key={i}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {tableData.rows.map((row, ri) => (
                  <tr key={ri}>{row.map((c, ci) => <td key={ci}>{c}</td>)}</tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: `<p>${formatText(summary)}</p>` }} />
          )}
        </div>
      )}

      {event.error && <pre className="result-error-box">{event.error}</pre>}

      <div className="result-meta">
        <span>
          共 {event.total_steps || 0} 步 · {event.success_count || 0} 成功 · {event.fail_count || 0} 失败
        </span>
        {summary && (
          <button className="result-copy-btn" onClick={handleCopy}>
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "已复制" : "复制结果"}
          </button>
        )}
      </div>
    </div>
  );
}
