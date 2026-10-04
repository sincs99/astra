import { Link } from "react-router-dom";
import { StatusBadge } from "../ui/StatusBadge";
import { ConfirmButton } from "../ui/ConfirmButton";
import { AddressRow } from "./AddressRow";
import { formatMoney, formatPeriod } from "../../lib/money";
import { gamePackageLabel } from "../../lib/subtitle";
import { t } from "../../i18n";
import type { Order } from "../../services/api";

interface OrderCardProps {
  order: Order;
  onlinePayment: boolean;
  paying: boolean;
  onPay: (order: Order) => void;
  onCancel: (order: Order) => void;
}

/** Karte für eine Bestellung ohne Server: wartet auf Zahlung oder auf freien Platz. */
export function OrderCard({ order, onlinePayment, paying, onPay, onCancel }: OrderCardProps) {
  const awaitingPayment = order.status === "pending_payment";
  return (
    <article className="card" aria-labelledby={`ord-${order.uuid}`}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <span id={`ord-${order.uuid}`} className="card-title">{order.instance_name}</span>
          {gamePackageLabel(order.blueprint_name, order.product_name) && <span className="card-sub">{gamePackageLabel(order.blueprint_name, order.product_name)}</span>}
        </div>
        <StatusBadge status={order.status} />
      </div>

      <AddressRow placeholder={awaitingPayment ? t("dash.addressAfterPayment") : t("dash.addressAfterSetup")} />

      {awaitingPayment && !onlinePayment && order.payment_purpose && (
        <div className="kv-list">
          <div className="kv"><span>{t("dash.rowPurpose")}</span></div>
          <AddressRow address={order.payment_purpose} />
        </div>
      )}

      <div className="kv-list">
        <div className="kv"><span>{t("dash.rowOrder")}</span><span className="mono">#{order.id}</span></div>
        <div className="kv"><span>{t("dash.rowAmount")}</span><span className="mono">{formatMoney(order.price_cents, order.currency)}</span></div>
        <div className="kv"><span>{t("dash.rowTerm")}</span><span>{formatPeriod(order.billing_period_days)}</span></div>
      </div>

      {awaitingPayment ? (
        <div className="row-actions">
          {onlinePayment ? (
            <button type="button" className="btn btn-sm btn-primary" disabled={paying} onClick={() => onPay(order)}>{t("dash.payCard")}</button>
          ) : (
            <Link to="/orders" className="btn btn-sm btn-primary">{t("dash.showPayment")}</Link>
          )}
          <span className="push">
            <ConfirmButton size="sm" label={t("dash.cancel")} confirmMessage={t("dash.cancelConfirm")} onConfirm={() => onCancel(order)} />
          </span>
        </div>
      ) : (
        <p className="hint">{t("dash.waiting")}</p>
      )}
    </article>
  );
}
