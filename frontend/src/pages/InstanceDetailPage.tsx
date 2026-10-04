import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  api,
  type Instance,
  type Blueprint,
  type Order,
  type PowerSignal,
  type ResourceStats,
} from "../services/api";
import { hasRunningOrder, ORDER_END_NOTICE } from "../lib/orders";
import { instanceState, isRunning, orderForInstance } from "../lib/dashboard";
import { useCheckout } from "../hooks/useCheckout";
import { DeleteInstanceForm } from "../components/DeleteInstanceForm";
import { SftpAccess } from "../components/SftpAccess";
import { ServerConsole } from "../components/ServerConsole";
import { FileBrowser } from "../components/FileBrowser";
import { BackupManager } from "../components/BackupManager";
import { CollaboratorManager } from "../components/CollaboratorManager";
import { RoutineManager } from "../components/RoutineManager";
import { ActivityLog } from "../components/ActivityLog";
import { Tabs } from "../components/server/Tabs";
import { ConnectionPanel, ResourcesPanel, TermPanel } from "../components/server/ServerAside";
import { Icon } from "../components/ui/Icon";
import { t } from "../i18n";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState,
  Toast, useToast,
} from "../components/ui";

type TabKey = "console" | "files" | "backups" | "settings";
const TAB_KEYS: TabKey[] = ["console", "files", "backups", "settings"];

export function InstanceDetailPage() {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: TabKey = TAB_KEYS.includes(tabParam as TabKey) ? (tabParam as TabKey) : "console";
  const setTab = (key: TabKey) => setSearchParams(key === "console" ? {} : { tab: key }, { replace: true });

  const [instance, setInstance] = useState<Instance | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [resources, setResources] = useState<ResourceStats | null>(null);
  const [order, setOrder] = useState<Order | undefined>(undefined);
  const [onlinePayment, setOnlinePayment] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [orderNotice, setOrderNotice] = useState<string | null>(null);
  const { pay } = useCheckout(toast.error);

  // Gehört die Instance zu einer laufenden Bestellung, endet diese mit dem Löschen (ohne Erstattung)
  const startDeleting = async () => {
    setDeleting(true);
    try {
      const orders = await api.getMyOrders();
      setOrderNotice(hasRunningOrder(orders, uuid) ? ORDER_END_NOTICE : null);
    } catch {
      setOrderNotice(null);
    }
  };

  // Variable editing
  const [varEdits, setVarEdits] = useState<Record<string, string>>({});
  const [varSaving, setVarSaving] = useState(false);

  const loadInstance = useCallback(async () => {
    if (!uuid) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getClientInstance(uuid);
      setInstance(data);
      if (data.blueprint_id) {
        try {
          const bps = await api.getBlueprints();
          const bp = bps.find(b => b.id === data.blueprint_id) ?? null;
          setBlueprint(bp);
          if (bp?.variables) {
            const initial: Record<string, string> = {};
            for (const v of bp.variables) {
              if (v.user_viewable || v.user_editable) {
                initial[v.env_var] = data.variable_values?.[v.env_var] ?? v.default_value ?? "";
              }
            }
            setVarEdits(initial);
          }
        } catch {
          // Blueprint is best-effort
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t("srv.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [uuid]);

  const loadResources = useCallback(async () => {
    if (!uuid) return;
    try {
      const data = await api.getInstanceResources(uuid);
      setResources(data);
    } catch {
      // Still silently – Resources sind optional
    }
  }, [uuid]);

  // Laufzeit-Angaben aus der Bestellung (best effort: Mitbenutzer haben keine eigene Bestellung)
  useEffect(() => {
    if (!uuid) return;
    let alive = true;
    Promise.all([api.getMyOrders().catch(() => [] as Order[]), api.getBillingInfo().catch(() => null)]).then(([orders, billing]) => {
      if (!alive) return;
      setOrder(orderForInstance(orders, uuid));
      if (billing) setOnlinePayment(billing.online_payment);
    });
    return () => { alive = false; };
  }, [uuid]);

  useEffect(() => {
    loadInstance();
    loadResources();
  }, [loadInstance, loadResources]);

  // Auto-Refresh alle 5 Sekunden für Resources
  useEffect(() => {
    const interval = setInterval(loadResources, 5000);
    return () => clearInterval(interval);
  }, [loadResources]);

  const handlePower = async (signal: PowerSignal) => {
    if (!uuid) return;
    try {
      setActing(true);
      setError(null);
      const result = await api.sendPowerAction(uuid, signal);
      toast.success(result.message);
      setTimeout(() => { loadInstance(); loadResources(); }, 500);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("srv.powerFailed"));
    } finally {
      setActing(false);
    }
  };

  const handleReinstall = async () => {
    if (!uuid) return;
    try {
      setActing(true);
      setError(null);
      const result = await api.reinstallInstance(uuid);
      toast.success(result.message);
      await loadInstance();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("srv.reinstallError"));
    } finally {
      setActing(false);
    }
  };

  const handleSaveVariables = async () => {
    if (!uuid) return;
    try {
      setVarSaving(true);
      const result = await api.updateVariableValues(uuid, varEdits);
      if (result.rejected && result.rejected.length > 0) {
        toast.error(t("srv.varRejected", { list: result.rejected.join(", ") }));
      } else {
        toast.success(t("srv.varSaved"));
      }
      await loadInstance();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("srv.varError"));
    } finally {
      setVarSaving(false);
    }
  };

  const renew = async (o: Order) => {
    const outcome = await pay(o);
    if (outcome === "manual") { setOnlinePayment(false); navigate("/orders"); }
  };

  const back = { to: "/", label: t("dash.title") };

  if (loading && !instance) {
    return (
      <PageLayout title={t("srv.pageTitle")} back={back}>
        <LoadingState message={t("srv.loading")} />
      </PageLayout>
    );
  }

  if (error && !instance) {
    return (
      <PageLayout title={t("srv.pageTitle")} back={back}>
        <ErrorState message={error} onRetry={loadInstance} />
      </PageLayout>
    );
  }

  if (!instance) return null;

  const status = instance.status ?? "ready";
  const viewableVars = blueprint?.variables?.filter(v => v.user_viewable || v.user_editable) ?? [];
  const isOwner = instance.role === "owner";
  const ready = status === "ready";
  const running = resources ? resources.container_status === "running" : isRunning(instance);
  const badge = instanceState({ status: instance.status, container_state: resources ? resources.container_status : instance.container_state });

  const powerActions = (
    <>
      <button type="button" className="btn btn-sm" disabled={acting || !ready || running} onClick={() => handlePower("start")}>
        <Icon name="play" size={12} />{t("dash.start")}
      </button>
      <button type="button" className="btn btn-sm" disabled={acting || !ready || !running} onClick={() => handlePower("restart")}>
        <Icon name="restart" size={13} />{t("dash.restart")}
      </button>
      <button type="button" className="btn btn-sm btn-danger-text" disabled={acting || !ready || !running} onClick={() => handlePower("stop")}>
        <Icon name="stop" size={12} />{t("dash.stop")}
      </button>
      <button type="button" className="btn btn-sm btn-danger-text" style={{ borderColor: "var(--danger-border)" }} disabled={acting || !ready}
        title={t("srv.killTitle")}
        onClick={() => { if (confirm(t("srv.killConfirm"))) handlePower("kill"); }}>
        {t("srv.kill")}
      </button>
    </>
  );

  const subtitle = (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <StatusBadge status={badge} />
      <span className="mono" style={{ fontSize: 12, color: "var(--text-3)" }}>{instance.uuid.slice(0, 8)}</span>
      {instance.description && <span>{instance.description}</span>}
    </span>
  );

  const tabs = [
    { key: "console" as const, label: t("srv.tabConsole") },
    { key: "files" as const, label: t("srv.tabFiles") },
    { key: "backups" as const, label: t("srv.tabBackups") },
    { key: "settings" as const, label: t("srv.tabSettings") },
  ];

  return (
    <PageLayout title={instance.name} subtitle={subtitle} actions={powerActions} back={back} maxWidth={1200}>
      <Toast {...toast} />

      <div className="stack" style={{ gap: 16 }}>
        {/* Suspension-Banner (M29) */}
        {instance.status === "suspended" && (
          <div role="alert" className="banner banner-warn">
            <span className="dot dot-warn" aria-hidden="true" />
            <span className="banner-text">
              <strong>{t("srv.suspendedTitle")}</strong>
              {instance.suspended_reason && <span> — {instance.suspended_reason}</span>}
              <span style={{ display: "block", fontSize: 13, color: "var(--text-2)" }}>{t("srv.suspendedText")}</span>
            </span>
          </div>
        )}

        {(status === "provisioning" || status === "reinstalling") && (
          <div role="status" className="banner banner-info">
            <span className="banner-text">{status === "reinstalling" ? t("srv.reinstalling") : t("srv.provisioning")}</span>
          </div>
        )}

        {(status === "provision_failed" || status === "reinstall_failed") && (
          <div role="alert" className="banner banner-danger">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text">{status === "reinstall_failed" ? t("srv.reinstallFailed") : t("srv.provisionFailed")}</span>
            {isOwner && <button type="button" className="btn btn-sm" disabled={acting} onClick={handleReinstall}>🔄 {t("srv.reinstall")}</button>}
          </div>
        )}

        {error && <ErrorState message={error} />}

        <Tabs tabs={tabs} active={tab} onChange={setTab} label={t("srv.tabs")} idPrefix="srv" />

        <div className="detail-layout">
          <div className="detail-main" role="tabpanel" id="srv-panel" aria-labelledby={`srv-tab-${tab}`}>
            {tab === "console" && <ServerConsole instanceUuid={instance.uuid} />}

            {tab === "files" && (
              <section className="card" aria-label={t("srv.tabFiles")}><FileBrowser instanceUuid={instance.uuid} /></section>
            )}

            {tab === "backups" && (
              <section className="card" aria-label={t("srv.tabBackups")}><BackupManager instanceUuid={instance.uuid} /></section>
            )}

            {tab === "settings" && (
              <>
                {viewableVars.length > 0 && (
                  <section className="card" aria-labelledby="set-vars">
                    <h2 id="set-vars" className="section-title" style={{ margin: 0 }}>{t("srv.variables")}</h2>
                    <div style={{ overflowX: "auto" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                          <tr style={{ background: "var(--surface-2)" }}>
                            <th scope="col" style={thSmall}>{t("srv.varName")}</th>
                            <th scope="col" style={thSmall}>{t("srv.varValue")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {viewableVars.map(v => (
                            <tr key={v.env_var} style={{ borderBottom: "1px solid var(--border-soft)" }}>
                              <td style={{ padding: 8, verticalAlign: "middle" }}>
                                <label htmlFor={`var-${v.env_var}`} style={{ fontWeight: 600, fontSize: 13 }}>{v.name}</label>
                                {v.description && <div className="hint" style={{ fontSize: 12 }}>{v.description}</div>}
                                <code style={{ fontSize: 11, color: "var(--text-3)" }}>{v.env_var}</code>
                              </td>
                              <td style={{ padding: 8, verticalAlign: "middle" }}>
                                {v.user_editable ? (
                                  <input id={`var-${v.env_var}`} className="inp" type="text" value={varEdits[v.env_var] ?? ""}
                                    onChange={e => setVarEdits(prev => ({ ...prev, [v.env_var]: e.target.value }))} />
                                ) : (
                                  <span className="mono" style={{ fontSize: 13 }}>{varEdits[v.env_var] ?? "–"}</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {viewableVars.some(v => v.user_editable) && (
                      <div>
                        <button type="button" className="btn btn-primary" onClick={handleSaveVariables} disabled={varSaving}>
                          {varSaving ? t("srv.varSaving") : t("srv.varSave")}
                        </button>
                      </div>
                    )}
                  </section>
                )}

                <SftpAccess instance={instance} />

                {isOwner && (
                  <section className="card" aria-labelledby="set-routines">
                    <h2 id="set-routines" className="section-title" style={{ margin: 0 }}>{t("srv.routines")}</h2>
                    <RoutineManager instanceUuid={instance.uuid} />
                  </section>
                )}

                <section className="card" aria-labelledby="set-collab">
                  <h2 id="set-collab" className="section-title" style={{ margin: 0 }}>{t("srv.collaborators")}</h2>
                  <CollaboratorManager instanceUuid={instance.uuid} isOwner={isOwner} />
                </section>

                <section className="card" aria-labelledby="set-activity">
                  <h2 id="set-activity" className="section-title" style={{ margin: 0 }}>{t("srv.activity")}</h2>
                  <ActivityLog instanceUuid={instance.uuid} />
                </section>

                <section className="card" aria-labelledby="set-details">
                  <h2 id="set-details" className="section-title" style={{ margin: 0 }}>{t("srv.details")}</h2>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <tbody>
                      <DetailRow label="UUID" value={instance.uuid} mono />
                      <DetailRow label="Lifecycle" value={status} />
                      <DetailRow label="Container" value={instance.container_state ?? "–"} />
                      <DetailRow label="Agent" value={`#${instance.agent_id}`} />
                      <DetailRow label="Blueprint" value={blueprint ? `${blueprint.name} (#${instance.blueprint_id})` : `#${instance.blueprint_id}`} />
                      <DetailRow label="Owner" value={`#${instance.owner_id}`} />
                      <DetailRow label="Image" value={instance.image ?? "–"} mono />
                      <DetailRow label="Startup" value={instance.startup_command ?? "–"} mono />
                    </tbody>
                  </table>
                </section>

                <section className="card" aria-labelledby="set-limits">
                  <h2 id="set-limits" className="section-title" style={{ margin: 0 }}>{t("srv.limits")}</h2>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <tbody>
                      <DetailRow label="Memory" value={`${instance.memory} MB`} mono />
                      <DetailRow label="Swap" value={`${instance.swap} MB`} mono />
                      <DetailRow label="Disk" value={`${instance.disk} MB`} mono />
                      <DetailRow label="CPU" value={`${instance.cpu} %`} mono />
                      <DetailRow label="IO" value={`${instance.io}`} mono />
                      <DetailRow label="Endpoint" value={instance.primary_endpoint_id ? `#${instance.primary_endpoint_id}` : "–"} mono />
                    </tbody>
                  </table>
                </section>

                {/* Gefahrenzone: nur Owner */}
                {isOwner && (
                  <section className="card" aria-labelledby="set-danger" style={{ borderColor: "var(--danger-border)" }}>
                    <h2 id="set-danger" className="section-title text-danger" style={{ margin: 0 }}>{t("srv.danger")}</h2>
                    {instance.status === "suspended" ? (
                      <p className="hint" style={{ margin: 0 }}>{t("srv.suspendedDelete")}</p>
                    ) : deleting ? (
                      <DeleteInstanceForm
                        name={instance.name}
                        status={instance.status}
                        notice={orderNotice}
                        idPrefix="detail-del"
                        onCancel={() => setDeleting(false)}
                        onDelete={async () => {
                          await api.deleteInstance(instance.uuid, instance.name);
                          // Toast auf dem Dashboard anzeigen (die Detailseite wird verlassen)
                          navigate("/", { state: { toast: t("srv.deleted", { name: instance.name }) } });
                        }}
                      />
                    ) : (
                      <div>
                        <button type="button" onClick={startDeleting} className="btn btn-danger-text" style={{ borderColor: "var(--danger-border)" }}>
                          {t("srv.deleteBtn")}
                        </button>
                      </div>
                    )}
                  </section>
                )}
              </>
            )}
          </div>

          <aside className="detail-aside" aria-label={t("srv.pageTitle")}>
            <ConnectionPanel instance={instance} />
            <ResourcesPanel instance={instance} stats={resources} />
            <TermPanel order={order} onlinePayment={onlinePayment} onRenew={renew} />
          </aside>
        </div>
      </div>
    </PageLayout>
  );
}

// ── Hilfskomponenten ───────────────────────────────────

const thSmall: React.CSSProperties = { padding: "6px 8px", textAlign: "left", fontSize: 12, fontWeight: 500, color: "var(--text-2)" };

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <tr>
      <td style={{ padding: "6px 0", fontWeight: 500, fontSize: 13, width: 120, color: "var(--text-2)" }}>{label}</td>
      <td className={mono ? "mono" : undefined} style={{ padding: "6px 0", fontSize: 13, overflowWrap: "anywhere" }}>{value}</td>
    </tr>
  );
}
