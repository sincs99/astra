import { useEffect, useState } from "react";
import { api, type RoutineEntry, ACTION_TYPES } from "../services/api";

interface RoutineManagerProps {
  instanceUuid: string;
}

export function RoutineManager({ instanceUuid }: RoutineManagerProps) {
  const [routines, setRoutines] = useState<RoutineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  // Create form
  const [newName, setNewName] = useState("");
  // Expanded routine for action management
  const [expandedId, setExpandedId] = useState<number | null>(null);
  // Add action form
  const [aType, setAType] = useState(ACTION_TYPES[0]);
  const [aPayload, setAPayload] = useState("{}");
  const [aDelay, setADelay] = useState(0);

  const loadRoutines = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getRoutines(instanceUuid);
      setRoutines(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
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
      showMsg("Routine erstellt");
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
    finally { setActing(false); }
  };

  const handleDelete = async (r: RoutineEntry) => {
    if (!confirm(`Routine "${r.name}" löschen?`)) return;
    try {
      setActing(true); setError(null);
      await api.deleteRoutine(instanceUuid, r.id);
      showMsg("Routine gelöscht");
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
    finally { setActing(false); }
  };

  const handleToggle = async (r: RoutineEntry) => {
    try {
      setError(null);
      await api.updateRoutine(instanceUuid, r.id, { is_active: !r.is_active });
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
  };

  const handleExecute = async (r: RoutineEntry) => {
    try {
      setActing(true); setError(null);
      const result = await api.executeRoutine(instanceUuid, r.id);
      const ok = result.results.filter((r) => r.success).length;
      const fail = result.results.filter((r) => !r.success).length;
      showMsg(`Routine ausgeführt: ${ok} OK, ${fail} Fehler`);
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
    finally { setActing(false); }
  };

  const handleAddAction = async (routineId: number) => {
    const routine = routines.find((r) => r.id === routineId);
    if (!routine) return;
    const nextSeq = routine.actions.length > 0 ? Math.max(...routine.actions.map((a) => a.sequence)) + 1 : 1;
    let payload: Record<string, unknown> | null = null;
    try { payload = JSON.parse(aPayload); } catch { setError("Ungültiges JSON im Payload"); return; }
    try {
      setActing(true); setError(null);
      await api.addRoutineAction(instanceUuid, routineId, {
        sequence: nextSeq, action_type: aType, payload, delay_seconds: aDelay,
      });
      setAPayload("{}"); setADelay(0);
      showMsg("Action hinzugefügt");
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
    finally { setActing(false); }
  };

  const handleDeleteAction = async (routineId: number, actionId: number) => {
    try {
      setActing(true); setError(null);
      await api.deleteRoutineAction(instanceUuid, routineId, actionId);
      showMsg("Action gelöscht");
      await loadRoutines();
    } catch (err) { setError(err instanceof Error ? err.message : "Fehler"); }
    finally { setActing(false); }
  };

  return (
    <div>
      {/* Create */}
      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Routine-Name" required style={{ flex: 1, padding: 6, fontSize: 13 }} />
        <button type="submit" disabled={acting} style={btnS}>+ Routine</button>
      </form>

      {error && <div style={errS}>{error}</div>}
      {message && <div style={msgS}>{message}</div>}

      {loading ? <p style={{ color: "#888" }}>Wird geladen...</p> : routines.length === 0 ? (
        <p style={{ color: "#888", fontSize: 13 }}>Keine Routinen vorhanden.</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {routines.map((r) => (
            <div key={r.id} style={{ border: "1px solid #eee", borderRadius: 6, padding: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong style={{ fontSize: 13 }}>{r.name}</strong>
                  <span style={{ marginLeft: 8, fontSize: 11, color: r.is_active ? "#5cb85c" : "#999" }}>
                    {r.is_active ? "●aktiv" : "○inaktiv"}
                  </span>
                  {r.is_processing && <span style={{ marginLeft: 6, fontSize: 11, color: "#f0ad4e" }}>⏳running</span>}
                  <span style={{ marginLeft: 8, fontSize: 10, color: "#aaa" }}>
                    {r.cron_minute} {r.cron_hour} {r.cron_day_month} {r.cron_month} {r.cron_day_week}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => handleToggle(r)} style={smB} title={r.is_active ? "Deaktivieren" : "Aktivieren"}>
                    {r.is_active ? "⏸" : "▶"}
                  </button>
                  <button onClick={() => handleExecute(r)} disabled={acting || r.is_processing} style={{ ...smB, color: "#5cb85c" }} title="Ausführen">⚡</button>
                  <button onClick={() => setExpandedId(expandedId === r.id ? null : r.id)} style={smB}>
                    {expandedId === r.id ? "▲" : "▼"}
                  </button>
                  <button onClick={() => handleDelete(r)} disabled={acting} style={{ ...smB, color: "#c00" }}>🗑</button>
                </div>
              </div>

              {r.last_run_at && (
                <div style={{ fontSize: 10, color: "#aaa", marginTop: 2 }}>
                  Zuletzt: {new Date(r.last_run_at).toLocaleString("de-CH")}
                </div>
              )}

              {/* Expanded: Actions */}
              {expandedId === r.id && (
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #eee" }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Actions ({r.actions.length})</div>
                  {r.actions.length > 0 && (
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginBottom: 8 }}>
                      <thead>
                        <tr>
                          <th style={thS}>#</th>
                          <th style={thS}>Typ</th>
                          <th style={thS}>Payload</th>
                          <th style={thS}>Delay</th>
                          <th style={{ ...thS, width: 30 }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {r.actions.map((a) => (
                          <tr key={a.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                            <td style={tdS}>{a.sequence}</td>
                            <td style={tdS}><code>{a.action_type}</code></td>
                            <td style={tdS}><code style={{ fontSize: 10 }}>{JSON.stringify(a.payload)}</code></td>
                            <td style={tdS}>{a.delay_seconds}s</td>
                            <td style={tdS}>
                              <button onClick={() => handleDeleteAction(r.id, a.id)} style={{ ...smB, color: "#c00", fontSize: 10 }}>✕</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  {/* Add Action */}
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "flex-end" }}>
                    <div>
                      <label style={{ fontSize: 10 }}>Typ</label>
                      <select value={aType} onChange={(e) => setAType(e.target.value)} style={{ display: "block", fontSize: 11, padding: 4 }}>
                        {ACTION_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: 10 }}>Payload (JSON)</label>
                      <input type="text" value={aPayload} onChange={(e) => setAPayload(e.target.value)} style={{ display: "block", fontSize: 11, padding: 4, width: 180 }} />
                    </div>
                    <div>
                      <label style={{ fontSize: 10 }}>Delay (s)</label>
                      <input type="number" value={aDelay} onChange={(e) => setADelay(Number(e.target.value))} min={0} style={{ display: "block", fontSize: 11, padding: 4, width: 50 }} />
                    </div>
                    <button onClick={() => handleAddAction(r.id)} disabled={acting} style={{ ...smB, fontSize: 11 }}>+ Action</button>
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

const btnS: React.CSSProperties = { padding: "6px 12px", border: "1px solid #ddd", borderRadius: 4, cursor: "pointer", fontSize: 12, backgroundColor: "#fff" };
const smB: React.CSSProperties = { padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, backgroundColor: "#fff", cursor: "pointer", fontSize: 12 };
const thS: React.CSSProperties = { padding: 4, textAlign: "left", fontSize: 11, fontWeight: 600 };
const tdS: React.CSSProperties = { padding: 4, fontSize: 12 };
const errS: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#fee", border: "1px solid #c00", borderRadius: 4, color: "#c00", fontSize: 12 };
const msgS: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#efe", border: "1px solid #0a0", borderRadius: 4, color: "#060", fontSize: 12 };
