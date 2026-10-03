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
  ready: { bg: "#e8f5e9", color: "#2e7d32" },
  running: { bg: "#e8f5e9", color: "#2e7d32" },
  starting: { bg: "#e3f2fd", color: "#1565c0" },
  stopping: { bg: "#fff3e0", color: "#bf360c" },
  stopped: { bg: "#f5f5f5", color: "#666" },
  provisioning: { bg: "#e3f2fd", color: "#1565c0" },
  provision_failed: { bg: "#ffebee", color: "#c62828", label: "Fehler" },
  reinstalling: { bg: "#e3f2fd", color: "#1565c0" },
  reinstall_failed: { bg: "#ffebee", color: "#c62828", label: "Fehler" },
  restoring: { bg: "#fff3e0", color: "#bf360c" },
  suspended: { bg: "#f5f5f5", color: "#666" },
  transferring: { bg: "#e3f2fd", color: "#1565c0" },
  transfer_failed: { bg: "#ffebee", color: "#c62828", label: "Transfer Fehler" },
  // Health
  healthy: { bg: "#e8f5e9", color: "#2e7d32" },
  stale: { bg: "#fff8e1", color: "#bf360c" },
  degraded: { bg: "#ffebee", color: "#c62828" },
  unreachable: { bg: "#f5f5f5", color: "#666" },
  // Jobs
  pending: { bg: "#e3f2fd", color: "#1565c0" },
  completed: { bg: "#e8f5e9", color: "#2e7d32" },
  failed: { bg: "#ffebee", color: "#c62828" },
  retrying: { bg: "#f3e5f5", color: "#7b1fa2" },
  // Bestellungen (Phase 4)
  pending_payment: { bg: "#e3f2fd", color: "#1565c0", label: "Zahlung ausstehend" },
  awaiting_provisioning: { bg: "#e3f2fd", color: "#1565c0", label: "wird bereitgestellt" },
  past_due: { bg: "#fff3e0", color: "#bf360c", label: "überfällig" },
  cancelled: { bg: "#f5f5f5", color: "#666", label: "gekündigt" },
  expired: { bg: "#ffebee", color: "#c62828", label: "abgelaufen" },
  // Maintenance
  maintenance: { bg: "#fff3e0", color: "#bf360c" },
  // Misc
  ok: { bg: "#e8f5e9", color: "#2e7d32" },
  active: { bg: "#e8f5e9", color: "#2e7d32", label: "aktiv" },
  inactive: { bg: "#f5f5f5", color: "#666", label: "inaktiv" },
  offline: { bg: "#f5f5f5", color: "#666" },
  unknown: { bg: "#f5f5f5", color: "#666" },
  error: { bg: "#ffebee", color: "#c62828" },
  warning: { bg: "#fff3e0", color: "#bf360c" },
  info: { bg: "#e3f2fd", color: "#1565c0" },
  success: { bg: "#e8f5e9", color: "#2e7d32" },
};

interface StatusBadgeProps {
  status: string | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, label, size = "md" }: StatusBadgeProps) {
  const s = (status || "unknown").toLowerCase();
  const cfg = STATUS_CONFIG[s] || { bg: "#f5f5f5", color: "#666" };
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
