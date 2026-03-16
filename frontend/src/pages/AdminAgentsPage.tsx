import { useEffect, useState } from "react";
import { api, type Agent, type Endpoint } from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState,
  Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, thStyle, tdStyle,
} from "../components/ui";

export function AdminAgentsPage() {
  const toast = useToast();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Agent-Formular
  const [name, setName] = useState("");
  const [fqdn, setFqdn] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Endpoint-Formular
  const [epAgentId, setEpAgentId] = useState<number | "">("");
  const [epIp, setEpIp] = useState("0.0.0.0");
  const [epPort, setEpPort] = useState("");
  const [epSubmitting, setEpSubmitting] = useState(false);

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, epData] = await Promise.all([
        api.getAgents(),
        api.getEndpoints(),
      ]);
      setAgents(agentData);
      setEndpoints(epData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const handleAgentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !fqdn.trim()) return;
    try {
      setSubmitting(true);
      setError(null);
      await api.createAgent({ name: name.trim(), fqdn: fqdn.trim() });
      setName("");
      setFqdn("");
      toast.success("Agent erstellt.");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  const handleEndpointSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!epAgentId || !epPort) return;
    try {
      setEpSubmitting(true);
      setError(null);
      await api.createEndpoint(epAgentId as number, {
        ip: epIp.trim() || "0.0.0.0",
        port: Number(epPort),
      });
      setEpPort("");
      toast.success("Endpoint erstellt.");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setEpSubmitting(false);
    }
  };

  return (
    <PageLayout title="Agents">
      <Toast {...toast} />

      {/* Agent erstellen */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Neuer Agent</h2>
        {error && <ErrorState message={error} onRetry={() => setError(null)} />}
        <form onSubmit={handleAgentSubmit} style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Name (z.B. Node-ZH-01)"
            required
            style={{ ...inputStyle, flex: 1, minWidth: 160 }}
          />
          <input
            type="text"
            value={fqdn}
            onChange={e => setFqdn(e.target.value)}
            placeholder="FQDN (z.B. node01.astra.dev)"
            required
            style={{ ...inputStyle, flex: 1, minWidth: 160 }}
          />
          <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
            {submitting ? "…" : "Agent erstellen"}
          </button>
        </form>
      </div>

      {/* Endpoint erstellen */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Neuer Endpoint</h2>
        <form onSubmit={handleEndpointSubmit} style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 140 }}>
            <label style={labelStyle}>Agent *</label>
            <select
              value={epAgentId}
              onChange={e => setEpAgentId(e.target.value ? Number(e.target.value) : "")}
              required
              style={inputStyle}
            >
              <option value="">– Wählen –</option>
              {agents.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>IP</label>
            <input
              type="text"
              value={epIp}
              onChange={e => setEpIp(e.target.value)}
              placeholder="0.0.0.0"
              style={{ ...inputStyle, width: 130 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Port *</label>
            <input
              type="number"
              value={epPort}
              onChange={e => setEpPort(e.target.value)}
              placeholder="25565"
              required
              min={1}
              max={65535}
              style={{ ...inputStyle, width: 100 }}
            />
          </div>
          <button type="submit" disabled={epSubmitting} style={{ ...btnPrimary, opacity: epSubmitting ? 0.6 : 1 }}>
            {epSubmitting ? "…" : "Endpoint erstellen"}
          </button>
        </form>
      </div>

      {/* Agent-Liste mit Endpoints */}
      {loading ? (
        <LoadingState message="Agents werden geladen..." />
      ) : agents.length === 0 ? (
        <EmptyState icon="🖥️" message="Noch keine Agents vorhanden." />
      ) : (
        agents.map(agent => {
          const agentEndpoints = endpoints.filter(ep => ep.agent_id === agent.id);
          return (
            <div key={agent.id} style={{ ...cardStyle, marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <strong style={{ fontSize: 16 }}>{agent.name}</strong>
                <span style={{ color: "#888", fontSize: 14 }}>{agent.fqdn}</span>
                <StatusBadge status={agent.is_active ? "active" : "inactive"} size="sm" />
              </div>

              {agentEndpoints.length === 0 ? (
                <p style={{ color: "#888", margin: "4px 0 0", fontSize: 13 }}>Keine Endpoints</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#f5f5f5" }}>
                      <th style={thStyle}>ID</th>
                      <th style={thStyle}>IP:Port</th>
                      <th style={thStyle}>Status</th>
                      <th style={thStyle}>Instance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentEndpoints.map(ep => (
                      <tr key={ep.id}>
                        <td style={tdStyle}>{ep.id}</td>
                        <td style={tdStyle}><code>{ep.ip}:{ep.port}</code></td>
                        <td style={tdStyle}>
                          {ep.is_locked ? "🔒 Gesperrt" : ep.instance_id ? "🟢 Belegt" : "⚪ Frei"}
                        </td>
                        <td style={tdStyle}>{ep.instance_id ? `Instance #${ep.instance_id}` : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}
    </PageLayout>
  );
}
