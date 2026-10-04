import type { Order } from "../services/api";
import { formatDate, formatDateTime } from "../lib/dates";
import { t } from "../i18n";
import { StatusBadge } from "./ui";

/**
 * Hinweise zur Laufzeit einer Bestellung (Kunde und Admin):
 * - past_due: "Gesperrt seit …" und "Server wird am … gelöscht" (rot)
 * - aktiv + gekündigt: "Läuft bis …, wird dann gelöscht" (orange)
 * - refunded: "Zahlung erstattet, der Server wird am … gelöscht" (rot)
 * - disputed: Badge "Zahlung angefochten"
 */
export function OrderNotice({ order }: { order: Order }) {
  const deletion = order.scheduled_deletion_at;

  return (
    <>
      {order.disputed && (
        <div style={{ marginTop: 4 }}>
          <StatusBadge status="disputed" size="sm" />
        </div>
      )}
      {order.status === "past_due" && (
        <div role="alert" style={{ marginTop: 4, fontSize: 12, color: "var(--danger)", fontWeight: 600 }}>
          <div>{t("orders.suspendedSince", { date: formatDateTime(order.past_due_at) })}</div>
          {deletion && <div>{t("orders.deletedOn", { date: formatDate(deletion) })}</div>}
        </div>
      )}
      {order.status === "refunded" && (
        <div role="alert" style={{ marginTop: 4, fontSize: 12, color: "var(--danger)", fontWeight: 600 }}>
          {order.refunded_at ? t("orders.refundedAt", { date: formatDate(order.refunded_at) }) : t("orders.refunded")}
          {deletion ? t("orders.refundedDelete", { date: formatDate(deletion) }) : t("orders.refundedLocked")}
        </div>
      )}
      {order.status === "active" && order.cancel_at_period_end && (
        <div style={{ marginTop: 4, fontSize: 12, color: "var(--warn)" }}>
          {t("orders.endsThenDeleted", { date: formatDate(deletion ?? order.current_period_end) })}
        </div>
      )}
    </>
  );
}
