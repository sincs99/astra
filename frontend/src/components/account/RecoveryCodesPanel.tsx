import { useState } from "react";
import { btnDefault } from "../ui";
import { t } from "../../i18n";

/** Dateiinhalt für "Als Textdatei speichern". */
export function recoveryCodesFile(codes: string[]): string {
  return `${t("account.mfa.fileHeader")}\n\n${codes.join("\n")}\n`;
}

/**
 * Zeigt frisch erzeugte Recovery-Codes (nur dieses eine Mal): groß, mit Kopieren und Download.
 * Geschlossen wird erst, wenn bestätigt ist, dass die Codes gesichert wurden.
 */
export function RecoveryCodesPanel({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setCopied(true);
    } catch {
      // Zwischenablage nicht verfügbar: Codes bleiben markierbar
    }
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([recoveryCodesFile(codes)], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "astra-recovery-codes.txt";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div role="alert" style={{ padding: 12, marginBottom: 12, background: "var(--warn-soft)", border: "1px solid var(--warn-border)", borderRadius: 8 }}>
      <strong>{t("account.mfa.recoveryTitle")}</strong>
      <p style={{ margin: "4px 0 8px", fontSize: 13 }}>{t("account.mfa.recoveryText")}</p>
      <ul aria-label={t("account.mfa.recoveryList")} style={{
        listStyle: "none", margin: "0 0 8px", padding: 0, display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 8,
      }}>
        {codes.map((c) => (
          <li key={c}><code style={{
            display: "block", textAlign: "center", fontSize: 18, fontWeight: 600, letterSpacing: 1, userSelect: "all",
            background: "var(--surface)", color: "var(--text)", padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)",
          }}>{c}</code></li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" style={btnDefault} onClick={copy}>
          {copied ? `✓ ${t("account.copied")}` : `📋 ${t("account.copy")}`}
        </button>
        <button type="button" style={btnDefault} onClick={download}>⬇ {t("account.mfa.download")}</button>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, fontSize: 14 }}>
        <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
        {t("account.mfa.saved")}
      </label>
      <button type="button" disabled={!confirmed} onClick={onDone}
        style={{ ...btnDefault, marginTop: 8, opacity: confirmed ? 1 : 0.5, cursor: confirmed ? "pointer" : "not-allowed" }}>
        {t("account.mfa.done")}
      </button>
    </div>
  );
}
