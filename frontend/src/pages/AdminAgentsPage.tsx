import { useEffect, useState } from "react";
import { api, type Agent, type Endpoint } from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState, ConfirmButton,
  Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
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
  const [scheme, setScheme] = useState("https");
  const [behindProxy, setBehindProxy] = useState(false);
  const [daemonListen, setDaemonListen] = useState("8080");
  const [daemonSftp, setDaemonSftp] = useState("2022");
  const [daemonBase, setDaemonBase] = useState("/var/lib/pterodactyl/volumes");
  const [submitting, setSubmitting] = useState(false);

  // Endpoint-Formular
  const [epAgentId, setEpAgentId] = useState<number | "">("");
  const [epIp, setEpIp] = useState("0.0.0.0");
  const [epPort, setEpPort] = useState("");
  const [epSubmitting, setEpSubmitting] = useState(false);

  // config.yml-Dialog (M33)
  const [configAgent, setConfigAgent] = useState<Agent | null>(null);
  const [configYaml, setConfigYaml] = useState("");
  const [configLoading, setConfigLoading] = useState(false);

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
      await api.createAgent({
        name: name.trim(),
        fqdn: fqdn.trim(),
        scheme,
        behind_proxy: behindProxy,
        daemon_connect: Number(daemonListen) || 8080,
        daemon_listen: Number(daemonListen) || 8080,
        daemon_sftp: Number(daemonSftp) || 2022,
        daemon_base: daemonBase.trim() || "/var/lib/pterodactyl/volumes",
      });
      setName("");
      setFqdn("");
      toast.success("Agent erstellt. Node-Credentials wurden erzeugt – config.yml abrufen.");
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

  const openConfig = async (agent: Agent) => {
    try {
      setConfigLoading(true);
      setConfigAgent(agent);
      setConfigYaml("");
      const cfg = await api.getAgentConfiguration(agent.id);
      setConfigYaml(cfg.yaml);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "config.yml konnte nicht geladen werden");
      setConfigAgent(null);
    } finally {
      setConfigLoading(false);
    }
  };

  const copyConfig = async () => {
    try {
      await navigator.clipboard.writeText(configYaml);
      toast.success("config.yml in die Zwischenablage kopiert.");
    } catch {
      toast.error("Kopieren nicht möglich – bitte manuell markieren.");
    }
  };

  const rotateCredentials = async (agent: Agent) => {
    try {
      const result = await api.rotateAgentCredentials(agent.id);
      toast.success(result.message);
      await loadAll();
      if (configAgent?.id === agent.id) {
        await openConfig(result.agent);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Rotation fehlgeschlagen");
    }
  };

  return (
    <PageLayout title="Agents">
      <Toast {...toast} />

      {/* Agent erstellen */}
      <div style={cardStyle}>
        <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Neuer Agent (Wings-Node)</h2>
        {error && <ErrorState message={error} onRetry={() => setError(null)} />}
        <form onSubmit={handleAgentSubmit}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <label style={labelStyle}>Name *</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="z.B. Node-ZH-01"
                required
                style={inputStyle}
              />
            </div>
            <div style={{ flex: 1, minWidth: 160 }}>
              <label style={labelStyle}>FQDN *</label>
              <input
                type="text"
                value={fqdn}
                onChange={e => setFqdn(e.target.value)}
                placeholder="node01.astra.dev"
                required
                style={inputStyle}
              />
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, alignItems: "flex-end" }}>
            <div>
              <label style={labelStyle}>Schema</label>
              <select value={scheme} onChange={e => setScheme(e.target.value)} style={{ ...inputStyle, width: 110 }}>
                <option value="https">https</option>
                <option value="http">http</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Wings-Port</label>
              <input type="number" value={daemonListen} onChange={e => setDaemonListen(e.target.value)} min={1} max={65535} style={{ ...inputStyle, width: 100 }} />
            </div>
            <div>
              <label style={labelStyle}>SFTP-Port</label>
              <input type="number" value={daemonSftp} onChange={e => setDaemonSftp(e.target.value)} min={1} max={65535} style={{ ...inputStyle, width: 100 }} />
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={labelStyle}>Datenverzeichnis</label>
              <input type="text" value={daemonBase} onChange={e => setDaemonBase(e.target.value)} style={inputStyle} />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, paddingBottom: 8, whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={behindProxy} onChange={e => setBehindProxy(e.target.checked)} />
              Hinter Reverse Proxy (TLS extern)
            </label>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}>
              {submitting ? "…" : "Agent erstellen"}
            </button>
          </div>
        </form>
        <p style={{ color: "#888", fontSize: 12, margin: "8px 0 0" }}>
          Beim Erstellen werden Node-Credentials erzeugt. Die fertige <code>config.yml</code> für Wings
          gibt es anschließend über den Button beim Agent.
        </p>
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

      {/* config.yml-Dialog */}
      {configAgent && (
        <div style={{ ...cardStyle, borderColor: "#1976d2" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>
              config.yml für {configAgent.name}
            </h2>
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={copyConfig} disabled={!configYaml} style={btnDefault}>📋 Kopieren</button>
              <button onClick={() => setConfigAgent(null)} style={btnDefault}>Schließen</button>
            </div>
          </div>
          <p style={{ color: "#666", fontSize: 12, margin: "8px 0" }}>
            Auf dem Node nach <code>/etc/pterodactyl/config.yml</code> speichern und Wings neu starten.
            Diese Datei enthält das Node-Secret – nicht weitergeben.
          </p>
          {configLoading ? (
            <LoadingState message="config.yml wird erzeugt..." />
          ) : (
            <pre style={{ background: "#1e1e1e", color: "#e8e8e8", padding: 12, borderRadius: 6, fontSize: 12, overflowX: "auto", margin: 0 }}>
              {configYaml}
            </pre>
          )}
        </div>
      )}

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
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                <strong style={{ fontSize: 16 }}>{agent.name}</strong>
                <span style={{ color: "#888", fontSize: 14 }}>
                  {agent.scheme}://{agent.fqdn}:{agent.daemon_connect}
                </span>
                <StatusBadge status={agent.is_active ? "active" : "inactive"} size="sm" />
                <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                  <button onClick={() => openConfig(agent)} style={btnDefault}>📄 config.yml</button>
                  <ConfirmButton
                    label="🔑 Credentials rotieren"
                    confirmMessage={`Neue Node-Credentials für "${agent.name}" erzeugen? Wings auf dem Node braucht danach die neue config.yml.`}
                    onConfirm={() => rotateCredentials(agent)}
                    size="sm"
                  />
                </span>
              </div>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "#555", marginBottom: 8 }}>
                <span><strong>Token-ID:</strong> <code>{agent.daemon_token_id ?? "–"}</code></span>
                <span><strong>SFTP:</strong> {agent.daemon_sftp}</span>
                <span><strong>Daten:</strong> <code>{agent.daemon_base}</code></span>
                {agent.behind_proxy && <span>Hinter Proxy</span>}
                <span><strong>Zuletzt gesehen:</strong> {agent.last_seen_at ? new Date(agent.last_seen_at).toLocaleString("de-CH") : "noch nie"}</span>
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
