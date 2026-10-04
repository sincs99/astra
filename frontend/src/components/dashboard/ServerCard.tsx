import { Link } from "react-router-dom";
import { StatusBadge } from "../ui/StatusBadge";
import { Icon } from "../ui/Icon";
import { AddressRow } from "./AddressRow";
import { canRenew, expiryOf, formatMemory, instanceState, isRunning, type Expiry } from "../../lib/dashboard";
import { formatDateLong } from "../../lib/dates";
import { dateLocale, t } from "../../i18n";
import type { Instance, Order, PowerSignal } from "../../services/api";

/** Text zum Laufzeitende, z.B. "28. Okt 2026" oder "in 3 Tagen · 7. Okt". */
function expiryText(e: Expiry): string {
  if (e.kind === "ok") return formatDateLong(e.date);
  if (e.kind === "overdue") return t("dash.endedOn", { date: formatDateLong(e.date) });
  if (e.kind === "soon") {
    const date = formatDateLong(e.date);
    return e.days <= 0 ? t("dash.endsToday", { date }) : e.days === 1 ? t("dash.endsTomorrow", { date }) : t("dash.endsSoon", { n: e.days, date });
  }
  return "";
}

interface ServerCardProps {
  instance: Instance;
  order?: Order;
  acting: boolean;
  onPower: (instance: Instance, signal: PowerSignal) => void;
  /** Verlängern: Stripe -> Checkout, sonst Link zu den Bestellungen */
  onRenew: (order: Order) => void;
  onlinePayment: boolean;
}

export function ServerCard({ instance, order, acting, onPower, onRenew, onlinePayment }: ServerCardProps) {
  const state = instanceState(instance);
  const running = isRunning(instance);
  const expiry = expiryOf(order);
  const controllable = (instance.status ?? "ready") === "ready" && instance.role !== "none";
  const renew = canRenew(order);
  const sub = order?.product_name ?? "";
  const toDetail = `/instances/${instance.uuid}`;

  return (
    <article className="card" aria-labelledby={`srv-${instance.uuid}`}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <Link id={`srv-${instance.uuid}`} to={toDetail} className="card-title">{instance.name}</Link>
          {sub && <span className="card-sub">{sub}</span>}
        </div>
        <StatusBadge status={state} />
      </div>

      <AddressRow address={instance.connection?.address} placeholder={t("dash.addressAfterSetup")} />

      <div className="kv-list">
        {instance.memory > 0 && <div className="kv"><span>{t("dash.rowRam")}</span><span className="mono">{formatMemory(instance.memory, dateLocale())}</span></div>}
        {instance.disk > 0 && <div className="kv"><span>{t("dash.rowDisk")}</span><span className="mono">{formatMemory(instance.disk, dateLocale())}</span></div>}
        {expiry.kind !== "none" && (
          <div className="kv">
            <span>{t("dash.rowEnds")}</span>
            <span className={expiry.kind === "soon" ? "text-warn" : expiry.kind === "overdue" ? "text-danger" : undefined}>{expiryText(expiry)}</span>
          </div>
        )}
      </div>

      <div className="row-actions">
        {controllable && running && (
          <button type="button" className="btn btn-sm btn-danger-text" disabled={acting} onClick={() => onPower(instance, "stop")}>
            <Icon name="stop" size={12} />{t("dash.stop")}
          </button>
        )}
        {controllable && !running && state !== "starting" && state !== "stopping" && (
          <button type="button" className="btn btn-sm" disabled={acting} onClick={() => onPower(instance, "start")}>
            <Icon name="play" size={12} />{t("dash.start")}
          </button>
        )}
        {controllable && running && (
          <button type="button" className="btn btn-sm" disabled={acting} onClick={() => onPower(instance, "restart")}>
            <Icon name="restart" size={13} />{t("dash.restart")}
          </button>
        )}
        {renew && order && (onlinePayment ? (
          <button type="button" className="btn btn-sm btn-accent-outline" onClick={() => onRenew(order)}>{t("dash.renew")}</button>
        ) : (
          <Link to="/orders" className="btn btn-sm btn-accent-outline">{t("dash.renew")}</Link>
        ))}
        <Link to={toDetail} className="btn btn-sm push">{t("dash.open")}</Link>
      </div>
    </article>
  );
}
