import type { AgentMonitoringEntry } from "../services/api";
import { StatusBadge } from "./ui";

type Props = Pick<AgentMonitoringEntry, "daemon_reachable" | "daemon_version" | "daemon_error">;

/**
 * Wings-Erreichbarkeit: Badge "Wings erreichbar" / "Wings nicht erreichbar" (Fehler als Tooltip)
 * und Version. Rendert nichts, solange das Backend keine Daemon-Pruefung liefert.
 */
export function DaemonStatus({ daemon_reachable, daemon_version, daemon_error }: Props) {
  if (daemon_reachable === undefined || daemon_reachable === null) return null;
  return (
    <>
      <span title={!daemon_reachable && daemon_error ? daemon_error : undefined}>
        <StatusBadge
          status={daemon_reachable ? "ok" : "failed"}
          label={daemon_reachable ? "Wings erreichbar" : "Wings nicht erreichbar"}
          size="sm"
        />
      </span>
      {daemon_version && <span style={{ color: "var(--fg-muted)", fontSize: 12 }}>Wings {daemon_version}</span>}
    </>
  );
}
