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
  ready: { bg: "#e8f5e9", color: "#4caf50" },
  running: { bg: "#e8f5e9", color: "#4caf50" },
  starting: { bg: "#e3f2fd", color: "#1976d2" },
  stopping: { bg: "#fff3e0", color: "#f57c00" },
  stopped: { bg: "#f5f5f5", color: "#888" },
  provisioning: { bg: "#e3f2fd", color: "#1976d2" },
  provision_failed: { bg: "#ffebee", color: "#d32f2f", label: "Fehler" },
  reinstalling: { bg: "#e3f2fd", color: "#1976d2" },
  reinstall_failed: { bg: "#ffebee", color: "#d32f2f", label: "Fehler" },
  restoring: { bg: "#fff3e0", color: "#f57c00" },
  suspended: { bg: "#f5f5f5", color: "#888" },
  // Health
  healthy: { bg: "#e8f5e9", color: "#4caf50" },
  stale: { bg: "#fff8e1", color: "#f57c00" },
  degraded: { bg: "#ffebee", color: "#d32f2f" },
  unreachable: { bg: "#f5f5f5", color: "#888" },
  // Jobs
  pending: { bg: "#e3f2fd", color: "#1976d2" },
  completed: { bg: "#e8f5e9", color: "#4caf50" },
  failed: { bg: "#ffebee", color: "#d32f2f" },
  retrying: { bg: "#f3e5f5", color: "#9c27b0" },
  // Maintenance
  maintenance: { bg: "#fff3e0", color: "#e65100" },
  // Misc
  ok: { bg: "#e8f5e9", color: "#4caf50" },
  active: { bg: "#e8f5e9", color: "#4caf50", label: "aktiv" },
  inactive: { bg: "#f5f5f5", color: "#888", label: "inaktiv" },
  offline: { bg: "#f5f5f5", color: "#888" },
  unknown: { bg: "#f5f5f5", color: "#888" },
  error: { bg: "#ffebee", color: "#d32f2f" },
  warning: { bg: "#fff3e0", color: "#f57c00" },
  info: { bg: "#e3f2fd", color: "#1976d2" },
  success: { bg: "#e8f5e9", color: "#4caf50" },
};

interface StatusBadgeProps {
  status: string | null | undefined;
  label?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, label, size = "md" }: StatusBadgeProps) {
  const s = (status || "unknown").toLowerCase();
  const cfg = STATUS_CONFIG[s] || { bg: "#f5f5f5", color: "#888" };
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
