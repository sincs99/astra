import { useEffect, useState } from "react";
import { api, type ActivityLogEntry } from "../services/api";

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

  if (loading) return <p style={{ color: "#888", fontSize: 13 }}>Wird geladen...</p>;
  if (logs.length === 0) return <p style={{ color: "#888", fontSize: 13 }}>Keine Aktivitäten vorhanden.</p>;

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <thead>
        <tr style={{ borderBottom: "2px solid #ddd" }}>
          <th style={thS}>Zeit</th>
          <th style={thS}>Event</th>
          <th style={thS}>Beschreibung</th>
          <th style={thS}>Actor</th>
        </tr>
      </thead>
      <tbody>
        {logs.map((l) => (
          <tr key={l.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
            <td style={tdS}>
              {l.created_at ? new Date(l.created_at).toLocaleString("de-CH", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" }) : "–"}
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
  if (event.startsWith("instance:")) return "#e8f0fe";
  if (event.startsWith("backup:")) return "#fef3e0";
  if (event.startsWith("file:")) return "#e8f5e9";
  if (event.startsWith("collaborator:")) return "#f3e5f5";
  if (event.startsWith("routine:")) return "#e0f7fa";
  return "#f5f5f5";
}

const thS: React.CSSProperties = { padding: 6, textAlign: "left", fontSize: 11, fontWeight: 600 };
const tdS: React.CSSProperties = { padding: 6, fontSize: 12 };
