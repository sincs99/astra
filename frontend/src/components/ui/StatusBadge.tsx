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

const STATUS_CONFIG: Record<string, { bg: string; color: string; label?: string }> = {
  // Lifecycle
  ready: { bg: "var(--tint-green)", color: "var(--c-green)", label: "bereit" },
  running: { bg: "var(--tint-green)", color: "var(--c-green)", label: "läuft" },
  starting: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "startet" },
  stopping: { bg: "var(--tint-orange)", color: "var(--c-orange)", label: "stoppt" },
  stopped: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "gestoppt" },
  provisioning: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "wird eingerichtet" },
  provision_failed: { bg: "var(--tint-red)", color: "var(--c-red)", label: "Fehler" },
  reinstalling: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "wird neu installiert" },
  reinstall_failed: { bg: "var(--tint-red)", color: "var(--c-red)", label: "Fehler" },
  restoring: { bg: "var(--tint-orange)", color: "var(--c-orange)", label: "wird wiederhergestellt" },
  suspended: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "gesperrt" },
  transferring: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "wird verschoben" },
  transfer_failed: { bg: "var(--tint-red)", color: "var(--c-red)", label: "Transfer Fehler" },
  // Health
  healthy: { bg: "var(--tint-green)", color: "var(--c-green)", label: "gesund" },
  stale: { bg: "var(--tint-yellow)", color: "var(--c-orange)", label: "veraltet" },
  degraded: { bg: "var(--tint-red)", color: "var(--c-red)", label: "beeinträchtigt" },
  unreachable: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "nicht erreichbar" },
  // Jobs
  pending: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "ausstehend" },
  completed: { bg: "var(--tint-green)", color: "var(--c-green)", label: "abgeschlossen" },
  failed: { bg: "var(--tint-red)", color: "var(--c-red)", label: "fehlgeschlagen" },
  retrying: { bg: "var(--tint-purple)", color: "var(--c-purple)", label: "wird wiederholt" },
  // Bestellungen (Phase 4)
  pending_payment: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "Zahlung ausstehend" },
  awaiting_provisioning: { bg: "var(--tint-blue)", color: "var(--c-blue)", label: "wird bereitgestellt" },
  past_due: { bg: "var(--tint-orange)", color: "var(--c-orange)", label: "überfällig" },
  cancelled: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "gekündigt" },
  expired: { bg: "var(--tint-red)", color: "var(--c-red)", label: "abgelaufen" },
  // Zahlungsereignisse
  mismatch: { bg: "var(--tint-red)", color: "var(--c-red)", label: "Betrag weicht ab" },
  unapplied: { bg: "var(--tint-orange)", color: "var(--c-orange)", label: "Erstattung prüfen" },
  // Maintenance
  maintenance: { bg: "var(--tint-orange)", color: "var(--c-orange)", label: "Wartung" },
  // Misc
  ok: { bg: "var(--tint-green)", color: "var(--c-green)" },
  active: { bg: "var(--tint-green)", color: "var(--c-green)", label: "aktiv" },
  inactive: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "inaktiv" },
  offline: { bg: "var(--bg-subtle)", color: "var(--fg-muted)", label: "offline" },
  unknown: { bg: "var(--bg-subtle)", color: "var(--fg-muted)" },
  error: { bg: "var(--tint-red)", color: "var(--c-red)" },
  warning: { bg: "var(--tint-orange)", color: "var(--c-orange)" },
  info: { bg: "var(--tint-blue)", color: "var(--c-blue)" },
  success: { bg: "var(--tint-green)", color: "var(--c-green)" },
};

/** Deutsche Bezeichnung eines Status fuer Fliesstexte (Fallback: der Rohwert). */
export function statusLabel(status: string | null | undefined): string {
  const s = (status || "unknown").toLowerCase();
  return STATUS_CONFIG[s]?.label ?? s;
}

interface StatusBadgeProps {
  status: string | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, label, size = "md" }: StatusBadgeProps) {
  const s = (status || "unknown").toLowerCase();
  const cfg = STATUS_CONFIG[s] || { bg: "var(--bg-subtle)", color: "var(--fg-muted)" };
  const displayLabel = label || cfg.label || s;

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
