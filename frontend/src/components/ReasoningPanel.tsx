import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  thinking: string;
}

export default function ReasoningPanel({ thinking }: Props) {
  const [open, setOpen] = useState(true);

  if (!thinking) return null;

  return (
    <div className="reasoning-panel">
      <div className="reasoning-header" onClick={() => setOpen(!open)}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Brain size={14} color="var(--accent)" />
          <span>Agent 正在思考</span>
        </div>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </div>
      {open && <div className="reasoning-body">{thinking}</div>}
    </div>
  );
}
