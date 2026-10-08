import { useEffect, useRef, useState } from "react";
import { api, type Agent, type AgentMonitoringEntry, type Endpoint } from "../services/api";
import { DaemonInfo, LoadBar } from "../components/admin/AgentParts";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { parsePortRange } from "../lib/portRange";
import { EMPTY_AGENT_FORM, agentToForm, toAgentPayload, type AgentFormValues } from "../lib/agentForm";
import {
  PageLayout, AutoRefreshToggle, StatusBadge, ConfirmButton, ScrollRegion, Toast, useToast,
} from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { formatDateTime } from "../lib/dates";
import { t } from "../i18n";

const GRID: React.CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(180px, 100%), 1fr))", gap: 14 };

export function AdminAgentsPage() {
  const toast = useToast();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [health, setHealth] = useState<Record<number, AgentMonitoringEntry>>({});
  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("agents");
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

  // config.yml-Bereich (M33)
  const [configAgent, setConfigAgent] = useState<Agent | null>(null);
  const [configYaml, setConfigYaml] = useState("");
  const [configLoading, setConfigLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current); }, []);

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, epData] = await Promise.all([api.getAgents(), api.getEndpoints()]);
      setAgents(agentData);
      setEndpoints(epData);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("aagents.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  // Health-Status ist Zusatzinfo: Fehler hier duerfen die Seite nicht blockieren
  const loadHealth = async () => {
    try {
      const entries = await api.getAgentsMonitoring();
      setHealth(Object.fromEntries(entries.map(e => [e.id, e])));
    } catch {
      setHealth({});
    }
  };

  useEffect(() => { loadAll(); loadHealth(); }, []);

  useAutoRefresh(loadHealth, 15000, autoRefresh);

  const handleAgentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = toAgentPayload(form, { requireCapacity: true });
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
        memory_total: payload.memory_total,
        disk_total: payload.disk_total,
        cpu_total: payload.cpu_total,
        memory_overalloc: payload.memory_overalloc,
        disk_overalloc: payload.disk_overalloc,
        cpu_overalloc: payload.cpu_overalloc,
      });
      setForm({ ...EMPTY_AGENT_FORM });
      toast.success(t("aagents.created"));
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("aagents.createFailed"));
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
      toast.success(t("aagents.saved"));
      setEditId(null);
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("aagents.saveFailed"));
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleEndpointSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!epAgentId) return;
    const range = parsePortRange(epPort);
    if (typeof range === "string") { toast.error(range); return; }
    const ip = epIp.trim() || "0.0.0.0";
    try {
      setEpSubmitting(true);
      setError(null);
      if (range.start === range.end) {
        await api.createEndpoint(epAgentId as number, { ip, port: range.start });
        toast.success(t("aagents.ep.created"));
      } else {
        const result = await api.createEndpointsBulk(epAgentId as number, {
          ip, port_start: range.start, port_end: range.end,
        });
        toast.success(t("aagents.ep.bulk", { created: result.created, skipped: result.skipped }));
      }
      setEpPort("");
      await loadAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("aagents.createFailed"));
    } finally {
      setEpSubmitting(false);
    }
  };

  const openConfig = async (agent: Agent) => {
    try {
      setConfigLoading(true);
      setConfigAgent(agent);
      setConfigYaml("");
      setCopied(false);
      const cfg = await api.getAgentConfiguration(agent.id);
      setConfigYaml(cfg.yaml);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("aagents.cfg.loadFailed"));
      setConfigAgent(null);
    } finally {
      setConfigLoading(false);
    }
  };

  const copyConfig = async () => {
    try {
      await navigator.clipboard.writeText(configYaml);
      setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1500);
      toast.success(t("aagents.cfg.copiedStatus"));
    } catch {
      toast.error(t("aagents.cfg.copyFailed"));
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
      toast.error(err instanceof Error ? err.message : t("aagents.rotateFailed"));
    }
  };

  return (
    <PageLayout title={t("aagents.title")} subtitle={t("aagents.subtitle")}
      actions={<AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />}>
      <Toast {...toast} />
      <div className="stack">
        {error && (
          <div className="banner banner-danger" role="alert">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text">{error}</span>
            <button type="button" className="btn btn-sm" onClick={loadAll}>{t("aagents.retry")}</button>
          </div>
        )}

        {/* Agent erstellen */}
        <section className="panel" aria-labelledby="aagents-new">
          <div className="panel-head"><h2 id="aagents-new">{t("aagents.newTitle")}</h2></div>
          <form className="panel-body" onSubmit={handleAgentSubmit}>
            <AgentFormFields values={form} onChange={setForm} idPrefix="new" />
            <div className="row-actions">
              <button type="submit" disabled={submitting} className="btn btn-primary">
                <Icon name="plus" size={14} />{submitting ? t("aagents.saving") : t("aagents.create")}
              </button>
            </div>
            <p className="hint">{t("aagents.createHint")}</p>
          </form>
        </section>

        {/* Endpoint erstellen */}
        <section className="panel" aria-labelledby="aagents-ep">
          <div className="panel-head"><h2 id="aagents-ep">{t("aagents.ep.title")}</h2></div>
          <form className="panel-body" onSubmit={handleEndpointSubmit}>
            <div style={GRID}>
              <div className="field">
                <label htmlFor="ep-agent">{t("aagents.ep.agent")} *</label>
                <select id="ep-agent" className="inp" value={epAgentId} required
                  onChange={e => setEpAgentId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">{t("aagents.ep.choose")}</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="ep-ip">{t("aagents.ep.ip")}</label>
                <input id="ep-ip" className="inp mono" type="text" value={epIp} placeholder="0.0.0.0" onChange={e => setEpIp(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="ep-port">{t("aagents.ep.port")} *</label>
                <input id="ep-port" className="inp mono" type="text" inputMode="numeric" value={epPort} required
                  placeholder={t("aagents.ep.portPh")} aria-describedby="ep-range-hint" onChange={e => setEpPort(e.target.value)} />
              </div>
            </div>
            <div className="row-actions">
              <button type="submit" disabled={epSubmitting} className="btn btn-primary">
                <Icon name="plus" size={14} />{epSubmitting ? t("aagents.saving") : t("aagents.ep.create")}
              </button>
            </div>
            <p id="ep-range-hint" className="hint">{t("aagents.ep.hint")}</p>
          </form>
        </section>

        {/* Agent bearbeiten */}
        {editId !== null && (
          <section className="panel" aria-labelledby="aagents-edit">
            <div className="panel-head"><h2 id="aagents-edit">{t("aagents.editTitle")}</h2></div>
            <form className="panel-body" onSubmit={handleAgentUpdate}>
              <AgentFormFields values={editForm} onChange={setEditForm} idPrefix="edit" showActive />
              <div className="row-actions">
                <button type="submit" disabled={editSubmitting} className="btn btn-primary">
                  <Icon name="save" size={14} />{editSubmitting ? t("aagents.saving") : t("aagents.save")}
                </button>
                <button type="button" className="btn" onClick={() => setEditId(null)}>{t("aagents.cancel")}</button>
              </div>
            </form>
          </section>
        )}

        {/* config.yml */}
        {configAgent && (
          <section className="panel" aria-labelledby="aagents-cfg">
            <div className="panel-head">
              <h2 id="aagents-cfg">{t("aagents.cfg.title", { name: configAgent.name })}</h2>
              <div className="row-actions" style={{ marginTop: 0 }}>
                <button type="button" className="btn btn-sm" onClick={copyConfig} disabled={!configYaml} aria-label={t("aagents.cfg.copyAria")}>
                  <Icon name="copy" size={13} />{copied ? t("aagents.cfg.copied") : t("aagents.cfg.copy")}
                </button>
                <button type="button" className="btn btn-sm" onClick={() => setConfigAgent(null)}>{t("aagents.close")}</button>
              </div>
            </div>
            <div className="panel-body">
              <p className="hint">{t("aagents.cfg.hint")}</p>
              {configLoading ? (
                <p className="hint" role="status">{t("aagents.cfg.loading")}</p>
              ) : (
                <div role="region" tabIndex={0} aria-label={t("aagents.cfg.contentAria")} style={{ overflowX: "auto" }}>
                  <pre className="box-console mono" style={{ margin: 0, fontSize: "var(--fs-small)" }}>{configYaml}</pre>
                </div>
              )}
              <span role="status" className="sr-only">{copied ? t("aagents.cfg.copiedStatus") : ""}</span>
            </div>
          </section>
        )}

        {/* Agent-Liste mit Endpoints */}
        {loading ? (
          <p className="hint" role="status">{t("aagents.loading")}</p>
        ) : agents.length === 0 ? (
          !error && <div className="card-empty">{t("aagents.empty")}</div>
        ) : (
          agents.map(agent => {
            const agentEndpoints = endpoints.filter(ep => ep.agent_id === agent.id);
            const h = health[agent.id];
            return (
              <section key={agent.id} className="panel" aria-label={agent.name}>
                <div className="panel-head" style={{ flexWrap: "wrap" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
                    <h2>{agent.name}</h2>
                    <span className="mono hint">{agent.scheme}://{agent.fqdn}:{agent.daemon_connect}</span>
                    <StatusBadge status={agent.is_active ? "active" : "inactive"} size="sm" />
                    {h && (
                      <>
                        <StatusBadge status={h.health_status} size="sm" />
                        <DaemonInfo {...h} />
                      </>
                    )}
                  </div>
                  <div className="row-actions" style={{ marginTop: 0 }}>
                    <button type="button" className="btn btn-sm" onClick={() => startEdit(agent)} aria-label={t("aagents.editAria", { name: agent.name })}>
                      <Icon name="pencil" size={13} />{t("aagents.edit")}
                    </button>
                    <button type="button" className="btn btn-sm" onClick={() => openConfig(agent)} aria-label={t("aagents.cfg.openAria", { name: agent.name })}>
                      <Icon name="download" size={13} />{t("aagents.cfg.open")}
                    </button>
                    <ConfirmButton
                      label={t("aagents.rotate")}
                      confirmMessage={t("aagents.rotateConfirm", { name: agent.name })}
                      onConfirm={() => rotateCredentials(agent)}
                      size="sm"
                    />
                  </div>
                </div>
                <div className="panel-body">
                  <div style={GRID}>
                    <div className="kv"><span>{t("aagents.tokenId")}</span><span className="mono">{agent.daemon_token_id ?? t("aagents.dash")}</span></div>
                    <div className="kv"><span>{t("aagents.listen")}</span><span className="mono">{agent.daemon_listen}</span></div>
                    <div className="kv"><span>{t("aagents.sftp")}</span><span className="mono">{agent.daemon_sftp}</span></div>
                    <div className="kv"><span>{t("aagents.data")}</span><span className="mono">{agent.daemon_base}</span></div>
                    <div className="kv"><span>{t("aagents.lastSeen")}</span><span>{agent.last_seen_at ? formatDateTime(agent.last_seen_at) : t("aagents.never")}</span></div>
                    {agent.behind_proxy && <div className="kv"><span>{t("aagents.proxy")}</span><span>{t("aagents.dash")}</span></div>}
                  </div>

                  {h && (
                    <div style={GRID}>
                      <LoadBar showLabel label={t("aagents.memory")} unit="MB" used={h.utilization.used_memory_mb}
                        total={h.capacity.effective_memory_mb} percent={h.utilization.memory_utilization} />
                      <LoadBar showLabel label={t("aagents.disk")} unit="MB" used={h.utilization.used_disk_mb}
                        total={h.capacity.effective_disk_mb} percent={h.utilization.disk_utilization} />
                      <LoadBar showLabel label={t("aagents.cpu")} unit="%" used={h.utilization.used_cpu_percent}
                        total={h.capacity.effective_cpu_percent} percent={h.utilization.cpu_utilization} />
                    </div>
                  )}

                  {agentEndpoints.length === 0 ? (
                    <p className="hint">{t("aagents.ep.none")}</p>
                  ) : (
                    <ScrollRegion label={t("aagents.ep.tableAria", { name: agent.name })}>
                      <table className="tbl tbl-cards">
                        <thead>
                          <tr>
                            <th scope="col">{t("aagents.ep.colId")}</th>
                            <th scope="col">{t("aagents.ep.colAddr")}</th>
                            <th scope="col">{t("aagents.ep.colStatus")}</th>
                            <th scope="col">{t("aagents.ep.colInstance")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {agentEndpoints.map(ep => (
                            <tr key={ep.id}>
                              <td data-label={t("aagents.ep.colId")}>{ep.id}</td>
                              <td data-label={t("aagents.ep.colAddr")} className="mono">{ep.ip}:{ep.port}</td>
                              <td data-label={t("aagents.ep.colStatus")}>
                                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                                  <span className={`dot ${ep.is_locked ? "dot-danger" : ep.instance_id ? "dot-warn" : "dot-ok"}`} aria-hidden="true" />
                                  {ep.is_locked ? t("aagents.ep.locked") : ep.instance_id ? t("aagents.ep.used") : t("aagents.ep.free")}
                                </span>
                              </td>
                              <td data-label={t("aagents.ep.colInstance")}>{ep.instance_id ? t("aagents.ep.instance", { id: ep.instance_id }) : t("aagents.dash")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </ScrollRegion>
                  )}
                </div>
              </section>
            );
          })
        )}
      </div>
    </PageLayout>
  );
}


// ── Agent-Formular (Erstellen & Bearbeiten) ─────────────

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

  return (
    <>
      <div style={GRID}>
        <div className="field">
          <label htmlFor={id("name")}>{t("aagents.f.name")} *</label>
          <input id={id("name")} className="inp" type="text" value={values.name} onChange={e => set("name", e.target.value)}
            placeholder={t("aagents.f.namePh")} required />
        </div>
        <div className="field">
          <label htmlFor={id("fqdn")}>{t("aagents.f.fqdn")} *</label>
          <input id={id("fqdn")} className="inp mono" type="text" value={values.fqdn} onChange={e => set("fqdn", e.target.value)}
            placeholder="node01.astra.dev" required />
        </div>
        <div className="field">
          <label htmlFor={id("scheme")}>{t("aagents.f.scheme")}</label>
          <select id={id("scheme")} className="inp" value={values.scheme} onChange={e => set("scheme", e.target.value)}>
            <option value="https">https</option>
            <option value="http">http</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={id("connect")}>{t("aagents.f.connect")}</label>
          <input id={id("connect")} className="inp mono" type="number" value={values.connect} min={1} max={65535}
            onChange={e => onChange({ ...values, connect: e.target.value, connectTouched: true })} />
        </div>
        <div className="field">
          <label htmlFor={id("listen")}>{t("aagents.f.listen")}</label>
          <input id={id("listen")} className="inp mono" type="number" value={values.listen} min={1} max={65535}
            onChange={e => onChange({
              ...values,
              listen: e.target.value,
              connect: values.connectTouched ? values.connect : e.target.value,
            })} />
        </div>
        <div className="field">
          <label htmlFor={id("sftp")}>{t("aagents.f.sftp")}</label>
          <input id={id("sftp")} className="inp mono" type="number" value={values.sftp} onChange={e => set("sftp", e.target.value)} min={1} max={65535} />
        </div>
        <div className="field">
          <label htmlFor={id("base")}>{t("aagents.f.base")}</label>
          <input id={id("base")} className="inp mono" type="text" value={values.base} onChange={e => set("base", e.target.value)} />
        </div>
        {showActive && (
          <div className="field">
            <label htmlFor={id("upload")}>{t("aagents.f.upload")}</label>
            <input id={id("upload")} className="inp mono" type="number" value={values.uploadSize} onChange={e => set("uploadSize", e.target.value)} min={1} />
          </div>
        )}
      </div>
      <fieldset className="fieldset">
        <legend className="panel-title" style={{ marginBottom: 10 }}>{t("aagents.f.capacity")}</legend>
        <div style={GRID}>
          {([
            ["memory-total", t("aagents.f.memTotal"), "memoryTotal", true],
            ["disk-total", t("aagents.f.diskTotal"), "diskTotal", true],
            ["cpu-total", t("aagents.f.cpuTotal"), "cpuTotal", false],
          ] as const).map(([key, label, field, needed]) => {
            // Beim Anlegen Pflicht (> 0); beim Bearbeiten bleibt 0 erlaubt, wird aber als fehlend gekennzeichnet
            const required = needed && !showActive;
            const missing = needed && showActive && Number(values[field]) === 0;
            return (
              <div className="field" key={key}>
                <label htmlFor={id(key)}>{label}{required ? " *" : ""}</label>
                <input id={id(key)} className="inp mono" type="number" min={required ? 1 : 0} required={required} aria-required={required || undefined}
                  placeholder={needed ? (field === "memoryTotal" ? "16384" : "512000") : undefined}
                  aria-describedby={missing ? `${id(key)}-missing` : undefined}
                  value={values[field]} onChange={e => set(field, e.target.value)} />
                {missing && <small id={`${id(key)}-missing`} className="hint">{t("aagents.f.capacityMissingEdit")}</small>}
              </div>
            );
          })}
          {([
            ["memory-over", t("aagents.f.memOver"), "memoryOveralloc"],
            ["disk-over", t("aagents.f.diskOver"), "diskOveralloc"],
            ["cpu-over", t("aagents.f.cpuOver"), "cpuOveralloc"],
          ] as const).map(([key, label, field]) => (
            <div className="field" key={key}>
              <label htmlFor={id(key)}>{label}</label>
              <input id={id(key)} className="inp mono" type="number" min={0} max={1000} value={values[field]} onChange={e => set(field, e.target.value)} />
            </div>
          ))}
        </div>
        <p className="hint">{t("aagents.f.capacityPurpose")}</p>
        <p className="hint">{t("aagents.f.capacityHint")}</p>
      </fieldset>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--fs-small)" }}>
          <input type="checkbox" checked={values.behindProxy} onChange={e => set("behindProxy", e.target.checked)} />
          {t("aagents.f.behindProxy")}
        </label>
        {showActive && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--fs-small)" }}>
            <input type="checkbox" checked={values.isActive} onChange={e => set("isActive", e.target.checked)} />
            {t("aagents.f.active")}
          </label>
        )}
      </div>
      <p className="hint">{t("aagents.f.portHint")}</p>
    </>
  );
}
