import { useEffect, useState } from "react";
import { api, type Agent, type AgentUpdate, type Endpoint } from "../services/api";
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

  // Agent-Formular (Erstellen) und Bearbeiten
  const [form, setForm] = useState<AgentFormValues>(EMPTY_AGENT_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<AgentFormValues>(EMPTY_AGENT_FORM);
  const [editSubmitting, setEditSubmitting] = useState(false);

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
    const payload = toAgentPayload(form);
    if (typeof payload === "string") { toast.error(payload); return; }
    try {
      setSubmitting(true);
      setError(null);
      await api.createAgent({
        name: payload.name!,
        fqdn: payload.fqdn!,
        scheme: payload.scheme,
        behind_proxy: payload.behind_proxy,
        daemon_connect: payload.daemon_connect,
        daemon_listen: payload.daemon_listen,
        daemon_sftp: payload.daemon_sftp,
        daemon_base: payload.daemon_base,
      });
      setForm({ ...EMPTY_AGENT_FORM });
      toast.success("Agent erstellt. Node-Credentials wurden erzeugt – config.yml abrufen.");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (agent: Agent) => {
    setEditId(agent.id);
    setEditForm(agentToForm(agent));
  };

  const handleAgentUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editId === null) return;
    const payload = toAgentPayload(editForm);
    if (typeof payload === "string") { toast.error(payload); return; }
    try {
      setEditSubmitting(true);
      await api.updateAgent(editId, payload);
      toast.success("Agent gespeichert. Bei geänderten Ports die config.yml neu abrufen.");
      setEditId(null);
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setEditSubmitting(false);
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
          <AgentFormFields values={form} onChange={setForm} idPrefix="new" />
          <button type="submit" disabled={submitting} style={{ ...btnPrimary, marginTop: 12, opacity: submitting ? 0.6 : 1 }}>
            {submitting ? "…" : "Agent erstellen"}
          </button>
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

      {/* Agent bearbeiten */}
      {editId !== null && (
        <div style={{ ...cardStyle, borderColor: "#f57c00" }}>
          <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Agent bearbeiten</h2>
          <form onSubmit={handleAgentUpdate}>
            <AgentFormFields values={editForm} onChange={setEditForm} idPrefix="edit" showActive />
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button type="submit" disabled={editSubmitting} style={{ ...btnPrimary, opacity: editSubmitting ? 0.6 : 1 }}>
                {editSubmitting ? "…" : "Speichern"}
              </button>
              <button type="button" onClick={() => setEditId(null)} style={btnDefault}>Abbrechen</button>
            </div>
          </form>
        </div>
      )}

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
                  <button type="button" onClick={() => startEdit(agent)} style={btnDefault}>✏️ Bearbeiten</button>
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
                <span><strong>Listen:</strong> {agent.daemon_listen}</span>
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


// ── Agent-Formular (Erstellen & Bearbeiten) ─────────────

interface AgentFormValues {
  name: string;
  fqdn: string;
  scheme: string;
  behindProxy: boolean;
  /** Port, ueber den das Panel Wings erreicht (z.B. 443 hinter Caddy) */
  connect: string;
  /** Port, auf dem Wings lokal lauscht (z.B. 8080) */
  listen: string;
  sftp: string;
  base: string;
  uploadSize: string;
  isActive: boolean;
  /** Solange false, folgt der Connect-Port automatisch dem Listen-Port */
  connectTouched: boolean;
}

const EMPTY_AGENT_FORM: AgentFormValues = {
  name: "", fqdn: "", scheme: "https", behindProxy: false,
  connect: "8080", listen: "8080", sftp: "2022",
  base: "/var/lib/pterodactyl/volumes", uploadSize: "100",
  isActive: true, connectTouched: false,
};

function agentToForm(a: Agent): AgentFormValues {
  return {
    name: a.name, fqdn: a.fqdn, scheme: a.scheme, behindProxy: a.behind_proxy,
    connect: String(a.daemon_connect), listen: String(a.daemon_listen), sftp: String(a.daemon_sftp),
    base: a.daemon_base, uploadSize: String(a.upload_size), isActive: a.is_active,
    connectTouched: true,
  };
}

function validPort(value: string): number | null {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 65535 ? n : null;
}

/** Liefert den API-Payload oder eine Fehlermeldung (string). */
function toAgentPayload(v: AgentFormValues): AgentUpdate | string {
  if (!v.name.trim() || !v.fqdn.trim()) return "Name und FQDN sind erforderlich.";
  const connect = validPort(v.connect);
  const listen = validPort(v.listen);
  const sftp = validPort(v.sftp);
  if (connect === null) return "Connect-Port muss zwischen 1 und 65535 liegen.";
  if (listen === null) return "Listen-Port muss zwischen 1 und 65535 liegen.";
  if (sftp === null) return "SFTP-Port muss zwischen 1 und 65535 liegen.";
  const upload = Number(v.uploadSize);
  return {
    name: v.name.trim(),
    fqdn: v.fqdn.trim(),
    scheme: v.scheme,
    behind_proxy: v.behindProxy,
    daemon_connect: connect,
    daemon_listen: listen,
    daemon_sftp: sftp,
    daemon_base: v.base.trim() || "/var/lib/pterodactyl/volumes",
    upload_size: Number.isFinite(upload) && upload > 0 ? upload : 100,
    is_active: v.isActive,
  };
}

interface AgentFormFieldsProps {
  values: AgentFormValues;
  onChange: (v: AgentFormValues) => void;
  idPrefix: string;
  showActive?: boolean;
}

function AgentFormFields({ values, onChange, idPrefix, showActive }: AgentFormFieldsProps) {
  const set = <K extends keyof AgentFormValues>(key: K, value: AgentFormValues[K]) =>
    onChange({ ...values, [key]: value });
  const id = (name: string) => `${idPrefix}-${name}`;
  const portInput = { ...inputStyle, width: 100 };

  return (
    <>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label htmlFor={id("name")} style={labelStyle}>Name *</label>
          <input id={id("name")} type="text" value={values.name} onChange={e => set("name", e.target.value)}
            placeholder="z.B. Node-ZH-01" required style={inputStyle} />
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label htmlFor={id("fqdn")} style={labelStyle}>FQDN *</label>
          <input id={id("fqdn")} type="text" value={values.fqdn} onChange={e => set("fqdn", e.target.value)}
            placeholder="node01.astra.dev" required style={inputStyle} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, alignItems: "flex-end" }}>
        <div>
          <label htmlFor={id("scheme")} style={labelStyle}>Schema</label>
          <select id={id("scheme")} value={values.scheme} onChange={e => set("scheme", e.target.value)} style={{ ...inputStyle, width: 110 }}>
            <option value="https">https</option>
            <option value="http">http</option>
          </select>
        </div>
        <div>
          <label htmlFor={id("connect")} style={labelStyle} title="Port, über den das Panel Wings erreicht (z.B. 443 hinter Caddy)">Connect-Port</label>
          <input id={id("connect")} type="number" value={values.connect} min={1} max={65535} style={portInput}
            onChange={e => onChange({ ...values, connect: e.target.value, connectTouched: true })} />
        </div>
        <div>
          <label htmlFor={id("listen")} style={labelStyle} title="Port, auf dem Wings lokal lauscht (z.B. 8080)">Listen-Port</label>
          <input id={id("listen")} type="number" value={values.listen} min={1} max={65535} style={portInput}
            onChange={e => onChange({
              ...values,
              listen: e.target.value,
              connect: values.connectTouched ? values.connect : e.target.value,
            })} />
        </div>
        <div>
          <label htmlFor={id("sftp")} style={labelStyle}>SFTP-Port</label>
          <input id={id("sftp")} type="number" value={values.sftp} onChange={e => set("sftp", e.target.value)} min={1} max={65535} style={portInput} />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <label htmlFor={id("base")} style={labelStyle}>Datenverzeichnis</label>
          <input id={id("base")} type="text" value={values.base} onChange={e => set("base", e.target.value)} style={inputStyle} />
        </div>
        {showActive && (
          <div>
            <label htmlFor={id("upload")} style={labelStyle}>Max. Upload (MB)</label>
            <input id={id("upload")} type="number" value={values.uploadSize} onChange={e => set("uploadSize", e.target.value)} min={1} style={portInput} />
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={values.behindProxy} onChange={e => set("behindProxy", e.target.checked)} />
          Hinter Reverse Proxy (TLS extern)
        </label>
        {showActive && (
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={values.isActive} onChange={e => set("isActive", e.target.checked)} />
            Aktiv
          </label>
        )}
      </div>
      <p style={{ color: "#888", fontSize: 12, margin: "8px 0 0" }}>
        <strong>Connect-Port:</strong> unter diesem Port erreicht das Panel Wings (z.B. 443 hinter Caddy).{" "}
        <strong>Listen-Port:</strong> hier lauscht Wings lokal (z.B. 8080).
      </p>
    </>
  );
}
