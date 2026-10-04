import { useEffect, useRef } from "react";
import { btnDefault, btnPrimary } from "./ui";
import { t } from "../i18n";

/** Dateiname für "Als Datei speichern", z.B. "beleg-R-2026-0001.html". */
export function receiptFileName(number: string): string {
  return `beleg-${number.replace(/[^A-Za-z0-9._-]/g, "_")}.html`;
}

/**
 * Zeigt einen Beleg (fertiges HTML vom Server) in einem Dialog. Die Seite läuft in einem Iframe ohne
 * Skripte und ohne Zugriff auf die App (sandbox), und lässt sich als HTML-Datei speichern.
 */
export function ReceiptViewer({ number, html, onClose }: { number: string; html: string; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const save = () => {
    const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = receiptFileName(number);
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
      onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={t("orders.receiptDialog", { number })}
        onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--bg-card)", color: "var(--fg)", borderRadius: 8, width: "min(720px, 100%)", maxHeight: "100%", display: "flex", flexDirection: "column", padding: 16, gap: 12 }}>
        <iframe title={t("orders.receiptFrame", { number })} sandbox="" srcDoc={html}
          style={{ flex: 1, minHeight: 360, border: "1px solid var(--border)", borderRadius: 6, background: "white" }} />
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button type="button" style={btnDefault} onClick={save}>{t("orders.receiptSave")}</button>
          <button type="button" ref={closeRef} style={btnPrimary} onClick={onClose}>{t("common.close")}</button>
        </div>
      </div>
    </div>
  );
}
