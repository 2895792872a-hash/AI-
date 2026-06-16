import { Monitor, MousePointer } from "lucide-react";

interface Props {
  screenshot: string | null;
  currentUrl: string;
  currentAction: string;
}

export default function LiveViewport({ screenshot, currentUrl, currentAction }: Props) {
  return (
    <div className="viewport-panel">
      <div className="viewport-header">
        <Monitor size={14} />
        <span className="viewport-url">{currentUrl || "等待加载…"}</span>
      </div>
      <div className="viewport-img-wrap">
        {screenshot ? (
          <img
            src={`data:image/png;base64,${screenshot}`}
            alt="浏览器截图"
            className="viewport-img"
          />
        ) : (
          <div className="viewport-placeholder">
            <Monitor size={32} />
            <span>浏览器视图</span>
          </div>
        )}
      </div>
      {currentAction && (
        <div className="viewport-action">
          <MousePointer size={14} />
          <span>{currentAction}</span>
        </div>
      )}
    </div>
  );
}
