/**
 * Einfaches Toast-/Notification-System (M26).
 *
 * Verwendung:
 *   const toast = useToast();
 *   toast.success("Gespeichert!");
 *   toast.error("Fehlgeschlagen!");
 *
 *   <Toast {...toast} />
 */

import { useState, useCallback } from "react";

type ToastType = "success" | "error" | "info" | "warning";

interface ToastMessage {
  id: number;
  type: ToastType;
  text: string;
}

const COLORS: Record<ToastType, { bg: string; color: string; border: string }> = {
  success: { bg: "var(--tint-green)", color: "var(--c-green)", border: "var(--border-green)" },
  error: { bg: "var(--tint-red)", color: "var(--c-red)", border: "var(--border-red)" },
  info: { bg: "var(--tint-blue)", color: "var(--c-blue)", border: "var(--border-blue)" },
  warning: { bg: "var(--tint-orange)", color: "var(--c-orange)", border: "var(--border-orange)" },
};

let _nextId = 0;

export function useToast() {
  const [messages, setMessages] = useState<ToastMessage[]>([]);

  const show = useCallback((type: ToastType, text: string, duration = 4000) => {
    const id = ++_nextId;
    setMessages((prev) => [...prev, { id, type, text }]);
    setTimeout(() => {
      setMessages((prev) => prev.filter((m) => m.id !== id));
    }, duration);
  }, []);

  return {
    messages,
    success: (text: string) => show("success", text),
    error: (text: string) => show("error", text),
    info: (text: string) => show("info", text),
    warning: (text: string) => show("warning", text),
  };
}

interface ToastProps {
  messages: ToastMessage[];
}

export function Toast({ messages }: ToastProps) {
  if (messages.length === 0) return null;

  return (
    <div style={{
      position: "fixed", top: 16, right: 16, left: 16, marginLeft: "auto", zIndex: 9999,
      display: "flex", flexDirection: "column", gap: 8, maxWidth: 400, pointerEvents: "none",
    }}>
      {messages.map((msg) => {
        const c = COLORS[msg.type];
        return (
          <div
            key={msg.id}
            role={msg.type === "error" ? "alert" : "status"}
            style={{
              pointerEvents: "auto",
              padding: "10px 16px", borderRadius: 8,
              backgroundColor: c.bg, color: c.color,
              border: `1px solid ${c.border}`,
              fontSize: 14, fontWeight: 500,
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                          }}
          >
            {msg.text}
          </div>
        );
      })}
    </div>
  );
}
