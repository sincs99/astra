import { t, dateLocale } from "../i18n";
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
      <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>{t("sform.tickTitle")}</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <StatusBadge status={status.healthy ? "healthy" : "degraded"} />
        <span>
          {t("sform.tickLast", { when: status.last_run_at ? formatTimeAgo(status.last_run_at) : t("sform.tickNever") })}
        </span>
      </div>
      {!status.healthy && (
        <p role="alert" style={{ color: "var(--danger)", fontWeight: 600, margin: "12px 0 0" }}>
          {t("sform.tickCheck", { n: status.orders_needing_tick, minutes: status.max_age_minutes })}
        </p>
      )}
      {waiting && waiting.count > 0 && (
        <p style={{ margin: "12px 0 0" }} data-testid="awaiting-capacity">
          {t("sform.tickWaiting", { n: waiting.count })}
          {waiting.oldest_wait_hours != null && t("sform.tickOldest", { wait: waitText(waiting.oldest_wait_hours) })}.
        </p>
      )}
      {tooLong && (
        <p role="alert" style={{ color: "var(--danger)", fontWeight: 600, margin: "8px 0 0" }}>
          {t("sform.tickCapacity", { hours: waiting!.warn_after_hours })}{" "}
          <Link to="/admin/agents" style={linkStyle}>{t("sform.toAgents")}</Link>
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
  if (hours < 1) return t("sform.lessThanHour");
  return new Intl.NumberFormat(dateLocale(), { style: "unit", unit: "hour", unitDisplay: "long" }).format(Math.round(hours));
}
