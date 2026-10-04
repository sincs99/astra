import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Order, type OrderStatus } from "../services/api";
import { OrderNotice } from "../components/OrderNotice";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, thStyle, tdStyle,
  ScrollRegion,
} from "../components/ui";

const STATUS_VALUES = ["pending_payment", "awaiting_provisioning", "active", "past_due", "cancelled", "expired", "refunded"];

const STATUSES: { value: OrderStatus; label: string }[] = [
  { value: "pending_payment", label: "Zahlung ausstehend" },
  { value: "awaiting_provisioning", label: "Wird bereitgestellt" },
  { value: "active", label: "Aktiv" },
  { value: "past_due", label: "Überfällig" },
  { value: "cancelled", label: "Gekündigt" },
  { value: "expired", label: "Abgelaufen" },
  { value: "refunded", label: "Erstattet" },
];

/** Admin: Bestellungen filtern, Zahlung bestaetigen (legt die Instance an) oder erneut bereitstellen. */
export function AdminOrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  // Filter ueber ?status=... vorbelegbar (z.B. vom Dashboard); unbekannte Werte werden ignoriert
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = searchParams.get("status") ?? "";
  const [status, setStatusState] = useState<OrderStatus | "">(STATUS_VALUES.includes(initial) ? (initial as OrderStatus) : "");
  const setStatus = (value: OrderStatus | "") => {
    setStatusState(value);
    setSearchParams(value ? { status: value } : {}, { replace: true });
  };
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

  const waiting = orders.filter((o) => o.status === "awaiting_provisioning").length;

  // active/past_due: mark-paid ist eine Verlaengerung und verlangt eine Zahlungsreferenz
  const isRenewal = (o: Order) => o.status === "active" || o.status === "past_due";

  const markPaid = async (order: Order, paymentReference?: string) => {
    const ref = paymentReference?.trim();
    if (isRenewal(order) && !ref) {
      toast.error("Für eine Verlängerung ist eine Zahlungsreferenz erforderlich.");
      return;
    }
    try {
      setBusy(true);
      const result = await api.markOrderPaid(order.uuid, ref || undefined);
      if (isRenewal(order)) {
        toast.success(`Bestellung #${order.id} verlängert bis ${formatDate(result.current_period_end)}.`);
      } else if (result.status === "awaiting_provisioning") {
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

      {waiting > 0 && (
        <div role="status" style={{ padding: "10px 14px", marginBottom: 16, backgroundColor: "var(--tint-yellow)", border: "1px solid var(--border-orange)", borderRadius: 8, color: "var(--c-yellow)", fontSize: 14 }}>
          <strong>{waiting} bezahlte Bestellung{waiting === 1 ? "" : "en"} wartet auf Bereitstellung.</strong>{" "}
          Schaffe Platz (Endpoints, Kapazität) und wähle „Erneut bereitstellen“.
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message="Bestellungen werden geladen..." />
      ) : orders.length === 0 && !error ? (
        <EmptyState icon="🧾" message="Keine Bestellungen gefunden." />
      ) : (
        <ScrollRegion label="Bestellungen-Tabelle">
          <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid var(--border)" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Bestellungen</caption>
            <thead>
              <tr style={{ backgroundColor: "var(--bg-subtle)" }}>
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
                <tr key={o.uuid} style={o.status === "awaiting_provisioning" ? { backgroundColor: "var(--tint-yellow)" } : undefined}>
                  <td style={tdStyle}>{o.id}</td>
                  <td style={tdStyle}>{o.username ?? `User #${o.user_id}`}</td>
                  <td style={tdStyle}>
                    {o.product_name ?? `Produkt #${o.product_id}`}
                    <div style={{ fontSize: 12, color: "var(--fg-muted)" }}>{formatPrice(o.price_cents, o.currency, o.billing_period_days)}</div>
                  </td>
                  <td style={tdStyle}>
                    <StatusBadge status={o.status} size="sm" />
                    {o.payment_reference && <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>Ref: {o.payment_reference}</div>}
                  </td>
                  <td style={tdStyle}>
                    {formatDate(o.current_period_end)}
                    <OrderNotice order={o} />
                  </td>
                  <td style={tdStyle}>
                    {o.instance_name}
                    {o.instance_uuid && <div><code style={{ fontSize: 11 }}>{o.instance_uuid.slice(0, 8)}</code></div>}
                  </td>
                  <td style={tdStyle}>
                    {o.status === "pending_payment" || isRenewal(o) ? (
                      payingUuid === o.uuid ? (
                        <form onSubmit={(e) => { e.preventDefault(); markPaid(o, reference); }} style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "flex-end" }}>
                          <div>
                            <label htmlFor={`ref-${o.uuid}`} style={{ ...labelStyle, fontSize: 11 }}>
                              {isRenewal(o) ? "Zahlungsreferenz *" : "Zahlungsreferenz (optional)"}
                            </label>
                            <input id={`ref-${o.uuid}`} type="text" value={reference} autoFocus required={isRenewal(o)}
                              onChange={(e) => setReference(e.target.value)} style={{ ...inputStyle, width: 170, padding: "4px 8px" }} />
                          </div>
                          <button type="submit" disabled={busy} style={{ ...btnPrimary, padding: "5px 12px", fontSize: 12 }}>
                            {busy ? "…" : isRenewal(o) ? "Verlängerung buchen" : "Bezahlt bestätigen"}
                          </button>
                          <button type="button" onClick={() => { setPayingUuid(null); setReference(""); }} style={{ ...btnDefault, padding: "5px 10px", fontSize: 12 }}>
                            Abbrechen
                          </button>
                        </form>
                      ) : (
                        <button type="button" onClick={() => { setPayingUuid(o.uuid); setReference(""); }}
                          style={{ ...btnDefault, padding: "4px 12px", fontSize: 12 }}>
                          {isRenewal(o) ? "Verlängern (Zahlung erfassen)" : "Als bezahlt markieren"}
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
        </ScrollRegion>
      )}
    </PageLayout>
  );
}
