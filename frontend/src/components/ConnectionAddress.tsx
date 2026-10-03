import { useState } from "react";
import type { InstanceConnection } from "../services/api";
import { btnDefault } from "./ui";

interface ConnectionAddressProps {
  connection?: InstanceConnection | null;
  /** Kompakte Darstellung fuer Listen */
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
      // Clipboard nicht verfuegbar (z.B. http): Adresse bleibt sichtbar und markierbar
    }
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      {!compact && <span style={{ color: "#888", fontSize: 13 }}>Adresse:</span>}
      <code style={{ fontSize: compact ? 12 : 13, userSelect: "all", background: "#f5f5f5", padding: "2px 6px", borderRadius: 4 }}>
        {connection.address}
      </code>
      <button
        type="button"
        onClick={copy}
        aria-label={`Adresse ${connection.address} kopieren`}
        style={{ ...btnDefault, padding: "2px 8px", fontSize: 12 }}
      >
        {copied ? "✓ Kopiert" : "📋 Kopieren"}
      </button>
      <span role="status" style={{ position: "absolute", left: -9999 }}>{copied ? "Adresse kopiert" : ""}</span>
    </span>
  );
}
