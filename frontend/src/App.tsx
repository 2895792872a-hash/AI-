import { useState, useEffect } from "react";
import { Globe, MessageSquare, PanelLeftClose, PanelLeft, Clock, Sun, Moon, Send } from "lucide-react";
import ChatSidebar from "./components/ChatSidebar";
import ChatView from "./components/ChatView";
import SchedulePanel from "./components/SchedulePanel";
import StatusBar from "./components/StatusBar";
import QuickStart from "./components/QuickStart";

function WelcomeInput({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const send = () => { if (text.trim()) { onSend(text.trim()); setText(""); } };
  return (
    <div className="task-input">
      <div className="input-wrap">
        <textarea
          value={text} onChange={(e) => setText(e.target.value)}
          placeholder="输入消息，或直接说'帮我打开xxx网站搜索xxx'…"
          className="task-textarea" rows={2}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        <button className="submit-btn" onClick={send}><Send size={18} /></button>
      </div>
    </div>
  );
}
import ToastContainer from "./components/Toast";

type Tab = "chat" | "schedule";

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem("theme") as "dark" | "light") || "dark"
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  // Chat state
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [chatRefresh, setChatRefresh] = useState(0);

  const handleNewChat = async () => {
    setChatSessionId(null); // Go to welcome screen
  };

  const handleStartChat = async (text: string) => {
    const res = await fetch("/api/chat/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: text.slice(0, 30) }),
    });
    const s = await res.json();
    setChatSessionId(s.id);
    setChatRefresh((r) => r + 1);
    // Send first message
    await fetch(`/api/chat/sessions/${s.id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text }),
    });
    setChatRefresh((r) => r + 1);
  };

  return (
    <div className="app">
      <div className="bg-blobs">
        <div className="bg-blob" />
        <div className="bg-blob" />
      </div>
      <StatusBar status="idle" />

      <header className="app-header">
        <div className="app-brand">
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
          <Globe size={18} />
          <span className="app-title">Browser Agent</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title={theme === "dark" ? "切换亮色" : "切换暗色"}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        <nav className="app-tabs">
          {([
            ["chat", "对话", MessageSquare],
            ["schedule", "定时", Clock],
          ] as [Tab, string, any][]).map(([t, label, Icon]) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`tab-btn${tab === t ? " active" : ""}`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </nav>
        </div>
      </header>

      <div className="app-body">
        {sidebarOpen && (
          <aside className="app-sidebar">
            <ChatSidebar
              activeId={chatSessionId}
              onSelect={(id) => { setChatSessionId(id); setTab("chat"); }}
              onNew={handleNewChat}
              refresh={chatRefresh}
            />
          </aside>
        )}

        <main className="app-main">
          {tab === "chat" && (
            <div className="chat-layout">
              <ChatView sessionId={chatSessionId} refreshSidebar={() => setChatRefresh((r) => r + 1)} />
              {!chatSessionId && (
                <div className="chat-welcome">
                  <WelcomeInput onSend={handleStartChat} />
                  <h3>快速开始</h3>
                  <QuickStart onSelect={handleStartChat} />
                </div>
              )}
            </div>
          )}

          {tab === "schedule" && (
            <SchedulePanel refresh={0} onRefresh={() => {}} />
          )}
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
