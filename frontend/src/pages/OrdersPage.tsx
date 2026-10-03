import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Order } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import { OrderNotice } from "../components/OrderNotice";
import { ConnectionAddress } from "../components/ConnectionAddress";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, thStyle, tdStyle, linkStyle,
} from "../components/ui";

/** Meine Bestellungen (Kunde). */
export function OrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setOrders(await api.getMyOrders());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bestellungen konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const cancel = async (order: Order) => {
    try {
      const result = await api.cancelOrder(order.uuid);
      toast.success(
        order.status === "pending_payment"
          ? "Bestellung storniert."
          : `Gekündigt. Dein Server läuft noch bis ${formatDate(result.current_period_end ?? order.current_period_end)}.`,
      );
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Kündigung fehlgeschlagen");
    }
  };

  const action = (o: Order) => {
    if (o.status === "pending_payment") {
      return (
        <ConfirmButton size="sm" danger label="Stornieren"
          confirmMessage="Bestellung wirklich stornieren?" onConfirm={() => cancel(o)} />
      );
    }
    if ((o.status === "active" || o.status === "past_due") && !o.cancel_at_period_end) {
      return (
        <ConfirmButton size="sm" danger label="Kündigen zum Laufzeitende"
          confirmMessage="Zum Laufzeitende kündigen? Der Server bleibt bis dahin nutzbar."
          onConfirm={() => cancel(o)} />
      );
    }
    if (o.status === "awaiting_provisioning") {
      return <span style={{ fontSize: 12, color: "#666" }}>Bezahlt, wird bereitgestellt</span>;
    }
    return "–";
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
              {orders.map((o) => (
                <tr key={o.uuid}>
                  <td style={tdStyle}>
                    <strong>{o.product_name ?? `Produkt #${o.product_id}`}</strong>
                    <div style={{ fontSize: 12, color: "#666" }}>
                      {formatPrice(o.price_cents, o.currency, o.billing_period_days)}
                    </div>
                  </td>
                  <td style={tdStyle}><StatusBadge status={o.status} size="sm" /></td>
                  <td style={tdStyle}>
                    {formatDate(o.current_period_end)}
                    <OrderNotice order={o} />
                  </td>
                  <td style={tdStyle}>
                    <div>{o.instance_name}</div>
                    {o.instance_uuid && (
                      <>
                        <Link to={`/instances/${o.instance_uuid}`} style={linkStyle}>Zum Server</Link>
                        {o.connection && <div style={{ marginTop: 4 }}><ConnectionAddress connection={o.connection} compact /></div>}
                      </>
                    )}
                  </td>
                  <td style={tdStyle}>{action(o)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageLayout>
  );
}
