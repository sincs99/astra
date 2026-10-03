import { useEffect, useState } from "react";
import { api, type Order, type OrderStatus } from "../services/api";
import { formatDate } from "../lib/dates";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, inputStyle, labelStyle, thStyle, tdStyle,
} from "../components/ui";

const STATUSES: { value: OrderStatus; label: string }[] = [
  { value: "pending_payment", label: "Zahlung ausstehend" },
  { value: "active", label: "Aktiv" },
  { value: "past_due", label: "Überfällig" },
  { value: "cancelled", label: "Gekündigt" },
  { value: "expired", label: "Abgelaufen" },
];

/** Admin: Bestellungen filtern und manuell als bezahlt markieren (legt die Instance an). */
export function AdminOrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [status, setStatus] = useState<OrderStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setOrders(await api.getAdminOrders(status));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bestellungen konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [status]);

  const markPaid = async (order: Order) => {
    try {
      await api.markOrderPaid(order.id);
      toast.success(`Bestellung #${order.id} als bezahlt markiert, Instance wird angelegt.`);
      await load();
    } catch (err) {
      // z.B. 409 "Kein Agent mit genug Kapazitaet ...": Text des Backends unveraendert zeigen
      toast.error(err instanceof Error ? err.message : "Freischalten fehlgeschlagen");
    }
  };

  return (
    <PageLayout title="Bestellungen">
      <Toast {...toast} />

      <div style={{ ...cardStyle, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div>
          <label htmlFor="order-status" style={labelStyle}>Status</label>
          <select id="order-status" value={status} onChange={(e) => setStatus(e.target.value as OrderStatus | "")} style={{ ...inputStyle, width: 200 }}>
            <option value="">Alle</option>
            {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message="Bestellungen werden geladen..." />
      ) : orders.length === 0 && !error ? (
        <EmptyState icon="🧾" message="Keine Bestellungen gefunden." />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #e0e0e0" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Bestellungen</caption>
            <thead>
              <tr style={{ backgroundColor: "#f5f5f5" }}>
                <th scope="col" style={thStyle}>#</th>
                <th scope="col" style={thStyle}>Kunde</th>
                <th scope="col" style={thStyle}>Produkt</th>
                <th scope="col" style={thStyle}>Status</th>
                <th scope="col" style={thStyle}>Laufzeitende</th>
                <th scope="col" style={thStyle}>Instance</th>
                <th scope="col" style={thStyle}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td style={tdStyle}>{o.id}</td>
                  <td style={tdStyle}>{o.username ?? `User #${o.user_id}`}</td>
                  <td style={tdStyle}>
                    {o.product_name ?? `Produkt #${o.product_id}`}
                    {o.name && <div style={{ fontSize: 12, color: "#666" }}>{o.name}</div>}
                  </td>
                  <td style={tdStyle}><StatusBadge status={o.status} size="sm" /></td>
                  <td style={tdStyle}>{formatDate(o.current_period_end)}</td>
                  <td style={tdStyle}>{o.instance_id === null ? "–" : <code>{o.instance_uuid?.slice(0, 8) ?? `#${o.instance_id}`}</code>}</td>
                  <td style={tdStyle}>
                    {o.status === "pending_payment" || o.status === "past_due" ? (
                      <ConfirmButton
                        label="Als bezahlt markieren" size="sm"
                        confirmMessage={o.status === "pending_payment"
                          ? `Bestellung #${o.id} als bezahlt markieren? Die Instance wird angelegt.`
                          : `Bestellung #${o.id} als bezahlt markieren? Die Laufzeit wird verlängert.`}
                        onConfirm={() => markPaid(o)}
                      />
                    ) : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
