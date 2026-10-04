import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, type Order } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import { MANUAL_PAYMENT_NOTICE } from "../legal/payment";
import { isManualPayment, readPaymentReturn, safeCheckoutUrl } from "../lib/checkout";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { OrderNotice } from "../components/OrderNotice";
import { ConnectionAddress } from "../components/ConnectionAddress";
import {
  PageLayout, AutoRefreshToggle, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, thStyle, tdStyle, linkStyle, btnPrimary, btnDanger,
} from "../components/ui";

/** Meine Bestellungen (Kunde). */
export function OrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  // Auf schmalen Bildschirmen sonst ausserhalb des sichtbaren Bereichs: Aktionen -> Karten statt Tabelle
  const compact = useMediaQuery("(max-width: 640px)");
  const [paying, setPaying] = useState<string | null>(null);
  // Sobald der Checkout mit 409 "manual" antwortet, wird nicht online bezahlt: Button ausblenden
  const [manualPayment, setManualPayment] = useState(false);
  const handledReturn = useRef(false);

  // Stilles Nachladen, damit Kunden z.B. den Wechsel auf "aktiv" ohne Neuladen sehen
  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("orders");

  const load = async (silent = false) => {
    try {
      if (!silent) { setLoading(true); setError(null); }
      const [list, billing] = await Promise.all([
        api.getMyOrders(),
        // Zahlungsweg einmal beim Laden erfragen; schlaegt das fehl, bleibt der Fallback (Checkout probieren, 409 "manual")
        api.getBillingInfo().catch(() => null),
      ]);
      setOrders(list);
      if (billing) setManualPayment(!billing.online_payment);
    } catch (err) {
      // Bei stillem Nachladen die vorhandene Liste nicht durch einen Fehler ersetzen
      if (!silent) setError(err instanceof Error ? err.message : "Bestellungen konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useAutoRefresh(() => load(true), 30000, autoRefresh);

  // Rückkehr von Stripe: /orders?paid=<uuid> bzw. ?cancelled=<uuid> -> Toast, Parameter entfernen
  useEffect(() => {
    const ret = readPaymentReturn(searchParams);
    if (!ret || handledReturn.current) return;
    handledReturn.current = true;
    if (ret.kind === "paid") {
      toast.success("Zahlung eingegangen, Server wird bereitgestellt. Eine Bestätigung folgt per E-Mail.");
      // Die Bestätigung kommt asynchron per Webhook: nach 5 s nachladen, solange der Status noch aussteht (max. 6x)
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
      else {
        toast.error(err instanceof Error ? err.message : "Zahlung konnte nicht gestartet werden");
        // Der Status der Bestellung hat sich inzwischen geändert (z.B. bereits bezahlt): Liste aktualisieren
        if (err instanceof ApiError && err.code === "invalid_status") await load();
      }
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

  const productCell = (o: Order) => (
    <div>
      <strong>{o.product_name ?? `Produkt #${o.product_id}`}</strong>
      <div style={{ fontSize: 12, color: "var(--fg-muted)" }}>
        {formatPrice(o.price_cents, o.currency, o.billing_period_days)}
      </div>
    </div>
  );

  const endCell = (o: Order) => (
    <>
      {formatDate(o.current_period_end)}
      <OrderNotice order={o} />
    </>
  );

  const serverCell = (o: Order) => (
    <>
      <div>{o.instance_name}</div>
      {o.instance_uuid && (
        <>
          <Link to={`/instances/${o.instance_uuid}`} style={linkStyle}>Zum Server</Link>
          {o.connection && <div style={{ marginTop: 4 }}><ConnectionAddress connection={o.connection} compact /></div>}
        </>
      )}
    </>
  );

  const action = (o: Order) => {
    // Bei überfälliger Zahlung ist der Server gesperrt: Bezahl-Button rot hervorheben
    const payButton = (label: string, urgent = false) => manualPayment ? (
      <span style={{ fontSize: 12, color: "var(--fg-muted)", maxWidth: 220 }}>{MANUAL_PAYMENT_NOTICE}</span>
    ) : (
      <button type="button" onClick={() => pay(o)} disabled={paying === o.uuid}
        style={{ ...(urgent ? btnDanger : btnPrimary), padding: "4px 12px", fontSize: 12, opacity: paying === o.uuid ? 0.6 : 1 }}>
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
          {/* Kostenlose Bestellungen haben nichts zu bezahlen: weder Bezahl-Button noch Überweisungshinweis */}
          {o.price_cents > 0 && payButton("Verlängern und bezahlen", o.status === "past_due")}
          {!o.cancel_at_period_end && (
            <ConfirmButton size="sm" danger label="Kündigen zum Laufzeitende"
              confirmMessage="Zum Laufzeitende kündigen? Der Server bleibt bis dahin nutzbar."
              onConfirm={() => cancel(o)} />
          )}
        </div>
      );
    }
    if (o.status === "awaiting_provisioning") {
      return <span style={{ fontSize: 12, color: "var(--fg-muted)" }}>Bezahlt. Dein Server wird automatisch bereitgestellt, sobald Platz frei ist.</span>;
    }
    return "–";
  };

  return (
    <PageLayout title="Meine Bestellungen">
      <Toast {...toast} />
      {orders.length > 0 && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={30} />
        </div>
      )}
      {error && <ErrorState message={error} onRetry={() => load()} />}
      {loading ? (
        <LoadingState message="Bestellungen werden geladen..." />
      ) : orders.length === 0 && !error ? (
        <div>
          <EmptyState icon="🧾" message="Du hast noch keine Bestellungen." />
          <p style={{ textAlign: "center" }}><Link to="/shop" style={linkStyle}>Zum Shop</Link></p>
        </div>
      ) : (
        compact ? (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }} aria-label="Meine Bestellungen">
            {orders.map((o) => (
              <li key={o.uuid} style={{ ...cardStyle, marginBottom: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  {productCell(o)}
                  <StatusBadge status={o.status} size="sm" />
                </div>
                <dl style={{ margin: "12px 0", display: "grid", gridTemplateColumns: "max-content 1fr", gap: "6px 12px", fontSize: 14 }}>
                  <dt style={{ color: "var(--fg-soft)" }}>Laufzeitende</dt>
                  <dd style={{ margin: 0 }}>{endCell(o)}</dd>
                  <dt style={{ color: "var(--fg-soft)" }}>Server</dt>
                  <dd style={{ margin: 0 }}>{serverCell(o)}</dd>
                </dl>
                {action(o) !== "–" && <div>{action(o)}</div>}
              </li>
            ))}
          </ul>
        ) : (
        <div style={{ ...cardStyle, padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption style={{ position: "absolute", left: -9999 }}>Meine Bestellungen</caption>
            <thead>
              <tr style={{ backgroundColor: "var(--bg-subtle)" }}>
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
                  <td style={tdStyle}>{productCell(o)}</td>
                  <td style={tdStyle}><StatusBadge status={o.status} size="sm" /></td>
                  <td style={tdStyle}>{endCell(o)}</td>
                  <td style={tdStyle}>{serverCell(o)}</td>
                  <td style={tdStyle}>{action(o)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )
      )}
    </PageLayout>
  );
}
