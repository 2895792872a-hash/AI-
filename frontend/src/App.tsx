import { useState } from "react";
import TaskInput from "./components/TaskInput";
import ProgressStream from "./components/ProgressStream";
import ResultDisplay from "./components/ResultDisplay";
import { SSEEvent } from "./hooks/useSSE";

export default function App() {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [finalResult, setFinalResult] = useState<SSEEvent | null>(null);

  const handleTaskCreated = (id: string) => setTaskId(id);
  const handleEvents = (evs: SSEEvent[]) => setEvents(evs);
  const handleDone = (ev: SSEEvent) => { setFinalResult(ev); setIsRunning(false); };
  const handleError = (ev: SSEEvent) => { setFinalResult(ev); setIsRunning(false); };
  const handleRunning = (r: boolean) => setIsRunning(r);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🤖 AI 浏览器自动化助手</h1>
        <p style={styles.subtitle}>
          基于 Claude + LangGraph + Playwright 的四阶段智能浏览器 Agent
        </p>
      </header>

      <main style={styles.main}>
        <TaskInput
          onTaskCreated={handleTaskCreated}
          disabled={isRunning}
        />

        {taskId && (
          <ProgressStream
            taskId={taskId}
            onEvents={handleEvents}
            onDone={handleDone}
            onError={handleError}
            onRunning={handleRunning}
          />
        )}

        {finalResult && (
          <ResultDisplay
            event={finalResult}
            events={events}
          />
        )}
      </main>

      <footer style={styles.footer}>
        <span>Stage: Task Parsing → Browser Ops → Info Extraction → Result Summary</span>
        <span>Powered by Claude API & Playwright</span>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 900,
    margin: "0 auto",
    padding: "24px 16px",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    textAlign: "center",
    marginBottom: 32,
  },
  title: {
    fontSize: 28,
    color: "#58a6ff",
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: "#8b949e",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  footer: {
    textAlign: "center",
    fontSize: 12,
    color: "#484f58",
    marginTop: 40,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
};
