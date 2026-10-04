import type { Order } from "../services/api";
import { formatDate, formatDateTime } from "../lib/dates";
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
        <div role="alert" style={{ marginTop: 4, fontSize: 12, color: "var(--c-red)", fontWeight: 600 }}>
          <div>Gesperrt seit {formatDateTime(order.past_due_at)}</div>
          {deletion && <div>Server wird am {formatDate(deletion)} gelöscht</div>}
        </div>
      )}
      {order.status === "refunded" && (
        <div role="alert" style={{ marginTop: 4, fontSize: 12, color: "var(--c-red)", fontWeight: 600 }}>
          Zahlung erstattet{order.refunded_at ? ` am ${formatDate(order.refunded_at)}` : ""}
          {deletion ? `, der Server wird am ${formatDate(deletion)} gelöscht` : ", der Server ist gesperrt"}
        </div>
      )}
      {order.status === "active" && order.cancel_at_period_end && (
        <div style={{ marginTop: 4, fontSize: 12, color: "var(--c-orange)" }}>
          Läuft bis {formatDate(deletion ?? order.current_period_end)}, wird dann gelöscht
        </div>
      )}
    </>
  );
}
