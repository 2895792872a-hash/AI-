import { useEffect, useState, useCallback } from "react";
import { CheckCircle, XCircle, X } from "lucide-react";
import { createPortal } from "react-dom";

interface ToastItem {
  id: number;
  type: "success" | "error";
  message: string;
}

let toastId = 0;
const listeners: Set<(t: ToastItem) => void> = new Set();

export function showToast(type: "success" | "error", message: string) {
  const toast: ToastItem = { id: ++toastId, type, message };
  listeners.forEach((fn) => fn(toast));
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((t: ToastItem) => {
    setToasts((prev) => [...prev, t]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((x) => x.id !== t.id));
    }, 4000);
  }, []);

  useEffect(() => {
    listeners.add(addToast);
    return () => { listeners.delete(addToast); };
  }, [addToast]);

  return createPortal(
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          {t.type === "success" ? (
            <CheckCircle size={16} color="var(--success)" />
          ) : (
            <XCircle size={16} color="var(--error)" />
          )}
          <span className="toast-text">{t.message}</span>
          <button
            className="toast-close"
            onClick={() =>
              setToasts((prev) => prev.filter((x) => x.id !== t.id))
            }
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>,
    document.body
  );
}
