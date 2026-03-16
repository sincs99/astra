import { useEffect, useState } from "react";
import {
  api,
  type Instance,
  type User,
  type Agent,
  type Blueprint,
  type Endpoint,
} from "../services/api";

export function AdminInstancesPage() {
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

  useEffect(() => {
    loadAll();
  }, []);

  // Freie Endpoints des gewählten Agents
  const freeEndpoints = endpoints.filter(
    (ep) =>
      ep.agent_id === agentId && ep.instance_id === null && !ep.is_locked
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
        memory,
        swap,
        disk,
        io,
        cpu,
      });
      // Formular zurücksetzen
      setName("");
      setDescription("");
      setOwnerId("");
      setAgentId("");
      setBlueprintId("");
      setEndpointId("");
      setMemory(512);
      setSwap(0);
      setDisk(1024);
      setIo(500);
      setCpu(100);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Instances</h1>

      {/* Erstell-Formular */}
      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
        }}
      >
        <h2 style={{ marginTop: 0 }}>Neue Instance</h2>
        <form onSubmit={handleSubmit}>
          {/* Name + Beschreibung */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z.B. MC-Server-1"
                required
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Beschreibung</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional"
                style={inputStyle}
              />
            </div>
          </div>

          {/* Dropdowns */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 12,
              marginTop: 12,
            }}
          >
            <div>
              <label style={labelStyle}>Owner *</label>
              <select
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value ? Number(e.target.value) : "")}
                required
                style={inputStyle}
              >
                <option value="">– Wählen –</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Agent *</label>
              <select
                value={agentId}
                onChange={(e) => {
                  setAgentId(e.target.value ? Number(e.target.value) : "");
                  setEndpointId("");
                }}
                required
                style={inputStyle}
              >
                <option value="">– Wählen –</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.fqdn})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Blueprint *</label>
              <select
                value={blueprintId}
                onChange={(e) =>
                  setBlueprintId(e.target.value ? Number(e.target.value) : "")
                }
                required
                style={inputStyle}
              >
                <option value="">– Wählen –</option>
                {blueprints.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Endpoint (optional) */}
          <div style={{ marginTop: 12 }}>
            <label style={labelStyle}>
              Endpoint (optional – sonst automatisch)
            </label>
            <select
              value={endpointId}
              onChange={(e) =>
                setEndpointId(e.target.value ? Number(e.target.value) : "")
              }
              style={inputStyle}
              disabled={!agentId}
            >
              <option value="">– Automatisch zuweisen –</option>
              {freeEndpoints.map((ep) => (
                <option key={ep.id} value={ep.id}>
                  {ep.ip}:{ep.port}
                </option>
              ))}
            </select>
            {agentId && freeEndpoints.length === 0 && (
              <small style={{ color: "#c00" }}>
                Keine freien Endpoints auf diesem Agent verfügbar.
              </small>
            )}
          </div>

          {/* Ressourcen */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr",
              gap: 12,
              marginTop: 12,
            }}
          >
            <div>
              <label style={labelStyle}>Memory (MB)</label>
              <input
                type="number"
                value={memory}
                onChange={(e) => setMemory(Number(e.target.value))}
                min={64}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Swap (MB)</label>
              <input
                type="number"
                value={swap}
                onChange={(e) => setSwap(Number(e.target.value))}
                min={0}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Disk (MB)</label>
              <input
                type="number"
                value={disk}
                onChange={(e) => setDisk(Number(e.target.value))}
                min={256}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>IO</label>
              <input
                type="number"
                value={io}
                onChange={(e) => setIo(Number(e.target.value))}
                min={10}
                max={1000}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>CPU (%)</label>
              <input
                type="number"
                value={cpu}
                onChange={(e) => setCpu(Number(e.target.value))}
                min={1}
                style={inputStyle}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            style={{ marginTop: 16, padding: "8px 20px", cursor: "pointer" }}
          >
            {submitting ? "Wird erstellt..." : "Instance erstellen"}
          </button>
        </form>
      </div>

      {/* Fehleranzeige */}
      {error && (
        <div
          style={{
            padding: 12,
            marginBottom: 16,
            backgroundColor: "#fee",
            border: "1px solid #c00",
            borderRadius: 4,
            color: "#c00",
          }}
        >
          {error}
        </div>
      )}

      {/* Instance-Liste */}
      {loading ? (
        <p>Instances werden geladen...</p>
      ) : instances.length === 0 ? (
        <p style={{ color: "#888" }}>Noch keine Instances vorhanden.</p>
      ) : (
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            border: "1px solid #ddd",
          }}
        >
          <thead>
            <tr style={{ backgroundColor: "#f5f5f5" }}>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>UUID</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Owner</th>
              <th style={thStyle}>Agent</th>
              <th style={thStyle}>Endpoint</th>
              <th style={thStyle}>Ressourcen</th>
            </tr>
          </thead>
          <tbody>
            {instances.map((inst) => {
              const owner = users.find((u) => u.id === inst.owner_id);
              const agent = agents.find((a) => a.id === inst.agent_id);
              const ep = endpoints.find(
                (e) => e.id === inst.primary_endpoint_id
              );
              return (
                <tr key={inst.id}>
                  <td style={tdStyle}>
                    <strong>{inst.name}</strong>
                    {inst.description && (
                      <div style={{ fontSize: 12, color: "#888" }}>
                        {inst.description}
                      </div>
                    )}
                  </td>
                  <td style={tdStyle}>
                    <code style={{ fontSize: 11 }}>
                      {inst.uuid.substring(0, 8)}…
                    </code>
                  </td>
                  <td style={tdStyle}>
                    <span style={statusBadge(inst.status ?? "ready")}>
                      {inst.status ?? "ready"}
                    </span>
                  </td>
                  <td style={tdStyle}>{owner?.username ?? "–"}</td>
                  <td style={tdStyle}>{agent?.name ?? "–"}</td>
                  <td style={tdStyle}>
                    {ep ? `${ep.ip}:${ep.port}` : "–"}
                  </td>
                  <td style={tdStyle}>
                    <small>
                      {inst.memory}MB RAM / {inst.disk}MB Disk / {inst.cpu}% CPU
                    </small>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 13,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: 8,
  boxSizing: "border-box",
};

const thStyle: React.CSSProperties = {
  padding: 10,
  textAlign: "left",
  borderBottom: "2px solid #ddd",
  fontSize: 13,
};

const tdStyle: React.CSSProperties = {
  padding: 10,
  borderBottom: "1px solid #eee",
  fontSize: 13,
};

function statusBadge(status: string): React.CSSProperties {
  const colors: Record<string, string> = {
    installing: "#f0ad4e",
    running: "#5cb85c",
    stopped: "#999",
    error: "#d9534f",
  };
  return {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 4,
    backgroundColor: colors[status] ?? "#eee",
    color: "#fff",
    fontSize: 11,
    fontWeight: 600,
  };
}
