/**
 * Einheitliches Status-Badge nach design/DESIGN.md: 7-px-Punkt + Text in immer derselben Form
 * (--surface-2, 1 px --border, Radius 4). Nur die Punktfarbe wechselt:
 * --ok läuft/bezahlt/gesund, --warn wartet/Warnung/bald fällig, --danger gestoppt/Fehler/überfällig,
 * --neutral inaktiv/unbekannt, Wartungsmodus nutzt --accent-soft.
 */

import { hasKey, t } from "../../i18n";

type Tone = "ok" | "warn" | "danger" | "neutral" | "accent";

const TONES: Record<string, Tone> = {
  ready: "ok", running: "ok", healthy: "ok", completed: "ok", ok: "ok", success: "ok", active: "ok",
  starting: "warn", stopping: "warn", provisioning: "warn", reinstalling: "warn", restoring: "warn", transferring: "warn",
  stale: "warn", pending: "warn", retrying: "warn", pending_payment: "warn", awaiting_provisioning: "warn",
  disputed: "warn", unapplied: "warn", warning: "warn",
  stopped: "danger", suspended: "danger", provision_failed: "danger", reinstall_failed: "danger", transfer_failed: "danger",
  degraded: "danger", failed: "danger", past_due: "danger", expired: "danger", refunded: "danger", mismatch: "danger", error: "danger",
  unreachable: "neutral", cancelled: "neutral", inactive: "neutral", offline: "neutral", unknown: "neutral",
  maintenance: "accent", info: "accent",
};

const DOT: Record<Tone, string> = {
  ok: "var(--ok)", warn: "var(--warn)", danger: "var(--danger)", neutral: "var(--neutral)", accent: "var(--accent)",
};

/** Übersetzte Bezeichnung (Schlüssel status.<name>); undefined, wenn es keine gibt. */
function translatedStatus(s: string): string | undefined {
  const key = `status.${s}`;
  return hasKey(key) ? t(key) : undefined;
}

/** Deutsche Bezeichnung eines Status fuer Fliesstexte (Fallback: der Rohwert). */
export function statusLabel(status: string | null | undefined): string {
  const s = (status || "unknown").toLowerCase();
  return translatedStatus(s) ?? s;
}

interface StatusBadgeProps {
  status: string | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, label, size = "md" }: StatusBadgeProps) {
  const s = (status || "unknown").toLowerCase();
  const tone = TONES[s] ?? "neutral";
  const displayLabel = label || translatedStatus(s) || s;
  const small = size === "sm";

  return (
    <span
      role="status"
      aria-label={displayLabel}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: small ? 6 : 7,
        padding: small ? "1px 7px 1px 6px" : "3px 9px 3px 8px",
        borderRadius: "var(--radius-badge)",
        fontSize: small ? 11 : 12,
        fontWeight: 500,
        lineHeight: 1.3,
        background: tone === "accent" ? "var(--accent-soft)" : "var(--surface-2)",
        border: "1px solid var(--border)",
        color: "var(--text)",
        whiteSpace: "nowrap",
      }}
    >
      <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: "50%", background: DOT[tone], flex: "0 0 auto" }} />
      {displayLabel}
    </span>
  );
}
