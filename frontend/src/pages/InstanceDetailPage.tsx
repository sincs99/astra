import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  api,
  type Instance,
  type Blueprint,
  type PowerSignal,
  type ResourceStats,
} from "../services/api";
import { ServerConsole } from "../components/ServerConsole";
import { FileBrowser } from "../components/FileBrowser";
import { BackupManager } from "../components/BackupManager";
import { CollaboratorManager } from "../components/CollaboratorManager";
import { RoutineManager } from "../components/RoutineManager";
import { ActivityLog } from "../components/ActivityLog";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState,
  Toast, useToast,
  cardStyle, btnDefault, btnPrimary,
} from "../components/ui";

export function InstanceDetailPage() {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [instance, setInstance] = useState<Instance | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [resources, setResources] = useState<ResourceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

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
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
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
      setTimeout(() => loadInstance(), 500);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler bei Power-Aktion");
    } finally {
      setActing(false);
    }
  };

  const handleInstallCallback = async (successful: boolean) => {
    if (!uuid) return;
    try {
      setActing(true);
      setError(null);
      const result = await api.reportInstallResult(uuid, successful);
      toast.success(result.message);
      await loadInstance();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler");
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
      toast.error(err instanceof Error ? err.message : "Reinstall fehlgeschlagen");
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
        toast.error(`Nicht gespeichert: ${result.rejected.join(", ")}`);
      } else {
        toast.success("Variablen gespeichert.");
      }
      await loadInstance();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setVarSaving(false);
    }
  };

  if (loading) {
    return (
      <PageLayout title="Instance" maxWidth={700}>
        <LoadingState message="Instance wird geladen..." />
      </PageLayout>
    );
  }

  if (error && !instance) {
    return (
      <PageLayout title="Instance" maxWidth={700}>
        <ErrorState message={error} onRetry={loadInstance} />
        <button onClick={() => navigate("/")} style={btnDefault}>Zurueck</button>
      </PageLayout>
    );
  }

  if (!instance) return null;

  const status = instance.status ?? "ready";
  const viewableVars = blueprint?.variables?.filter(v => v.user_viewable || v.user_editable) ?? [];

  return (
    <PageLayout title={instance.name} maxWidth={700}>
      <Toast {...toast} />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: -12, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={() => navigate("/")} style={btnDefault}>Zurueck</button>
          <StatusBadge status={status} />
          {instance.container_state && (
            <StatusBadge status={instance.container_state} size="sm" />
          )}
        </div>
      </div>

      {instance.description && (
        <p style={{ color: "#888", marginTop: 4 }}>{instance.description}</p>
      )}

      {/* Suspension-Banner (M29) */}
      {instance.status === "suspended" && (
        <div style={{
          padding: "12px 16px", marginBottom: 16,
          backgroundColor: "#fff3e0", border: "1px solid #ffcc80",
          borderRadius: 8, color: "#e65100",
        }}>
          <strong>Instance gesperrt (suspendiert)</strong>
          {instance.suspended_reason && (
            <span style={{ marginLeft: 8 }}>— {instance.suspended_reason}</span>
          )}
          <div style={{ fontSize: 12, marginTop: 4, color: "#bf360c" }}>
            Operative Aktionen (Power, Dateien, Backups, Datenbanken, Routinen) sind blockiert.
            Nur ein Administrator kann die Sperre aufheben.
          </div>
        </div>
      )}

      {error && <ErrorState message={error} />}

      {/* Power-Aktionen */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Power</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button onClick={() => handlePower("start")} disabled={acting} style={powerBtn("#5cb85c")}>▶ Start</button>
          <button onClick={() => handlePower("stop")} disabled={acting} style={powerBtn("#f0ad4e")}>⏹ Stop</button>
          <button onClick={() => handlePower("restart")} disabled={acting} style={powerBtn("#5bc0de")}>🔄 Restart</button>
          <button onClick={() => handlePower("kill")} disabled={acting} style={powerBtn("#d9534f")}>✕ Kill</button>
        </div>

        {(status === "provisioning" || status === "reinstalling") && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eee" }}>
            <p style={{ fontSize: 13, color: "#888", margin: "0 0 8px" }}>
              {status === "reinstalling" ? "⏳ Reinstallation läuft..." : "⏳ Installation läuft..."}
            </p>
            <p style={{ fontSize: 12, color: "#aaa", margin: "0 0 8px" }}>Simuliere Install-Callback:</p>
            <button onClick={() => handleInstallCallback(true)} disabled={acting} style={{ ...btnDefault, marginRight: 8 }}>✅ Erfolgreich</button>
            <button onClick={() => handleInstallCallback(false)} disabled={acting} style={btnDefault}>❌ Fehlgeschlagen</button>
          </div>
        )}

        {(status === "provision_failed" || status === "reinstall_failed") && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eee" }}>
            <p style={{ fontSize: 13, color: "#d9534f", margin: "0 0 8px" }}>
              {status === "reinstall_failed" ? "❌ Reinstallation fehlgeschlagen" : "❌ Installation fehlgeschlagen"}
            </p>
            {instance.role === "owner" && (
              <button onClick={handleReinstall} disabled={acting} style={powerBtn("#f0ad4e")}>
                🔄 Reinstall
              </button>
            )}
          </div>
        )}
      </div>

      {/* Runtime Resources */}
      <div style={cardStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Runtime</h3>
          {resources && (
            <StatusBadge status={resources.container_status === "running" ? "running" : "stopped"} size="sm" />
          )}
        </div>

        {resources ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 12 }}>
            <ResourceBox label="CPU" value={`${resources.cpu_percent}%`} />
            <ResourceBox
              label="Memory"
              value={formatBytes(resources.memory_bytes)}
              sub={`/ ${formatBytes(resources.memory_limit_bytes)}`}
            />
            <ResourceBox label="Disk" value={formatBytes(resources.disk_bytes)} />
            <ResourceBox label="Net ↓" value={formatBytes(resources.network_rx_bytes)} />
            <ResourceBox label="Net ↑" value={formatBytes(resources.network_tx_bytes)} />
            <ResourceBox label="Uptime" value={formatUptime(resources.uptime_seconds)} />
          </div>
        ) : (
          <p style={{ color: "#888", marginTop: 8 }}>Runtime-Daten werden geladen...</p>
        )}
        <p style={{ fontSize: 11, color: "#aaa", marginBottom: 0, marginTop: 8 }}>
          Auto-Refresh alle 5 Sekunden
        </p>
      </div>

      {/* Variablen */}
      {viewableVars.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Variablen</h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e0e0e0" }}>
                <th style={{ padding: "6px 8px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#555" }}>Name</th>
                <th style={{ padding: "6px 8px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#555" }}>Wert</th>
              </tr>
            </thead>
            <tbody>
              {viewableVars.map(v => (
                <tr key={v.env_var} style={{ borderBottom: "1px solid #f0f0f0" }}>
                  <td style={{ padding: "8px", verticalAlign: "middle" }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{v.name}</div>
                    {v.description && <div style={{ fontSize: 11, color: "#888" }}>{v.description}</div>}
                    <code style={{ fontSize: 11, color: "#aaa" }}>{v.env_var}</code>
                  </td>
                  <td style={{ padding: "8px", verticalAlign: "middle" }}>
                    {v.user_editable ? (
                      <input
                        type="text"
                        value={varEdits[v.env_var] ?? ""}
                        onChange={e => setVarEdits(prev => ({ ...prev, [v.env_var]: e.target.value }))}
                        style={{ padding: "4px 8px", fontSize: 13, borderRadius: 4, border: "1px solid #ccc", width: "100%" }}
                      />
                    ) : (
                      <span style={{ fontSize: 13, fontFamily: "monospace" }}>{varEdits[v.env_var] ?? "–"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {viewableVars.some(v => v.user_editable) && (
            <div style={{ marginTop: 12 }}>
              <button onClick={handleSaveVariables} disabled={varSaving} style={{ ...btnPrimary, opacity: varSaving ? 0.6 : 1 }}>
                {varSaving ? "Speichern..." : "Variablen speichern"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Console */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Console</h3>
        <ServerConsole instanceUuid={instance.uuid} />
      </div>

      {/* Files */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Files</h3>
        <FileBrowser instanceUuid={instance.uuid} />
      </div>

      {/* Backups */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Backups</h3>
        <BackupManager instanceUuid={instance.uuid} />
      </div>

      {/* Routines */}
      {instance.role === "owner" && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Routines</h3>
          <RoutineManager instanceUuid={instance.uuid} />
        </div>
      )}

      {/* Collaborators */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Collaborators</h3>
        <CollaboratorManager
          instanceUuid={instance.uuid}
          isOwner={instance.role === "owner"}
        />
      </div>

      {/* Activity */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Activity</h3>
        <ActivityLog instanceUuid={instance.uuid} />
      </div>

      {/* Details */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Details</h3>
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
      </div>

      {/* Konfigurierte Limits */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Konfigurierte Limits</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          <ResourceBox label="Memory" value={`${instance.memory} MB`} />
          <ResourceBox label="Swap" value={`${instance.swap} MB`} />
          <ResourceBox label="Disk" value={`${instance.disk} MB`} />
          <ResourceBox label="CPU" value={`${instance.cpu}%`} />
          <ResourceBox label="IO" value={`${instance.io}`} />
          <ResourceBox label="Endpoint" value={instance.primary_endpoint_id ? `#${instance.primary_endpoint_id}` : "–"} />
        </div>
      </div>
    </PageLayout>
  );
}

// ── Hilfskomponenten ───────────────────────────────────

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <tr>
      <td style={{ padding: "6px 0", fontWeight: 600, fontSize: 13, width: 120 }}>{label}</td>
      <td style={{ padding: "6px 0", fontSize: 13, fontFamily: mono ? "monospace" : "inherit" }}>{value}</td>
    </tr>
  );
}

function ResourceBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ padding: 12, backgroundColor: "#f8f8f8", borderRadius: 6, textAlign: "center" }}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 600 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#aaa" }}>{sub}</div>}
    </div>
  );
}

// ── Formatierung ───────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function powerBtn(bg: string): React.CSSProperties {
  return { padding: "8px 16px", cursor: "pointer", border: "none", borderRadius: 4, color: "#fff", fontWeight: 600, fontSize: 13, backgroundColor: bg };
}
