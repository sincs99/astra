import { useEffect, useState } from "react";
import {
  api,
  type Instance,
  type User,
  type Agent,
  type Blueprint,
  type Endpoint,
} from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState,
  Toast, useToast, ConfirmButton,
  cardStyle, inputStyle, labelStyle, btnPrimary, thStyle, tdStyle,
} from "../components/ui";

export function AdminInstancesPage() {
  const toast = useToast();
  const [instances, setInstances] = useState<Instance[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Formular-State
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [agentId, setAgentId] = useState<number | "">("");
  const [blueprintId, setBlueprintId] = useState<number | "">("");
  const [endpointId, setEndpointId] = useState<number | "">("");
  const [memory, setMemory] = useState(512);
  const [swap, setSwap] = useState(0);
  const [disk, setDisk] = useState(1024);
  const [io, setIo] = useState(500);
  const [cpu, setCpu] = useState(100);
  const [submitting, setSubmitting] = useState(false);

  // Transfer-State
  const [transferringUuid, setTransferringUuid] = useState<string | null>(null);
  const [transferTargetAgent, setTransferTargetAgent] = useState<number | "">("");

  const handleTransfer = async (uuid: string) => {
    if (!transferTargetAgent) { setError("Bitte Ziel-Agent auswählen"); return; }
    try {
      setError(null);
      await api.transferInstance(uuid, transferTargetAgent as number);
      toast.success(`Transfer für Instance ${uuid.substring(0, 8)}… gestartet.`);
      setTransferringUuid(null);
      setTransferTargetAgent("");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Transfer");
    }
  };

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [inst, usr, agt, bp, ep] = await Promise.all([
        api.getInstances(),
        api.getUsers(),
        api.getAgents(),
        api.getBlueprints(),
        api.getEndpoints(),
      ]);
      setInstances(inst);
      setUsers(usr);
      setAgents(agt);
      setBlueprints(bp);
      setEndpoints(ep);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const freeEndpoints = endpoints.filter(
    ep => ep.agent_id === agentId && ep.instance_id === null && !ep.is_locked
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !ownerId || !agentId || !blueprintId) return;

    try {
      setSubmitting(true);
      setError(null);
      await api.createInstance({
        name: name.trim(),
        description: description.trim() || undefined,
        owner_id: ownerId as number,
        agent_id: agentId as number,
        blueprint_id: blueprintId as number,
        endpoint_id: endpointId ? (endpointId as number) : undefined,
        memory, swap, disk, io, cpu,
      });
      setName(""); setDescription(""); setOwnerId(""); setAgentId("");
      setBlueprintId(""); setEndpointId("");
      setMemory(512); setSwap(0); setDisk(1024); setIo(500); setCpu(100);
      toast.success("Instance erstellt.");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageLayout title="Instances">
      <Toast {...toast} />

      {/* ── Erstell-Formular ── */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Neue Instance</h2>
        {error && <ErrorState message={error} onRetry={() => setError(null)} />}
        <form onSubmit={handleSubmit}>
          <div style={grid2}>
            <div>
              <label style={labelStyle}>Name *</label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="z.B. MC-Server-1" required style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Beschreibung</label>
              <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional" style={inputStyle} />
            </div>
          </div>

          <div style={{ ...grid3, marginTop: 12 }}>
            <div>
              <label style={labelStyle}>Owner *</label>
              <select value={ownerId} onChange={e => setOwnerId(e.target.value ? Number(e.target.value) : "")} required style={inputStyle}>
                <option value="">– Wählen –</option>
                {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Agent *</label>
              <select value={agentId} onChange={e => { setAgentId(e.target.value ? Number(e.target.value) : ""); setEndpointId(""); }} required style={inputStyle}>
                <option value="">– Wählen –</option>
                {agents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.fqdn})</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Blueprint *</label>
              <select value={blueprintId} onChange={e => setBlueprintId(e.target.value ? Number(e.target.value) : "")} required style={inputStyle}>
                <option value="">– Wählen –</option>
                {blueprints.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={labelStyle}>Endpoint (optional – sonst automatisch)</label>
            <select value={endpointId} onChange={e => setEndpointId(e.target.value ? Number(e.target.value) : "")} style={inputStyle} disabled={!agentId}>
              <option value="">– Automatisch zuweisen –</option>
              {freeEndpoints.map(ep => <option key={ep.id} value={ep.id}>{ep.ip}:{ep.port}</option>)}
            </select>
            {agentId && freeEndpoints.length === 0 && (
              <small style={{ color: "#d32f2f" }}>Keine freien Endpoints auf diesem Agent verfügbar.</small>
            )}
          </div>

          <div style={{ ...grid5, marginTop: 12 }}>
            {[
              { label: "Memory (MB)", value: memory, set: setMemory, min: 64 },
              { label: "Swap (MB)", value: swap, set: setSwap, min: 0 },
              { label: "Disk (MB)", value: disk, set: setDisk, min: 256 },
              { label: "IO", value: io, set: setIo, min: 10, max: 1000 },
              { label: "CPU (%)", value: cpu, set: setCpu, min: 1 },
            ].map(f => (
              <div key={f.label}>
                <label style={labelStyle}>{f.label}</label>
                <input type="number" value={f.value} onChange={e => f.set(Number(e.target.value))} min={f.min} max={f.max} style={inputStyle} />
              </div>
            ))}
          </div>

          <div style={{ marginTop: 16 }}>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? "Wird erstellt..." : "Instance erstellen"}
            </button>
          </div>
        </form>
      </div>

      {/* ── Instance-Liste ── */}
      {loading ? (
        <LoadingState message="Instances werden geladen..." />
      ) : instances.length === 0 ? (
        <EmptyState icon="🖥️" message="Noch keine Instances vorhanden." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #e0e0e0" }}>
            <thead>
              <tr style={{ backgroundColor: "#f5f5f5" }}>
                <th style={thStyle}>Name</th>
                <th style={thStyle}>UUID</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Owner</th>
                <th style={thStyle}>Agent</th>
                <th style={thStyle}>Endpoint</th>
                <th style={thStyle}>Ressourcen</th>
                <th style={thStyle}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {instances.map(inst => {
                const owner = users.find(u => u.id === inst.owner_id);
                const agent = agents.find(a => a.id === inst.agent_id);
                const ep = endpoints.find(e => e.id === inst.primary_endpoint_id);
                const isTransferring = transferringUuid === inst.uuid;
                return (
                  <tr key={inst.id}>
                    <td style={tdStyle}>
                      <strong>{inst.name}</strong>
                      {inst.description && <div style={{ fontSize: 12, color: "#888" }}>{inst.description}</div>}
                    </td>
                    <td style={tdStyle}>
                      <code style={{ fontSize: 11 }}>{inst.uuid.substring(0, 8)}…</code>
                    </td>
                    <td style={tdStyle}>
                      <StatusBadge status={inst.status ?? "ready"} size="sm" />
                    </td>
                    <td style={tdStyle}>{owner?.username ?? "–"}</td>
                    <td style={tdStyle}>{agent?.name ?? "–"}</td>
                    <td style={tdStyle}>{ep ? `${ep.ip}:${ep.port}` : "–"}</td>
                    <td style={tdStyle}>
                      <small style={{ color: "#666" }}>
                        {inst.memory}MB / {inst.disk}MB / {inst.cpu}%
                      </small>
                    </td>
                    <td style={tdStyle}>
                      {isTransferring ? (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
                          <select
                            value={transferTargetAgent}
                            onChange={e => setTransferTargetAgent(e.target.value ? Number(e.target.value) : "")}
                            style={{ padding: "4px 6px", fontSize: 12, borderRadius: 4, border: "1px solid #ccc" }}
                          >
                            <option value="">– Ziel-Agent –</option>
                            {agents.filter(a => a.id !== inst.agent_id && a.is_active).map(a => (
                              <option key={a.id} value={a.id}>{a.name}</option>
                            ))}
                          </select>
                          <button
                            onClick={() => handleTransfer(inst.uuid)}
                            style={{ padding: "4px 10px", fontSize: 12, backgroundColor: "#4caf50", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
                          >
                            ✓
                          </button>
                          <button
                            onClick={() => { setTransferringUuid(null); setTransferTargetAgent(""); }}
                            style={{ padding: "4px 8px", fontSize: 12, border: "1px solid #ccc", borderRadius: 4, cursor: "pointer", backgroundColor: "#fff" }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          <button
                            onClick={() => { setTransferringUuid(inst.uuid); setTransferTargetAgent(""); }}
                            style={{ padding: "4px 10px", fontSize: 12, border: "1px solid #ccc", borderRadius: 4, cursor: "pointer", backgroundColor: "#fff" }}
                            title="Instance transferieren"
                          >
                            ⇄ Transfer
                          </button>
                          {inst.status === "suspended" ? (
                            <ConfirmButton
                              label="Entsperren"
                              confirmMessage={`Suspension von "${inst.name}" aufheben?`}
                              size="sm"
                              onConfirm={async () => {
                                await api.unsuspendInstance(inst.uuid);
                                toast.success(`"${inst.name}" entsperrt`);
                                await loadAll();
                              }}
                            />
                          ) : (
                            <ConfirmButton
                              label="Sperren"
                              confirmMessage={`Instance "${inst.name}" suspendieren?`}
                              size="sm"
                              danger
                              onConfirm={async () => {
                                await api.suspendInstance(inst.uuid);
                                toast.success(`"${inst.name}" suspendiert`);
                                await loadAll();
                              }}
                            />
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}

// ── Styles ─────────────────────────────────────────────

const grid2: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 };
const grid3: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 };
const grid5: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 };
