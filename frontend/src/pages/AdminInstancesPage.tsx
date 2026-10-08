import { TransferInstanceForm } from "../components/TransferInstanceForm";
import { DeleteInstanceForm } from "../components/DeleteInstanceForm";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { Fragment, useEffect, useState } from "react";
import {
  api,
  type Instance,
  type User,
  type Agent,
  type Blueprint,
  type Endpoint,
} from "../services/api";
import { t } from "../i18n";
import { PageLayout, StatusBadge, Toast, useToast, ConfirmButton, ScrollRegion } from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { Field, ErrorBanner, fieldGrid as grid } from "../components/admin/AdminField";

export function AdminInstancesPage() {
  const toast = useToast();
  const [instances, setInstances] = useState<Instance[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [blueprints, setBlueprints] = useState<Blueprint[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

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
  const [deletingUuid, setDeletingUuid] = useState<string | null>(null);

  const handleTransfer = async (inst: Instance, targetAgentId: number) => {
    await api.transferInstance(inst.uuid, targetAgentId);
    toast.success(t("ainst.inst.transferStarted", { name: inst.name }));
    setTransferringUuid(null);
    await loadAll();
  };

  const loadAll = async () => {
    try {
      setLoading(true);
      setLoadError(null);
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
      setLoadError(err instanceof Error ? err.message : t("ainst.inst.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("instances");
  // Nur die Instance-Liste still aktualisieren; Formulare und Stammdaten bleiben unberuehrt
  useAutoRefresh(() => { api.getInstances().then(setInstances).catch(() => {}); }, 15000, autoRefresh);

  const freeEndpoints = endpoints.filter(
    ep => ep.agent_id === agentId && ep.instance_id === null && !ep.is_locked
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !ownerId || !blueprintId) return;

    try {
      setSubmitting(true);
      setFormError(null);
      await api.createInstance({
        name: name.trim(),
        description: description.trim() || undefined,
        owner_id: ownerId as number,
        agent_id: agentId ? (agentId as number) : null,
        blueprint_id: blueprintId as number,
        endpoint_id: endpointId ? (endpointId as number) : undefined,
        memory, swap, disk, io, cpu,
      });
      setName(""); setDescription(""); setOwnerId(""); setAgentId("");
      setBlueprintId(""); setEndpointId("");
      setMemory(512); setSwap(0); setDisk(1024); setIo(500); setCpu(100);
      toast.success(t("ainst.inst.created"));
      await loadAll();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t("ainst.inst.createFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  const autoToggle = (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--fs-small)", color: "var(--text-2)" }}>
      <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
      {t("common.autoRefresh", { seconds: 15 })}
    </label>
  );

  const col = {
    name: t("ainst.inst.colName"), uuid: t("ainst.inst.colUuid"), status: t("ainst.inst.colStatus"),
    owner: t("ainst.inst.colOwner"), agent: t("ainst.inst.colAgent"), endpoint: t("ainst.inst.colEndpoint"),
    resources: t("ainst.inst.colResources"), actions: t("ainst.inst.colActions"),
  };

  const resourceFields = [
    { id: "memory", label: t("ainst.inst.memory"), value: memory, set: setMemory, min: 64 },
    { id: "swap", label: t("ainst.inst.swap"), value: swap, set: setSwap, min: 0 },
    { id: "disk", label: t("ainst.inst.disk"), value: disk, set: setDisk, min: 256 },
    { id: "io", label: t("ainst.inst.io"), value: io, set: setIo, min: 10, max: 1000 },
    { id: "cpu", label: t("ainst.inst.cpu"), value: cpu, set: setCpu, min: 1 },
  ];

  return (
    <PageLayout title={t("ainst.inst.title")} actions={autoToggle}>
      <Toast {...toast} />
      <div className="stack">

        {/* ── Erstell-Formular ── */}
        <section className="panel" aria-labelledby="inst-new-title">
          <div className="panel-head"><h2 id="inst-new-title">{t("ainst.inst.newTitle")}</h2></div>
          <form className="panel-body" onSubmit={handleSubmit}>
            <p className="hint">{t("ainst.required")}</p>
            {formError && <ErrorBanner message={formError} />}
            <div style={grid(220)}>
              <Field label={t("ainst.inst.name")}>
                <input className="inp" type="text" value={name} onChange={e => setName(e.target.value)} placeholder={t("ainst.inst.namePh")} required aria-required="true" />
              </Field>
              <Field label={t("ainst.inst.description")}>
                <input className="inp" type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder={t("ainst.inst.optional")} />
              </Field>
            </div>

            <div style={grid(220)}>
              <Field label={t("ainst.inst.owner")}>
                <select className="inp" value={ownerId} onChange={e => setOwnerId(e.target.value ? Number(e.target.value) : "")} required aria-required="true">
                  <option value="">{t("ainst.choose")}</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                </select>
              </Field>
              <Field label={t("ainst.inst.agent")}>
                <select className="inp" value={agentId} onChange={e => { setAgentId(e.target.value ? Number(e.target.value) : ""); setEndpointId(""); }}>
                  <option value="">{t("ainst.inst.agentAuto")}</option>
                  {agents.map(a => <option key={a.id} value={a.id}>{a.name} ({a.fqdn})</option>)}
                </select>
              </Field>
              <Field label={t("ainst.inst.blueprint")}>
                <select className="inp" value={blueprintId} onChange={e => setBlueprintId(e.target.value ? Number(e.target.value) : "")} required aria-required="true">
                  <option value="">{t("ainst.choose")}</option>
                  {blueprints.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
                </select>
              </Field>
            </div>

            {agentId ? (
              <Field label={t("ainst.inst.endpoint")}>
                <select className="inp" value={endpointId} onChange={e => setEndpointId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">{t("ainst.inst.endpointAuto")}</option>
                  {freeEndpoints.map(ep => <option key={ep.id} value={ep.id}>{ep.ip}:{ep.port}</option>)}
                </select>
                {freeEndpoints.length === 0 && <span className="hint text-danger" role="status">{t("ainst.inst.noFreeEndpoints")}</span>}
              </Field>
            ) : (
              <p className="hint">{t("ainst.inst.autoHint")}</p>
            )}

            <fieldset className="fieldset">
              <legend className="panel-title">{t("ainst.inst.resources")}</legend>
              <div style={grid(130)}>
                {resourceFields.map(f => (
                  <Field key={f.id} label={f.label}>
                    <input className="inp mono" type="number" value={f.value} onChange={e => f.set(Number(e.target.value))} min={f.min} max={f.max} />
                  </Field>
                ))}
              </div>
            </fieldset>

            <div className="row-actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? t("ainst.inst.creating") : t("ainst.inst.create")}
              </button>
            </div>
          </form>
        </section>

        {/* ── Instance-Liste ── */}
        <section className="panel" aria-labelledby="inst-list-title">
          <div className="panel-head"><h2 id="inst-list-title">{t("ainst.inst.listTitle")}</h2></div>
          {loadError && (
            <div className="panel-body">
              <ErrorBanner message={loadError} title={t("ainst.errorTitle")} retryLabel={t("ainst.retry")} onRetry={loadAll} />
            </div>
          )}
          {loading ? (
            <div className="panel-body"><p className="hint" role="status" aria-busy="true">{t("ainst.inst.loading")}</p></div>
          ) : instances.length === 0 ? (
            !loadError && <div className="panel-body"><p className="hint">{t("ainst.inst.empty")}</p></div>
          ) : (
            <ScrollRegion label={t("ainst.inst.tableLabel")}>
              <table className="tbl tbl-cards">
                <thead>
                  <tr>
                    <th scope="col">{col.name}</th>
                    <th scope="col">{col.uuid}</th>
                    <th scope="col">{col.status}</th>
                    <th scope="col">{col.owner}</th>
                    <th scope="col">{col.agent}</th>
                    <th scope="col">{col.endpoint}</th>
                    <th scope="col">{col.resources}</th>
                    <th scope="col">{col.actions}</th>
                  </tr>
                </thead>
                <tbody>
                  {instances.map(inst => {
                    const owner = users.find(u => u.id === inst.owner_id);
                    const agent = agents.find(a => a.id === inst.agent_id);
                    const ep = endpoints.find(e => e.id === inst.primary_endpoint_id);
                    const isTransferring = transferringUuid === inst.uuid;
                    return (
                      <Fragment key={inst.id}>
                        <tr>
                          <td data-label={col.name}>
                            <strong>{inst.name}</strong>
                            {inst.description && <div className="hint">{inst.description}</div>}
                          </td>
                          <td data-label={col.uuid}><span className="mono">{inst.uuid.substring(0, 8)}…</span></td>
                          <td data-label={col.status}><StatusBadge status={inst.status ?? "ready"} size="sm" /></td>
                          <td data-label={col.owner}>{owner?.username ?? t("ainst.none")}</td>
                          <td data-label={col.agent}>{agent?.name ?? t("ainst.none")}</td>
                          <td data-label={col.endpoint}>
                            {/* Öffentliche Verbindungsadresse (Host:Port), auch wenn der Endpoint automatisch gewählt wurde; die Endpoint-Liste zeigt nur die Bind-IP */}
                            <span className="mono">{inst.connection?.address ?? (ep ? `${ep.ip}:${ep.port}` : t("ainst.none"))}</span>
                            {inst.connection?.address && ep && <div className="hint mono">{`${ep.ip}:${ep.port}`}</div>}
                          </td>
                          <td data-label={col.resources}>
                            <span className="mono hint">{inst.memory} MB / {inst.disk} MB / {inst.cpu}%</span>
                          </td>
                          <td data-label={col.actions}>
                            <div className="row-actions" style={{ marginTop: 0 }}>
                              <button
                                type="button" className="btn btn-sm"
                                onClick={() => { setTransferringUuid(inst.uuid); setDeletingUuid(null); }}
                                title={t("ainst.inst.transferTitle")}
                              >
                                {t("ainst.inst.transfer")}
                              </button>
                              {inst.status === "suspended" ? (
                                <ConfirmButton
                                  label={t("ainst.inst.unsuspend")}
                                  confirmMessage={t("ainst.inst.confirmUnsuspend", { name: inst.name })}
                                  size="sm"
                                  onConfirm={async () => {
                                    await api.unsuspendInstance(inst.uuid);
                                    toast.success(t("ainst.inst.unsuspended", { name: inst.name }));
                                    await loadAll();
                                  }}
                                />
                              ) : (
                                <ConfirmButton
                                  label={t("ainst.inst.suspend")}
                                  confirmMessage={t("ainst.inst.confirmSuspend", { name: inst.name })}
                                  size="sm"
                                  danger
                                  onConfirm={async () => {
                                    await api.suspendInstance(inst.uuid);
                                    toast.success(t("ainst.inst.suspended", { name: inst.name }));
                                    await loadAll();
                                  }}
                                />
                              )}
                              <button
                                type="button" className="btn btn-sm btn-danger-text"
                                onClick={() => { setDeletingUuid(inst.uuid); setTransferringUuid(null); }}
                                title={t("ainst.inst.deleteTitle")}
                              >
                                <Icon name="trash" size={14} />{t("ainst.inst.delete")}
                              </button>
                            </div>
                          </td>
                        </tr>
                        {isTransferring && (
                          <tr>
                            <td colSpan={8} style={{ background: "var(--danger-soft)" }}>
                              <TransferInstanceForm
                                instanceUuid={inst.uuid}
                                instanceName={inst.name}
                                agents={agents.filter(a => a.id !== inst.agent_id && a.is_active)}
                                idPrefix={`transfer-${inst.id}`}
                                onCancel={() => setTransferringUuid(null)}
                                onTransfer={(target) => handleTransfer(inst, target)}
                              />
                            </td>
                          </tr>
                        )}
                        {deletingUuid === inst.uuid && (
                          <tr>
                            <td colSpan={8} style={{ background: "var(--danger-soft)" }}>
                              <DeleteInstanceForm
                                name={inst.name}
                                status={inst.status}
                                allowForce
                                idPrefix={`del-${inst.id}`}
                                onCancel={() => setDeletingUuid(null)}
                                onDelete={async (force) => {
                                  const result = await api.adminDeleteInstance(inst.uuid, force);
                                  if (result.runner_cleanup === "failed") {
                                    toast.warning(t("ainst.inst.deletedCleanupFailed", { name: inst.name }));
                                  } else {
                                    toast.success(t("ainst.inst.deleted", { name: inst.name }));
                                  }
                                  setDeletingUuid(null);
                                  await loadAll();
                                }}
                              />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </ScrollRegion>
          )}
        </section>
      </div>
    </PageLayout>
  );
}
