import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Order } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import { MANUAL_PAYMENT_NOTICE } from "../legal/payment";
import { isManualPayment, readPaymentReturn, safeCheckoutUrl } from "../lib/checkout";
import { OrderNotice } from "../components/OrderNotice";
import { ConnectionAddress } from "../components/ConnectionAddress";
import {
  PageLayout, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, thStyle, tdStyle, linkStyle, btnPrimary,
} from "../components/ui";

/** Meine Bestellungen (Kunde). */
export function OrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [paying, setPaying] = useState<string | null>(null);
  // Sobald der Checkout mit 409 "manual" antwortet, wird nicht online bezahlt: Button ausblenden
  const [manualPayment, setManualPayment] = useState(false);
  const handledReturn = useRef(false);

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

  // Rueckkehr von Stripe: /orders?paid=<uuid> bzw. ?cancelled=<uuid> -> Toast, Parameter entfernen
  useEffect(() => {
    const ret = readPaymentReturn(searchParams);
    if (!ret || handledReturn.current) return;
    handledReturn.current = true;
    if (ret.kind === "paid") {
      toast.success("Zahlung eingegangen, Server wird bereitgestellt.");
      // Die Bestaetigung kommt asynchron per Webhook: nach 5 s nachladen, solange der Status noch aussteht (max. 6x)
      let tries = 0;
      const timer = setInterval(async () => {
        tries += 1;
        try {
          const list = await api.getMyOrders();
          setOrders(list);
          const current = list.find((o) => o.uuid === ret.orderUuid);
          if (!current || current.status !== "pending_payment" || tries >= 6) clearInterval(timer);
        } catch {
          clearInterval(timer);
        }
      }, 5000);
    } else {
      toast.warning("Zahlung abgebrochen.");
    }
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pay = async (order: Order) => {
    try {
      setPaying(order.uuid);
      const { checkout_url } = await api.createCheckout(order.uuid);
      const target = safeCheckoutUrl(checkout_url);
      if (!target) {
        toast.error("Die Zahlungsseite konnte nicht geöffnet werden (ungültige Adresse).");
        return;
      }
      window.location.assign(target);
    } catch (err) {
      if (isManualPayment(err)) setManualPayment(true);
      else toast.error(err instanceof Error ? err.message : "Zahlung konnte nicht gestartet werden");
    } finally {
      setPaying(null);
    }
  };

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
    const payButton = (label: string) => manualPayment ? (
      <span style={{ fontSize: 12, color: "#666", maxWidth: 220 }}>{MANUAL_PAYMENT_NOTICE}</span>
    ) : (
      <button type="button" onClick={() => pay(o)} disabled={paying === o.uuid}
        style={{ ...btnPrimary, padding: "4px 12px", fontSize: 12, opacity: paying === o.uuid ? 0.6 : 1 }}>
        {paying === o.uuid ? "…" : label}
      </button>
    );
    if (o.status === "pending_payment") {
      return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {payButton("Jetzt bezahlen")}
          <ConfirmButton size="sm" danger label="Stornieren"
            confirmMessage="Bestellung wirklich stornieren?" onConfirm={() => cancel(o)} />
        </div>
      );
    }
    if (o.status === "active" || o.status === "past_due") {
      return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {payButton("Verlängern und bezahlen")}
          {!o.cancel_at_period_end && (
            <ConfirmButton size="sm" danger label="Kündigen zum Laufzeitende"
              confirmMessage="Zum Laufzeitende kündigen? Der Server bleibt bis dahin nutzbar."
              onConfirm={() => cancel(o)} />
          )}
        </div>
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
