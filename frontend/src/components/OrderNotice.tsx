import type { Order } from "../services/api";
import { formatDate, formatDateTime } from "../lib/dates";

/**
 * Warnhinweise zur Laufzeit einer Bestellung (Kunde und Admin):
 * - past_due: "Gesperrt seit …" und "Server wird am … gelöscht" (rot)
 * - aktiv + gekuendigt: "Läuft bis …, wird dann gelöscht" (orange)
 */
export function OrderNotice({ order }: { order: Order }) {
  const deletion = order.scheduled_deletion_at;

  if (order.status === "past_due") {
    return (
      <div role="alert" style={{ marginTop: 4, fontSize: 12, color: "#c62828", fontWeight: 600 }}>
        <div>Gesperrt seit {formatDateTime(order.past_due_at)}</div>
        {deletion && <div>Server wird am {formatDate(deletion)} gelöscht</div>}
      </div>
    );
  }

  if (order.status === "active" && order.cancel_at_period_end) {
    return (
      <div style={{ marginTop: 4, fontSize: 12, color: "#bf360c" }}>
        Läuft bis {formatDate(deletion ?? order.current_period_end)}, wird dann gelöscht
      </div>
    );
  }

  return null;
}
