import { Link } from "react-router-dom";
import { StatusBadge } from "../ui/StatusBadge";
import { t } from "../../i18n";
import { formatDateTime } from "../../lib/dates";
import { formatMoney } from "../../lib/money";
import { RemindButton } from "./RemindButton";
import type { Order, PaymentEvent } from "../../services/api";

export function PaymentsPanel({ events, due }: { events: PaymentEvent[] | null; due: Order[] }) {
  // Betrag nur anzeigen, wenn das Backend das Feld liefert (M68)
  const showAmount = !!events?.some((e) => e.amount_cents !== undefined);
  return (
    <section className="panel" aria-labelledby="pay-title">
      <div className="panel-head">
        <h2 id="pay-title">{t("aover.paymentsTitle")}</h2>
        <Link to="/admin/orders" style={{ fontSize: 13, textDecoration: "none" }}>{t("aover.allOrders")}</Link>
      </div>
      {!events ? (
        <div className="panel-body"><p className="hint">{t("aover.loading")}</p></div>
      ) : events.length === 0 ? (
        <div className="panel-body"><p className="hint">{t("aover.noEvents")}</p></div>
      ) : (
        <div style={{ overflowX: "auto" }} role="region" aria-label={t("aover.paymentsTable")} tabIndex={0}>
          <table className="tbl">
            <thead><tr><th scope="col">{t("aover.colTime")}</th><th scope="col">{t("aover.colRef")}</th><th scope="col">{t("aover.colStatus")}</th>{showAmount && <th scope="col">{t("aover.colAmount")}</th>}<th scope="col">{t("aover.colNote")}</th></tr></thead>
            <tbody>
              {events.slice(0, 5).map((e) => (
                <tr key={e.id}>
                  <td style={{ color: "var(--text-2)", whiteSpace: "nowrap" }}>{formatDateTime(e.received_at)}</td>
                  <td className="mono" style={{ color: "var(--text-2)" }}>
                    {e.order_uuid ? <Link to="/admin/orders">{e.order_uuid.slice(0, 8)}</Link> : e.event_id.slice(0, 12)}
                  </td>
                  <td><StatusBadge status={e.status} size="sm" /></td>
                  {showAmount && (
                    <td className="mono" style={{ whiteSpace: "nowrap" }} data-testid={`event-amount-${e.id}`}>
                      {e.amount_cents != null && e.currency ? formatMoney(e.amount_cents, e.currency) : "–"}
                    </td>
                  )}
                  <td style={{ color: "var(--text-2)", overflowWrap: "anywhere" }}>{e.detail ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="panel-foot">
        <span>
          {due.length === 0
            ? t("aover.noneDue")
            : <>{t("aover.dueIn24")} {due.slice(0, 5).map((o, i) => (
              <span key={o.uuid} style={{ display: "inline-flex", gap: 6, alignItems: "flex-start", marginRight: 8 }}>{i > 0 && ","}<Link to="/admin/orders?status=active" className="mono">#{o.id}</Link><RemindButton order={o} /></span>
            ))}{due.length > 5 ? ` ${t("aover.andMore", { n: due.length - 5 })}` : ""}</>}
        </span>
      </div>
    </section>
  );
}
