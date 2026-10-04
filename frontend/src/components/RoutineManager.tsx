import { useEffect, useState } from "react";
import { api, type RoutineEntry, ACTION_TYPES } from "../services/api";
import { formatDateTime } from "../lib/dates";
import { hasKey, t } from "../i18n";
import { Icon } from "./ui/Icon";

interface RoutineManagerProps {
  instanceUuid: string;
}

/** Übersetzt einen API-Aktionstyp; unbekannte Werte werden roh angezeigt. */
function actionLabel(type: string): string {
  const key = `sroutines.type.${type}`;
  return hasKey(key) ? t(key) : type;
}

export function RoutineManager({ instanceUuid }: RoutineManagerProps) {
  const [routines, setRoutines] = useState<RoutineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const [newName, setNewName] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [aType, setAType] = useState(ACTION_TYPES[0]);
  const [aPayload, setAPayload] = useState("{}");
  const [aDelay, setADelay] = useState(0);

  const fail = (err: unknown) => setError(err instanceof Error ? err.message : t("sroutines.failed"));

  const loadRoutines = async () => {
    try {
      setLoading(true);
      setError(null);
      setRoutines(await api.getRoutines(instanceUuid));
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRoutines(); }, [instanceUuid]);

  const showMsg = (m: string) => { setMessage(m); setTimeout(() => setMessage(null), 3000); };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      setActing(true); setError(null);
      await api.createRoutine(instanceUuid, { name: newName.trim() });
      setNewName("");
      showMsg(t("sroutines.created"));
      await loadRoutines();
    } catch (err) { fail(err); }
    finally { setActing(false); }
  };

  const handleDelete = async (r: RoutineEntry) => {
    if (!confirm(t("sroutines.deleteConfirm", { name: r.name }))) return;
    try {
      setActing(true); setError(null);
      await api.deleteRoutine(instanceUuid, r.id);
      showMsg(t("sroutines.deleted"));
      await loadRoutines();
    } catch (err) { fail(err); }
    finally { setActing(false); }
  };

  const handleToggle = async (r: RoutineEntry) => {
    try {
      setError(null);
      await api.updateRoutine(instanceUuid, r.id, { is_active: !r.is_active });
      await loadRoutines();
    } catch (err) { fail(err); }
  };

  const handleExecute = async (r: RoutineEntry) => {
    try {
      setActing(true); setError(null);
      const result = await api.executeRoutine(instanceUuid, r.id);
      const ok = result.results.filter((x) => x.success).length;
      const failed = result.results.filter((x) => !x.success).length;
      showMsg(t("sroutines.executed", { ok, fail: failed }));
      await loadRoutines();
    } catch (err) { fail(err); }
    finally { setActing(false); }
  };

  const handleAddAction = async (routineId: number) => {
    const routine = routines.find((r) => r.id === routineId);
    if (!routine) return;
    const nextSeq = routine.actions.length > 0 ? Math.max(...routine.actions.map((a) => a.sequence)) + 1 : 1;
    let payload: Record<string, unknown> | null = null;
    try { payload = JSON.parse(aPayload); } catch { setError(t("sroutines.invalidJson")); return; }
    try {
      setActing(true); setError(null);
      await api.addRoutineAction(instanceUuid, routineId, {
        sequence: nextSeq, action_type: aType, payload, delay_seconds: aDelay,
      });
      setAPayload("{}"); setADelay(0);
      showMsg(t("sroutines.actionAdded"));
      await loadRoutines();
    } catch (err) { fail(err); }
    finally { setActing(false); }
  };

  const handleDeleteAction = async (routineId: number, actionId: number) => {
    try {
      setActing(true); setError(null);
      await api.deleteRoutineAction(instanceUuid, routineId, actionId);
      showMsg(t("sroutines.actionDeleted"));
      await loadRoutines();
    } catch (err) { fail(err); }
    finally { setActing(false); }
  };

  return (
    <div className="stack" style={{ gap: 14 }}>
      <form onSubmit={handleCreate} className="row-actions" style={{ alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "1 1 220px" }}>
          <label htmlFor="routine-name" className="sr-only">{t("sroutines.nameLabel")}</label>
          <input id="routine-name" className="inp" type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder={t("sroutines.namePlaceholder")} required />
        </div>
        <button type="submit" disabled={acting} className="btn btn-primary"><Icon name="plus" /> {t("sroutines.add")}</button>
      </form>

      {error && <div className="banner banner-danger" role="alert">{error}</div>}
      {message && <div className="banner banner-info" role="status">{message}</div>}

      {loading ? <p className="hint">{t("sroutines.loading")}</p> : routines.length === 0 ? (
        <div className="card-empty">{t("sroutines.empty")}</div>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {routines.map((r) => (
            <div key={r.id} className="card">
              <div className="row-actions" style={{ marginTop: 0 }}>
                <span className="card-title">{r.name}</span>
                <span className="card-sub">
                  <span className={`dot ${r.is_active ? "dot-ok" : ""}`} style={r.is_active ? undefined : { background: "var(--text-3)" }} aria-hidden="true" />{" "}
                  {r.is_active ? t("sroutines.active") : t("sroutines.inactive")}
                </span>
                {r.is_processing && <span className="card-sub text-warn">{t("sroutines.running")}</span>}
                <span className="card-sub mono" title={t("sroutines.cron")}>
                  {r.cron_minute} {r.cron_hour} {r.cron_day_month} {r.cron_month} {r.cron_day_week}
                </span>
                <span className="push row-actions" style={{ marginTop: 0 }}>
                  <button type="button" className="btn btn-sm btn-icon" onClick={() => handleToggle(r)}
                    aria-label={r.is_active ? t("sroutines.deactivate") : t("sroutines.activate")}
                    title={r.is_active ? t("sroutines.deactivate") : t("sroutines.activate")}>
                    <Icon name={r.is_active ? "stop" : "play"} />
                  </button>
                  <button type="button" className="btn btn-sm btn-icon" onClick={() => handleExecute(r)} disabled={acting || r.is_processing}
                    aria-label={t("sroutines.run")} title={t("sroutines.run")}>
                    <Icon name="zap" />
                  </button>
                  <button type="button" className="btn btn-sm btn-icon" onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                    aria-expanded={expandedId === r.id}
                    aria-label={expandedId === r.id ? t("sroutines.collapse") : t("sroutines.expand")}
                    title={expandedId === r.id ? t("sroutines.collapse") : t("sroutines.expand")}>
                    <Icon name="chevrons" />
                  </button>
                  <button type="button" className="btn btn-sm btn-icon btn-danger-text" onClick={() => handleDelete(r)} disabled={acting}
                    aria-label={t("sroutines.delete")} title={t("sroutines.delete")}>
                    <Icon name="close" />
                  </button>
                </span>
              </div>

              {r.last_run_at && <p className="hint">{t("sroutines.lastRun", { time: formatDateTime(r.last_run_at) })}</p>}

              {expandedId === r.id && (
                <div className="stack" style={{ gap: 12 }}>
                  <h3 className="section-title" style={{ margin: 0 }}>{t("sroutines.actionsTitle", { n: r.actions.length })}</h3>
                  {r.actions.length > 0 && (
                    <div style={{ overflowX: "auto" }}>
                      <table className="tbl">
                        <thead>
                          <tr>
                            <th scope="col">{t("sroutines.colSeq")}</th>
                            <th scope="col">{t("sroutines.colType")}</th>
                            <th scope="col">{t("sroutines.colPayload")}</th>
                            <th scope="col">{t("sroutines.colDelay")}</th>
                            <th scope="col"><span className="sr-only">{t("sroutines.colRemove")}</span></th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.actions.map((a) => (
                            <tr key={a.id}>
                              <td>{a.sequence}</td>
                              <td>{actionLabel(a.action_type)}</td>
                              <td><code className="mono">{JSON.stringify(a.payload)}</code></td>
                              <td>{a.delay_seconds}s</td>
                              <td>
                                <button type="button" className="btn btn-sm btn-icon btn-danger-text" onClick={() => handleDeleteAction(r.id, a.id)} disabled={acting}
                                  aria-label={t("sroutines.deleteAction", { n: a.sequence })} title={t("sroutines.deleteAction", { n: a.sequence })}>
                                  <Icon name="close" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="row-actions" style={{ alignItems: "flex-end" }}>
                    <div className="field">
                      <label htmlFor={`a-type-${r.id}`}>{t("sroutines.fieldType")}</label>
                      <select id={`a-type-${r.id}`} className="inp" value={aType} onChange={(e) => setAType(e.target.value)}>
                        {ACTION_TYPES.map((x) => <option key={x} value={x}>{actionLabel(x)}</option>)}
                      </select>
                    </div>
                    <div className="field" style={{ flex: "1 1 200px" }}>
                      <label htmlFor={`a-payload-${r.id}`}>{t("sroutines.fieldPayload")}</label>
                      <input id={`a-payload-${r.id}`} className="inp mono" type="text" value={aPayload} onChange={(e) => setAPayload(e.target.value)} />
                    </div>
                    <div className="field" style={{ width: 120 }}>
                      <label htmlFor={`a-delay-${r.id}`}>{t("sroutines.fieldDelay")}</label>
                      <input id={`a-delay-${r.id}`} className="inp" type="number" value={aDelay} onChange={(e) => setADelay(Number(e.target.value))} min={0} />
                    </div>
                    <button type="button" className="btn" onClick={() => handleAddAction(r.id)} disabled={acting}>
                      <Icon name="plus" /> {t("sroutines.addAction")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
