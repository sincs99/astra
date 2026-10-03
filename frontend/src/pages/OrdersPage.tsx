import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Order } from "../services/api";
import { formatDate } from "../lib/dates";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, thStyle, tdStyle, linkStyle,
} from "../components/ui";

const CANCELLABLE = ["pending_payment", "active", "past_due"];

/** Meine Bestellungen (Kunde). */
export function OrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [instanceUuids, setInstanceUuids] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [list, instances] = await Promise.all([
        api.getMyOrders(),
        // Instance-UUIDs fuer die Links; best effort, falls die Bestellung keine mitliefert
        api.getClientInstances().catch(() => []),
      ]);
      setOrders(list);
      setInstanceUuids(Object.fromEntries(instances.map((i) => [i.id, i.uuid])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bestellungen konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const cancel = async (order: Order) => {
    try {
      await api.cancelOrder(order.id);
      toast.success(order.status === "pending_payment" ? "Bestellung storniert." : "Gekündigt zum Laufzeitende.");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Kündigung fehlgeschlagen");
    }
  };

  return (
    <PageLayout title="Meine Bestellungen">
      <Toast {...toast} />
      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message="Bestellungen werden geladen..." />
      ) : orders.length === 0 && !error ? (
        <div>
          <EmptyState icon="🧾" message="Du hast noch keine Bestellungen." />
          <p style={{ textAlign: "center" }}><Link to="/shop" style={linkStyle}>Zum Shop</Link></p>
        </div>
      ) : (
        <div style={{ ...cardStyle, padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Meine Bestellungen</caption>
            <thead>
              <tr style={{ backgroundColor: "#f5f5f5" }}>
                <th scope="col" style={thStyle}>Produkt</th>
                <th scope="col" style={thStyle}>Status</th>
                <th scope="col" style={thStyle}>Laufzeitende</th>
                <th scope="col" style={thStyle}>Server</th>
                <th scope="col" style={thStyle}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => {
                const uuid = o.instance_uuid ?? (o.instance_id !== null ? instanceUuids[o.instance_id] : undefined);
                return (
                  <tr key={o.id}>
                    <td style={tdStyle}>
                      <strong>{o.product_name ?? `Produkt #${o.product_id}`}</strong>
                      {o.name && <div style={{ fontSize: 12, color: "#666" }}>{o.name}</div>}
                    </td>
                    <td style={tdStyle}><StatusBadge status={o.status} size="sm" /></td>
                    <td style={tdStyle}>
                      {formatDate(o.current_period_end)}
                      {o.cancel_at_period_end && o.status !== "cancelled" && (
                        <div style={{ fontSize: 12, color: "#e65100" }}>gekündigt zum Laufzeitende</div>
                      )}
                    </td>
                    <td style={tdStyle}>
                      {o.instance_id === null ? "–" : uuid ? (
                        <Link to={`/instances/${uuid}`} style={linkStyle}>Zum Server</Link>
                      ) : `Server #${o.instance_id}`}
                    </td>
                    <td style={tdStyle}>
                      {CANCELLABLE.includes(o.status) && !o.cancel_at_period_end ? (
                        <ConfirmButton
                          size="sm" danger
                          label={o.status === "pending_payment" ? "Stornieren" : "Kündigen zum Laufzeitende"}
                          confirmMessage={o.status === "pending_payment"
                            ? "Bestellung wirklich stornieren?"
                            : "Zum Laufzeitende kündigen? Der Server bleibt bis dahin nutzbar."}
                          onConfirm={() => cancel(o)}
                        />
                      ) : "–"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
