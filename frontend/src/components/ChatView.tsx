import { useState, useEffect, useRef } from "react";
import { Send, Bot, User, Loader, Globe, ChevronDown, ChevronRight, Monitor, Brain, Square, Copy, Download, Check } from "lucide-react";
import { SSEEvent } from "../hooks/useSSE";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  data?: { status?: string; task?: string; task_id?: string };
  timestamp: string;
}

interface Props {
  sessionId: string | null;
  refreshSidebar: () => void;
}

function ResultActions({ content, task, onRetry }: { content: string; task: string; onRetry: () => void }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };
  const handleDownload = () => {
    const md = content.replace(/\n/g, '\n\n');
    const blob = new Blob([`# 浏览器任务结果\n\n${md}\n\n---\n*由 AI Browser Agent 生成*`], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `result-${new Date().toISOString().slice(0,10)}.md`;
    a.click(); URL.revokeObjectURL(url);
  };
  return (
    <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
      <button className="action-btn" onClick={(e) => { e.stopPropagation(); handleCopy(); }} title="复制结果">
        {copied ? <Check size={12} /> : <Copy size={12} />}
        <span>{copied ? "已复制" : "复制"}</span>
      </button>
      <button className="action-btn" onClick={(e) => { e.stopPropagation(); handleDownload(); }} title="下载 Markdown">
        <Download size={12} />
        <span>下载</span>
      </button>
      <button className="action-btn" onClick={(e) => { e.stopPropagation(); onRetry(); }} title="重试">
        <span>重试</span>
      </button>
    </div>
  );
}

export default function ChatView({ sessionId, refreshSidebar }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [browserTaskId, setBrowserTaskId] = useState<string | null>(null);
  const [browserEvents, setBrowserEvents] = useState<SSEEvent[]>([]);
  const [showProgress, setShowProgress] = useState(false);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [thinking, setThinking] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    fetch(`/api/chat/sessions/${sessionId}/messages`)
      .then((r) => r.json())
      .then((d) => {
        const msgs: Message[] = d.messages || [];
        setMessages(msgs);
        // Detect if last message is a running browser task
        const last = msgs[msgs.length - 1];
        if (last?.data?.status === "browser_started" && last.data.task_id && !last.data.task_id) {
          // Task is still running, connect SSE
        }
        const running = msgs.find(m => m.data?.status === "browser_started") &&
                        !msgs.find(m => m.data?.status === "browser_done");
        if (running) {
          const bsMsg = msgs.find(m => m.data?.status === "browser_started");
          if (bsMsg?.data?.task_id) {
            setBrowserTaskId(bsMsg.data.task_id);
          }
        }
      })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, browserEvents]);

  // Connect SSE when browser task starts
  useEffect(() => {
    if (!browserTaskId) return;
    setShowProgress(true);
    setBrowserEvents([]);
    const es = new EventSource(`/api/tasks/${browserTaskId}/stream`);
    ["stage_change", "step_start", "step_complete", "step_error", "screenshot_update"].forEach((t) => {
      es.addEventListener(t, (e: MessageEvent) => {
        try {
          const d: SSEEvent = JSON.parse(e.data); d.type = t;
          setBrowserEvents((prev) => [...prev, d]);
          if (t === "screenshot_update") setScreenshot((d as any).image_base64 || null);
          if (t === "step_complete" && d.action === "vl_think") {
            setThinking((d.result_summary || "").replace("🤔 ", ""));
          }
        } catch {}
      });
    });
    es.addEventListener("done", () => {
      es.close();
      setShowProgress(false);
      setBrowserTaskId(null);
      setLoading(false);
      // Refresh messages to show browser_done result
      if (sessionId) {
        fetch(`/api/chat/sessions/${sessionId}/messages`)
          .then(r => r.json())
          .then(d => { if (d.messages) setMessages(d.messages); })
          .catch(() => {});
      }
      refreshSidebar();
    });
    es.addEventListener("error", () => {
      es.close();
      setBrowserTaskId(null);
      setLoading(false);
    });
    return () => es.close();
  }, [browserTaskId]);

  const send = async () => {
    if (!input.trim() || !sessionId || loading) return;
    const text = input.trim();
    setInput("");
    setLoading(true);
    setBrowserTaskId(null);
    setBrowserEvents([]);
    setScreenshot(null);
    setThinking("");

    const userMsg: Message = {
      id: "temp-u", role: "user", content: text, timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await fetch(`/api/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      const reply: Message = await res.json();
      setMessages((prev) => [...prev, reply]);

      if (reply.data?.status === "browser_started" && reply.data?.task_id) {
        setBrowserTaskId(reply.data.task_id);
        pollBrowserResult(sessionId);
      } else {
        setLoading(false);
        refreshSidebar();
      }
    } catch {
      setMessages((prev) => [...prev, {
        id: "err", role: "assistant",
        content: "请求失败，请确认后端已启动。",
        timestamp: new Date().toISOString(),
      }]);
      setLoading(false);
      refreshSidebar();
    }
  };

  const pollBrowserResult = async (sid: string) => {
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/chat/sessions/${sid}/messages`);
        const d = await res.json();
        const msgs: Message[] = d.messages || [];
        const done = msgs.filter((m) => m.role === "assistant" && m.data?.status === "browser_done").slice(-1)[0];
        if (done) {
          setMessages(msgs);
          setLoading(false);
          setBrowserTaskId(null);
          refreshSidebar();
          return;
        }
        setMessages(msgs);
      } catch { break; }
    }
    setLoading(false);
    setBrowserTaskId(null);
  };

  if (!sessionId) {
    return (
      <div className="chat-empty">
        <Bot size={48} strokeWidth={1} />
        <h3>选择或创建一个对话</h3>
        <p>需要浏览器操作时，直接告诉我要做什么即可</p>
      </div>
    );
  }

  const isBrowsing = !!browserTaskId;

  // Group step events
  const stepEvents = browserEvents.filter(
    (e) => e.type === "step_start" || e.type === "step_complete" || e.type === "step_error"
  );

  return (
    <div className="chat-view">
      <div className="chat-messages">
        {messages.map((msg) => {
          const isBrowserMsg = msg.data?.status === "browser_started";
          const isBrowserDone = msg.data?.status === "browser_done";
          return (
            <div key={msg.id} className={`chat-msg ${msg.role}`}>
              <div className="chat-avatar">
                {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className="chat-bubble">
                {isBrowserMsg ? (
                  <div>
                    <div className="browser-working">
                      <Globe size={14} />
                      <span>操作浏览器</span>
                      <button className="progress-toggle" onClick={() => setShowProgress(!showProgress)}>
                        {showProgress ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        <span>详情</span>
                      </button>
                    </div>

                    {/* Expandable progress panel */}
                    {showProgress && (
                      <div className="browser-progress">
                        {/* Screenshot */}
                        {screenshot && (
                          <div className="bp-screenshot">
                            <img src={`data:image/png;base64,${screenshot}`} alt="" />
                          </div>
                        )}

                        {/* Agent thinking */}
                        {thinking && (
                          <div className="bp-thinking">
                            <Brain size={12} />
                            <span>{thinking}</span>
                          </div>
                        )}

                        {/* Step list */}
                        {stepEvents.length > 0 && (
                          <div className="bp-steps">
                            {stepEvents.map((ev, i) => (
                              <div key={i} className="bp-step">
                                <span className="bp-step-icon">
                                  {ev.type === "step_start" ? "○" : ev.type === "step_complete" ? "●" : "✕"}
                                </span>
                                <span className="bp-step-text" style={{
                                  color: ev.type === "step_error" ? "var(--error)"
                                    : ev.type === "step_complete" ? "var(--success)" : "var(--text-secondary)",
                                }}>
                                  [{ev.action}]{" "}
                                  {ev.type === "step_start" ? ev.description
                                    : ev.type === "step_complete" ? "完成"
                                    : `失败 — ${ev.error?.slice(0, 40)}`}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : isBrowserDone ? (
                  <div>
                    <div className="browser-done-tag">
                      <Globe size={12} />
                      <span>{msg.content.includes('失败') || msg.content.includes('未找到') ? '任务完成（部分数据缺失）' : '任务完成'}</span>
                      <ResultActions content={msg.content} task={msg.data?.task || ''} onRetry={() => { setInput(msg.data?.task || ''); setTimeout(send, 100); }} />
                    </div>
                    <div className="chat-content">{msg.content}</div>
                  </div>
                ) : (
                  <div className="chat-content">{msg.content}</div>
                )}
              </div>
            </div>
          );
        })}

        {loading && !isBrowsing && (
          <div className="chat-msg assistant">
            <div className="chat-avatar"><Bot size={16} /></div>
            <div className="chat-bubble" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Loader size={14} className="spin" />
              <span style={{ color: "var(--text-secondary)", fontSize: 13 }}>思考中…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        {isBrowsing && (
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
            <button
              className="stop-btn"
              onClick={async () => {
                if (browserTaskId) {
                  await fetch(`/api/tasks/${browserTaskId}/cancel`, { method: "POST" });
                }
                setBrowserTaskId(null);
                setLoading(false);
              }}
            >
              <Square size={14} fill="currentColor" />
              <span>停止任务</span>
            </button>
          </div>
        )}
        <div className="chat-input-wrap">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入消息，或直接说'帮我打开xxx网站搜索xxx'…"
            className="chat-input"
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
          />
          <button
            className="chat-send-btn"
            disabled={!input.trim() || loading}
            onClick={send}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
