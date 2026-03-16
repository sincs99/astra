import { useEffect, useState } from "react";
import { api, type Agent, type Endpoint } from "../services/api";

export function AdminAgentsPage() {
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

  useEffect(() => {
    loadAll();
  }, []);

  const handleAgentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !fqdn.trim()) return;

    try {
      setSubmitting(true);
      setError(null);
      await api.createAgent({ name: name.trim(), fqdn: fqdn.trim() });
      setName("");
      setFqdn("");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
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
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setEpSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Agents</h1>

      {/* Agent erstellen */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0 }}>Neuer Agent</h2>
        <form onSubmit={handleAgentSubmit} style={{ display: "flex", gap: 12 }}>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name (z.B. Node-ZH-01)"
            required
            style={{ ...inputStyle, flex: 1 }}
          />
          <input
            type="text"
            value={fqdn}
            onChange={(e) => setFqdn(e.target.value)}
            placeholder="FQDN (z.B. node01.astra.dev)"
            required
            style={{ ...inputStyle, flex: 1 }}
          />
          <button type="submit" disabled={submitting} style={btnStyle}>
            {submitting ? "…" : "Agent erstellen"}
          </button>
        </form>
      </div>

      {/* Endpoint erstellen */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0 }}>Neuer Endpoint</h2>
        <form
          onSubmit={handleEndpointSubmit}
          style={{ display: "flex", gap: 12, alignItems: "flex-end" }}
        >
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Agent *</label>
            <select
              value={epAgentId}
              onChange={(e) =>
                setEpAgentId(e.target.value ? Number(e.target.value) : "")
              }
              required
              style={inputStyle}
            >
              <option value="">– Wählen –</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>IP</label>
            <input
              type="text"
              value={epIp}
              onChange={(e) => setEpIp(e.target.value)}
              placeholder="0.0.0.0"
              style={{ ...inputStyle, width: 130 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Port *</label>
            <input
              type="number"
              value={epPort}
              onChange={(e) => setEpPort(e.target.value)}
              placeholder="25565"
              required
              min={1}
              max={65535}
              style={{ ...inputStyle, width: 100 }}
            />
          </div>
          <button type="submit" disabled={epSubmitting} style={btnStyle}>
            {epSubmitting ? "…" : "Endpoint erstellen"}
          </button>
        </form>
      </div>

      {/* Fehleranzeige */}
      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {/* Agent-Liste mit Endpoints */}
      {loading ? (
        <p>Wird geladen...</p>
      ) : agents.length === 0 ? (
        <p style={{ color: "#888" }}>Noch keine Agents vorhanden.</p>
      ) : (
        agents.map((agent) => {
          const agentEndpoints = endpoints.filter(
            (ep) => ep.agent_id === agent.id
          );
          return (
            <div key={agent.id} style={{ ...cardStyle, marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>
                {agent.name}{" "}
                <span style={{ fontWeight: 400, color: "#888", fontSize: 14 }}>
                  {agent.fqdn}
                </span>
                {agent.is_active ? (
                  <span style={{ ...badge, backgroundColor: "#5cb85c" }}>
                    aktiv
                  </span>
                ) : (
                  <span style={{ ...badge, backgroundColor: "#999" }}>
                    inaktiv
                  </span>
                )}
              </h3>

              {agentEndpoints.length === 0 ? (
                <p style={{ color: "#888", margin: "8px 0 0" }}>
                  Keine Endpoints
                </p>
              ) : (
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    marginTop: 8,
                  }}
                >
                  <thead>
                    <tr>
                      <th style={thStyle}>ID</th>
                      <th style={thStyle}>IP:Port</th>
                      <th style={thStyle}>Status</th>
                      <th style={thStyle}>Instance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentEndpoints.map((ep) => (
                      <tr key={ep.id}>
                        <td style={tdStyle}>{ep.id}</td>
                        <td style={tdStyle}>
                          <code>
                            {ep.ip}:{ep.port}
                          </code>
                        </td>
                        <td style={tdStyle}>
                          {ep.is_locked
                            ? "🔒 Gesperrt"
                            : ep.instance_id
                              ? "🟢 Belegt"
                              : "⚪ Frei"}
                        </td>
                        <td style={tdStyle}>
                          {ep.instance_id
                            ? `Instance #${ep.instance_id}`
                            : "–"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 8,
  padding: 16,
  marginBottom: 24,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 13,
};

const inputStyle: React.CSSProperties = {
  padding: 8,
  boxSizing: "border-box",
  width: "100%",
};

const btnStyle: React.CSSProperties = {
  padding: "8px 20px",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

const errorStyle: React.CSSProperties = {
  padding: 12,
  marginBottom: 16,
  backgroundColor: "#fee",
  border: "1px solid #c00",
  borderRadius: 4,
  color: "#c00",
};

const badge: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: 4,
  color: "#fff",
  fontSize: 11,
  fontWeight: 600,
  marginLeft: 8,
};

const thStyle: React.CSSProperties = {
  padding: 8,
  textAlign: "left",
  borderBottom: "1px solid #ddd",
  fontSize: 12,
};

const tdStyle: React.CSSProperties = {
  padding: 8,
  borderBottom: "1px solid #eee",
  fontSize: 13,
};
