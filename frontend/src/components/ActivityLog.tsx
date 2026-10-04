import { useEffect, useState } from "react";
import { api, type ActivityLogEntry } from "../services/api";
import { formatLogTime } from "../lib/dates";
import { t } from "../i18n";

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

  if (loading) return <p className="hint">{t("susers.logLoading")}</p>;
  if (logs.length === 0) return <div className="card-empty">{t("susers.logEmpty")}</div>;

  return (
    <div className="panel" style={{ overflowX: "auto" }}>
      <table className="tbl">
        <thead>
          <tr>
            <th scope="col">{t("susers.colTime")}</th>
            <th scope="col">{t("susers.colEvent")}</th>
            <th scope="col">{t("susers.colDescription")}</th>
            <th scope="col">{t("susers.colActor")}</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.id}>
              <td>{formatLogTime(l.created_at)}</td>
              <td>
                <code className="mono" style={{ padding: "1px 6px", background: "var(--surface-2)", borderRadius: "var(--radius-badge)" }}>
                  {l.event}
                </code>
              </td>
              <td>{l.description || "–"}</td>
              <td>{l.actor_type === "system" ? t("susers.actorSystem") : t("susers.actorUser", { id: l.actor_id ?? "?" })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
