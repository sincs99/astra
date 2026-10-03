import { useEffect, useState } from "react";
import { api, type Order, type OrderStatus } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
} from "../components/ui";

const STATUSES: { value: OrderStatus; label: string }[] = [
  { value: "pending_payment", label: "Zahlung ausstehend" },
  { value: "awaiting_provisioning", label: "Wird bereitgestellt" },
  { value: "active", label: "Aktiv" },
  { value: "past_due", label: "Überfällig" },
  { value: "cancelled", label: "Gekündigt" },
  { value: "expired", label: "Abgelaufen" },
];

/** Admin: Bestellungen filtern, Zahlung bestaetigen (legt die Instance an) oder erneut bereitstellen. */
export function AdminOrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [status, setStatus] = useState<OrderStatus | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payingUuid, setPayingUuid] = useState<string | null>(null);
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);

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

  const markPaid = async (order: Order, paymentReference?: string) => {
    try {
      setBusy(true);
      const result = await api.markOrderPaid(order.uuid, paymentReference?.trim() || undefined);
      if (result.status === "awaiting_provisioning") {
        toast.warning(`Bestellung #${order.id} ist bezahlt, aber es ist noch kein Platz frei. Später erneut bereitstellen.`);
      } else {
        toast.success(
          order.status === "awaiting_provisioning"
            ? `Bestellung #${order.id} wurde bereitgestellt.`
            : `Bestellung #${order.id} als bezahlt markiert, Instance wird angelegt.`,
        );
      }
      setPayingUuid(null);
      setReference("");
      await load();
    } catch (err) {
      // z.B. 409 "Kein Agent mit genug Kapazitaet ...": Text des Backends unveraendert zeigen
      toast.error(err instanceof Error ? err.message : "Freischalten fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageLayout title="Bestellungen" maxWidth={1200}>
      <Toast {...toast} />

      <div style={{ ...cardStyle, display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
        <div>
          <label htmlFor="order-status" style={labelStyle}>Status</label>
          <select id="order-status" value={status} onChange={(e) => setStatus(e.target.value as OrderStatus | "")} style={{ ...inputStyle, width: 220 }}>
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
                <tr key={o.uuid}>
                  <td style={tdStyle}>{o.id}</td>
                  <td style={tdStyle}>{o.username ?? `User #${o.user_id}`}</td>
                  <td style={tdStyle}>
                    {o.product_name ?? `Produkt #${o.product_id}`}
                    <div style={{ fontSize: 12, color: "#666" }}>{formatPrice(o.price_cents, o.currency, o.billing_period_days)}</div>
                  </td>
                  <td style={tdStyle}>
                    <StatusBadge status={o.status} size="sm" />
                    {o.payment_reference && <div style={{ fontSize: 11, color: "#666" }}>Ref: {o.payment_reference}</div>}
                  </td>
                  <td style={tdStyle}>{formatDate(o.current_period_end)}</td>
                  <td style={tdStyle}>
                    {o.instance_name}
                    {o.instance_uuid && <div><code style={{ fontSize: 11 }}>{o.instance_uuid.slice(0, 8)}</code></div>}
                  </td>
                  <td style={tdStyle}>
                    {o.status === "pending_payment" ? (
                      payingUuid === o.uuid ? (
                        <form onSubmit={(e) => { e.preventDefault(); markPaid(o, reference); }} style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "flex-end" }}>
                          <div>
                            <label htmlFor={`ref-${o.uuid}`} style={{ ...labelStyle, fontSize: 11 }}>Zahlungsreferenz (optional)</label>
                            <input id={`ref-${o.uuid}`} type="text" value={reference} autoFocus
                              onChange={(e) => setReference(e.target.value)} style={{ ...inputStyle, width: 170, padding: "4px 8px" }} />
                          </div>
                          <button type="submit" disabled={busy} style={{ ...btnPrimary, padding: "5px 12px", fontSize: 12 }}>
                            {busy ? "…" : "Bezahlt bestätigen"}
                          </button>
                          <button type="button" onClick={() => { setPayingUuid(null); setReference(""); }} style={{ ...btnDefault, padding: "5px 10px", fontSize: 12 }}>
                            Abbrechen
                          </button>
                        </form>
                      ) : (
                        <button type="button" onClick={() => { setPayingUuid(o.uuid); setReference(""); }}
                          style={{ ...btnDefault, padding: "4px 12px", fontSize: 12 }}>
                          Als bezahlt markieren
                        </button>
                      )
                    ) : o.status === "awaiting_provisioning" ? (
                      <ConfirmButton label="Erneut bereitstellen" size="sm"
                        confirmMessage={`Bestellung #${o.id} erneut bereitstellen? Die Zahlung wird nicht doppelt verbucht.`}
                        onConfirm={() => markPaid(o)} />
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
