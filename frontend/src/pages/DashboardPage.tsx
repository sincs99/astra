import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Instance, getSimulatedUserId } from "../services/api";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { PageLayout, AutoRefreshToggle, StatusBadge, LoadingState, ErrorState, EmptyState, cardStyle } from "../components/ui";

export function DashboardPage() {
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("dashboard");

  const load = async (silent = false) => {
    try {
      if (!silent) { setLoading(true); setError(null); }
      const data = await api.getClientInstances();
      setInstances(data);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useAutoRefresh(() => load(true), 15000, autoRefresh);

  const userId = getSimulatedUserId();

  return (
    <PageLayout title="Dashboard" maxWidth={900}>
      <p style={{ color: "#888", marginTop: -12, marginBottom: 24, fontSize: 14 }}>
        Eingeloggt als User #{userId}
      </p>

      {error && <ErrorState message={error} onRetry={() => load()} />}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, margin: 0 }}>Meine Instances</h2>
        <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />
      </div>

      {loading ? (
        <LoadingState />
      ) : instances.length === 0 ? (
        <EmptyState message="Keine Instances vorhanden. Erstelle eine ueber den Admin-Bereich." icon="📦" />
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {instances.map((inst) => (
            <div
              key={inst.id}
              onClick={() => navigate(`/instances/${inst.uuid}`)}
              style={{ ...cardStyle, cursor: "pointer", transition: "border-color 0.15s" }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#1976d2")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e0e0e0")}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong style={{ fontSize: 16 }}>{inst.name}</strong>
                  {inst.description && (
                    <span style={{ color: "#888", marginLeft: 8, fontSize: 14 }}>
                      {inst.description}
                    </span>
                  )}
                </div>
                <StatusBadge status={inst.status ?? "ready"} />
              </div>
              <div style={{ marginTop: 8, fontSize: 13, color: "#666" }}>
                <code style={{ fontSize: 11 }}>{inst.uuid}</code>
                <span style={{ marginLeft: 16 }}>
                  {inst.memory} MB RAM &middot; {inst.disk} MB Disk &middot; {inst.cpu}% CPU
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageLayout>
  );
}
