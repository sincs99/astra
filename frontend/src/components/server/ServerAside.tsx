import { Link } from "react-router-dom";
import { AddressRow } from "../dashboard/AddressRow";
import { canRenew, expiryOf, formatMemory } from "../../lib/dashboard";
import { formatDateLong } from "../../lib/dates";
import { formatPrice } from "../../lib/money";
import { dateLocale, t } from "../../i18n";
import type { Instance, Order, ResourceStats } from "../../services/api";

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

/** Anteil in Prozent; ohne Limit (0) gibt es keinen Balken. */
export function percentOf(used: number, limit: number): number | null {
  return limit > 0 ? Math.round((used / limit) * 100) : null;
}

function Meter({ label, value, percent }: { label: string; value: string; percent: number | null }) {
  const cls = percent === null ? "" : percent > 100 ? " bar-danger" : percent >= 80 ? " bar-warn" : "";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div className="kv"><span>{label}</span><span className={`mono${percent !== null && percent >= 80 ? (percent > 100 ? " text-danger" : " text-warn") : ""}`}>{value}</span></div>
      {percent !== null && (
        <div className={`bar${cls}`} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(percent, 100)}>
          <span style={{ width: `${Math.min(percent, 100)}%` }} />
        </div>
      )}
    </div>
  );
}

export function ConnectionPanel({ instance }: { instance: Instance }) {
  const c = instance.connection;
  return (
    <section className="card" aria-labelledby="panel-conn" style={{ padding: 16, gap: 12 }}>
      <h2 id="panel-conn" className="panel-title">{t("srv.connection")}</h2>
      <span className="kv-title" id="conn-addr-label" style={{ fontSize: "var(--fs-small)", color: "var(--text-2)" }}>{t("srv.serverAddress")}</span>
      <AddressRow address={c?.address} placeholder={t("dash.addressAfterSetup")} />
      {c?.ip && <div className="kv"><span>{t("srv.ip")}</span><span className="mono">{c.ip}</span></div>}
      {c?.host && <div className="kv"><span>{t("srv.node")}</span><span className="mono">{c.host}</span></div>}
    </section>
  );
}

export function ResourcesPanel({ instance, stats }: { instance: Instance; stats: ResourceStats | null }) {
  return (
    <section className="card" aria-labelledby="panel-res" style={{ padding: 16, gap: 12 }}>
      <h2 id="panel-res" className="panel-title">{t("srv.resources")}</h2>
      {stats ? (
        <>
          <Meter label={t("srv.cpu")} value={`${stats.cpu_percent} %`} percent={percentOf(stats.cpu_percent, instance.cpu)} />
          <Meter label={t("srv.ram")} value={`${formatBytes(stats.memory_bytes)} / ${formatBytes(stats.memory_limit_bytes)}`}
            percent={percentOf(stats.memory_bytes, stats.memory_limit_bytes)} />
          <Meter label={t("srv.disk")} value={`${formatBytes(stats.disk_bytes)} / ${formatMemory(instance.disk, dateLocale())}`}
            percent={percentOf(stats.disk_bytes, instance.disk * 1024 * 1024)} />
          <div className="kv"><span>{t("srv.netIn")}</span><span className="mono">{formatBytes(stats.network_rx_bytes)}</span></div>
          <div className="kv"><span>{t("srv.netOut")}</span><span className="mono">{formatBytes(stats.network_tx_bytes)}</span></div>
          <div className="kv"><span>{t("srv.uptime")}</span><span className="mono">{formatUptime(stats.uptime_seconds)}</span></div>
          <p className="hint" style={{ fontSize: 12 }}>{t("srv.resourcesRefresh")}</p>
        </>
      ) : (
        <p className="hint" style={{ margin: 0 }}>{t("srv.resourcesLoading")}</p>
      )}
    </section>
  );
}

/** Laufzeit aus der zugehörigen Bestellung (nur wenn es eine gibt, z.B. nicht für Mitbenutzer). */
export function TermPanel({ order, onlinePayment, onRenew }: { order?: Order; onlinePayment: boolean; onRenew: (order: Order) => void }) {
  if (!order) return null;
  const expiry = expiryOf(order);
  const renewable = (order.status === "active" || order.status === "past_due") && order.price_cents > 0;
  return (
    <section className="card" aria-labelledby="panel-term" style={{ padding: 16, gap: 10 }}>
      <h2 id="panel-term" className="panel-title">{t("srv.term")}</h2>
      {order.product_name && <div className="kv"><span>{t("srv.plan")}</span><span>{order.product_name}</span></div>}
      {order.current_period_end && (
        <div className="kv">
          <span>{t("srv.runsUntil")}</span>
          <span className={expiry.kind === "soon" ? "text-warn" : expiry.kind === "overdue" ? "text-danger" : undefined}>{formatDateLong(order.current_period_end)}</span>
        </div>
      )}
      {renewable && <div className="kv"><span>{t("srv.renewal")}</span><span className="mono">{formatPrice(order.price_cents, order.currency, order.billing_period_days)}</span></div>}
      {renewable && (onlinePayment ? (
        <button type="button" className={`btn ${canRenew(order) ? "btn-primary" : ""}`} onClick={() => onRenew(order)}>{t("srv.renew")}</button>
      ) : (
        <Link to="/orders" className={`btn ${canRenew(order) ? "btn-primary" : ""}`}>{t("srv.renew")}</Link>
      ))}
    </section>
  );
}
