/**
 * Einheitliches Status-Badge (M26).
 *
 * Farb-Konventionen:
 * - Gruen: ready, running, healthy, completed, ok, active
 * - Blau: provisioning, starting, pending, info, reinstalling
 * - Orange: stale, retrying, warning, maintenance, restoring
 * - Rot: failed, error, degraded, stopped, provision_failed, reinstall_failed
 * - Grau: offline, unknown, inactive, unreachable, none
 */

import { hasKey, t } from "../../i18n";

const STATUS_CONFIG: Record<string, { bg: string; color: string }> = {
  // Lifecycle
  ready: { bg: "var(--tint-green)", color: "var(--c-green)" },
  running: { bg: "var(--tint-green)", color: "var(--c-green)" },
  starting: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  stopping: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  stopped: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  provisioning: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  provision_failed: { bg: "var(--tint-red)", color: "var(--c-red)" },
  reinstalling: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  reinstall_failed: { bg: "var(--tint-red)", color: "var(--c-red)" },
  restoring: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  suspended: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  transferring: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  transfer_failed: { bg: "var(--tint-red)", color: "var(--c-red)" },
  // Health
  healthy: { bg: "var(--tint-green)", color: "var(--c-green)" },
  stale: { bg: "var(--tint-yellow)", color: "var(--c-orange)" },
  degraded: { bg: "var(--tint-red)", color: "var(--c-red)" },
  unreachable: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  // Jobs
  pending: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  completed: { bg: "var(--tint-green)", color: "var(--c-green)" },
  failed: { bg: "var(--tint-red)", color: "var(--c-red)" },
  retrying: { bg: "var(--tint-purple)", color: "var(--c-purple)" },
  // Bestellungen (Phase 4)
  pending_payment: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  awaiting_provisioning: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  past_due: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  cancelled: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  expired: { bg: "var(--tint-red)", color: "var(--c-red)" },
  refunded: { bg: "var(--tint-red)", color: "var(--c-red)" },
  disputed: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  // Zahlungsereignisse
  mismatch: { bg: "var(--tint-red)", color: "var(--c-red)" },
  unapplied: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  // Maintenance
  maintenance: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  // Misc
  ok: { bg: "var(--tint-green)", color: "var(--c-green)" },
  active: { bg: "var(--tint-green)", color: "var(--c-green)" },
  inactive: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  offline: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  unknown: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  error: { bg: "var(--tint-red)", color: "var(--c-red)" },
  warning: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  info: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  success: { bg: "var(--tint-green)", color: "var(--c-green)" },
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
  const cfg = STATUS_CONFIG[s] || { bg: "var(--bg-subtle)", color: "var(--fg-muted)" };
  const displayLabel = label || translatedStatus(s) || s;

  const fontSize = size === "sm" ? 10 : 12;
  const padding = size === "sm" ? "1px 6px" : "2px 10px";

  return (
    <span
      role="status"
      aria-label={displayLabel}
      style={{
        display: "inline-block",
        padding,
        borderRadius: 12,
        fontSize,
        fontWeight: 600,
        backgroundColor: cfg.bg,
        color: cfg.color,
        whiteSpace: "nowrap",
      }}
    >
      {displayLabel}
    </span>
  );
}
