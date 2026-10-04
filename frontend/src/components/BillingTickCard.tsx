import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, type BillingStatus } from "../services/api";
import { formatTimeAgo } from "../lib/dates";
import { cardStyle, linkStyle, StatusBadge, statusLabel } from "./ui";

/**
 * Admin-System: Zustand des Billing-Ticks (Mahnung/Ablauf/Loeschung).
 * Mit onlyWhenUnhealthy (Dashboard) erscheint sie nur bei Stoerung
 * (Tick ungesund oder bezahlte Bestellung wartet zu lange auf Kapazitaet).
 * Fehler (z.B. 404 bei aelterem Backend) blenden die Karte still aus.
 */
export function BillingTickCard({ onlyWhenUnhealthy = false }: { onlyWhenUnhealthy?: boolean }) {
  const [status, setStatus] = useState<BillingStatus | null>(null);

  useEffect(() => {
    let alive = true;
    api.getBillingStatus().then((s) => { if (alive) setStatus(s); }).catch(() => { if (alive) setStatus(null); });
    return () => { alive = false; };
  }, []);

  const waiting = status?.awaiting_provisioning;
  const tooLong = !!waiting?.waiting_too_long;
  if (!status || (onlyWhenUnhealthy && status.healthy && !tooLong)) return null;
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
      {waiting && waiting.count > 0 && (
        <p style={{ margin: "12px 0 0" }} data-testid="awaiting-capacity">
          {waiting.count} bezahlte Bestellung(en) warten auf einen freien Node
          {waiting.oldest_wait_hours != null && `, die älteste seit ${waitText(waiting.oldest_wait_hours)}`}.
        </p>
      )}
      {tooLong && (
        <p role="alert" style={{ color: "#c62828", fontWeight: 600, margin: "8px 0 0" }}>
          Kapazität prüfen: Eine bezahlte Bestellung wartet länger als {waiting!.warn_after_hours} Stunden auf einen Node.{" "}
          <Link to="/admin/agents" style={linkStyle}>Zu den Agents</Link>
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

function waitText(hours: number): string {
  if (hours < 1) return "weniger als einer Stunde";
  const h = Math.round(hours);
  return h === 1 ? "einer Stunde" : `${h} Stunden`;
}
