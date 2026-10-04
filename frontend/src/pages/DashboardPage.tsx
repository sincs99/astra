import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, type Instance } from "../services/api";
import { ConnectionAddress } from "../components/ConnectionAddress";
import { BillingTickCard } from "../components/BillingTickCard";
import { OpenOrdersCard } from "../components/OpenOrdersCard";
import { useCurrentUser } from "../hooks/useCurrentUser";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { PageLayout, AutoRefreshToggle, Toast, useToast, StatusBadge, LoadingState, ErrorState, EmptyState, cardStyle, linkStyle } from "../components/ui";

export function DashboardPage() {
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  // Meldung von der vorherigen Seite (z.B. nach dem Löschen einer Instance), nur einmal anzeigen
  useEffect(() => {
    const message = (location.state as { toast?: string } | null)?.toast;
    if (message) {
      toast.success(message);
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const user = useCurrentUser();

  return (
    <PageLayout title="Dashboard" maxWidth={900}>
      <Toast {...toast} />
      <p style={{ color: "var(--fg-muted)", marginTop: -12, marginBottom: 24, fontSize: 14 }}>
        Eingeloggt als {user ? user.username : "…"}
      </p>

      {user?.is_admin && <BillingTickCard onlyWhenUnhealthy />}
      {user?.is_admin && <OpenOrdersCard />}

      {error && <ErrorState message={error} onRetry={() => load()} />}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        <h2 style={{ fontSize: 18, margin: 0 }}>Meine Server</h2>
        <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />
      </div>

      {loading ? (
        <LoadingState />
      ) : instances.length === 0 ? (
        <div>
          <EmptyState
            message={user?.is_admin
              ? "Keine Instances vorhanden. Erstelle eine über den Admin-Bereich."
              : "Du hast noch keinen Server."}
            icon="📦"
          />
          {!user?.is_admin && (
            <p style={{ textAlign: "center" }}>
              <Link to="/shop" style={linkStyle}>Zum Shop und Server bestellen</Link>
            </p>
          )}
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {instances.map((inst) => (
            <div
              key={inst.id}
              onClick={() => navigate(`/instances/${inst.uuid}`)}
              style={{ ...cardStyle, cursor: "pointer", transition: "border-color 0.15s" }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--c-blue)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong style={{ fontSize: 16 }}>{inst.name}</strong>
                  {inst.description && (
                    <span style={{ color: "var(--fg-muted)", marginLeft: 8, fontSize: 14 }}>
                      {inst.description}
                    </span>
                  )}
                </div>
                <StatusBadge status={inst.status ?? "ready"} />
              </div>
              <div style={{ marginTop: 8, fontSize: 13, color: "var(--fg-muted)" }}>
                <code style={{ fontSize: 11 }}>{inst.uuid}</code>
                <span style={{ marginLeft: 16 }}>
                  {inst.memory} MB RAM &middot; {inst.disk} MB Disk &middot; {inst.cpu}% CPU
                </span>
              </div>
              {inst.connection && (
                <div style={{ marginTop: 8 }}>
                  <ConnectionAddress connection={inst.connection} compact />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </PageLayout>
  );
}
