import { useState } from "react";
import type { InstanceConnection } from "../services/api";
import { btnDefault } from "./ui";
import { t } from "../i18n";

interface ConnectionAddressProps {
  connection?: InstanceConnection | null;
  /** Kompakte Darstellung für Listen */
  compact?: boolean;
}

/** Zeigt die Verbindungsadresse eines Servers mit Kopier-Button. Rendert nichts ohne Adresse. */
export function ConnectionAddress({ connection, compact = false }: ConnectionAddressProps) {
  const [copied, setCopied] = useState(false);
  if (!connection?.address) return null;

  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(connection.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard nicht verfügbar (z.B. http): Adresse bleibt sichtbar und markierbar
    }
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      {!compact && <span style={{ color: "var(--fg-muted)", fontSize: 13 }}>{t("orders.address")}</span>}
      <code style={{ fontSize: compact ? 12 : 13, userSelect: "all", background: "var(--bg-subtle)", padding: "2px 6px", borderRadius: 4 }}>
        {connection.address}
      </code>
      <button
        type="button"
        onClick={copy}
        aria-label={t("orders.copyAria", { address: connection.address })}
        style={{ ...btnDefault, padding: "2px 8px", fontSize: 12 }}
      >
        {copied ? "✓ " + t("orders.copied") : "📋 " + t("orders.copy")}
      </button>
      <span role="status" style={{ position: "absolute", left: -9999 }}>{copied ? t("orders.copiedStatus") : ""}</span>
    </span>
  );
}
