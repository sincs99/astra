import { useEffect, useState } from "react";
import { api, type BillingStatus } from "../services/api";
import { formatTimeAgo } from "../lib/dates";
import { cardStyle, StatusBadge, statusLabel } from "./ui";

/**
 * Admin-System: Zustand des Billing-Ticks (Mahnung/Ablauf/Loeschung).
 * Mit onlyWhenUnhealthy (Dashboard) erscheint sie nur bei Stoerung.
 * Fehler (z.B. 404 bei aelterem Backend) blenden die Karte still aus.
 */
export function BillingTickCard({ onlyWhenUnhealthy = false }: { onlyWhenUnhealthy?: boolean }) {
  const [status, setStatus] = useState<BillingStatus | null>(null);

  useEffect(() => {
    let alive = true;
    api.getBillingStatus().then((s) => { if (alive) setStatus(s); }).catch(() => { if (alive) setStatus(null); });
    return () => { alive = false; };
  }, []);

  if (!status || (onlyWhenUnhealthy && status.healthy)) return null;
  const counts = Object.entries(status.orders_by_status).filter(([, n]) => n > 0);

  return (
    <div style={cardStyle} data-testid="billing-tick-card">
      <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Billing-Tick</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <StatusBadge status={status.healthy ? "healthy" : "degraded"} />
        <span>
          Letzter Lauf: {status.last_run_at ? formatTimeAgo(status.last_run_at) : "noch nie"}
        </span>
      </div>
      {!status.healthy && (
        <p role="alert" style={{ color: "#c62828", fontWeight: 600, margin: "12px 0 0" }}>
          Container billing prüfen: {status.orders_needing_tick} Bestellung(en) warten auf den Billing-Tick,
          der letzte Lauf ist älter als {status.max_age_minutes} Minuten oder fehlt.
        </p>
      )}
      {counts.length > 0 && (
        <ul style={{ margin: "12px 0 0", paddingLeft: 20 }}>
          {counts.map(([st, n]) => (
            <li key={st}>{statusLabel(st)}: {n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
