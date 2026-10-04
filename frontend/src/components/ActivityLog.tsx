import { useEffect, useState } from "react";
import { api, type ActivityLogEntry } from "../services/api";
import { formatLogTime } from "../lib/dates";

interface ActivityLogProps {
  instanceUuid: string;
}

export function ActivityLog({ instanceUuid }: ActivityLogProps) {
  const [logs, setLogs] = useState<ActivityLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await api.getInstanceActivity(instanceUuid);
        setLogs(data);
      } catch {
        // Silent
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [instanceUuid]);

  if (loading) return <p style={{ color: "var(--fg-muted)", fontSize: 13 }}>Wird geladen...</p>;
  if (logs.length === 0) return <p style={{ color: "var(--fg-muted)", fontSize: 13 }}>Keine Aktivitäten vorhanden.</p>;

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <thead>
        <tr style={{ borderBottom: "2px solid var(--border)" }}>
          <th style={thS}>Zeit</th>
          <th style={thS}>Event</th>
          <th style={thS}>Beschreibung</th>
          <th style={thS}>Actor</th>
        </tr>
      </thead>
      <tbody>
        {logs.map((l) => (
          <tr key={l.id} style={{ borderBottom: "1px solid var(--bg-subtle)" }}>
            <td style={tdS}>
              {formatLogTime(l.created_at)}
            </td>
            <td style={tdS}>
              <code style={{ fontSize: 11, padding: "1px 4px", backgroundColor: eventColor(l.event), borderRadius: 3 }}>
                {l.event}
              </code>
            </td>
            <td style={tdS}>{l.description || "–"}</td>
            <td style={tdS}>
              {l.actor_type === "system" ? "🤖 System" : `👤 #${l.actor_id}`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function eventColor(event: string): string {
  if (event.startsWith("instance:")) return "var(--tint-blue)";
  if (event.startsWith("backup:")) return "var(--tint-orange)";
  if (event.startsWith("file:")) return "var(--tint-green)";
  if (event.startsWith("collaborator:")) return "var(--tint-purple)";
  if (event.startsWith("routine:")) return "var(--tint-blue)";
  return "var(--bg-subtle)";
}

const thS: React.CSSProperties = { padding: 6, textAlign: "left", fontSize: 11, fontWeight: 600 };
const tdS: React.CSSProperties = { padding: 6, fontSize: 12 };
