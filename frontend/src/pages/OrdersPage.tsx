import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, type Order } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatMoney, formatPrice } from "../lib/money";
import { manualPaymentNotice } from "../legal/payment";
import { t } from "../i18n";
import { isManualPayment, readPaymentReturn, safeCheckoutUrl } from "../lib/checkout";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { OrderNotice } from "../components/OrderNotice";
import { ReceiptViewer } from "../components/ReceiptViewer";
import { ConnectionAddress } from "../components/ConnectionAddress";
import {
  PageLayout, AutoRefreshToggle, StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, useToast,
  cardStyle, thStyle, tdStyle, linkStyle, btnPrimary, btnDanger, btnDefault,
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
  // Geöffneter Beleg (HTML vom Server); lädt per fetch mit Token, weil ein normaler Link keinen Authorization-Header trägt
  const [receipt, setReceipt] = useState<{ number: string; html: string } | null>(null);
  const [openingReceipt, setOpeningReceipt] = useState<string | null>(null);

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
      if (!silent) setError(err instanceof Error ? err.message : t("orders.loadFailed"));
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
      toast.success(t("orders.paid"));
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
      toast.warning(t("orders.payCancelled"));
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
        toast.error(t("orders.badCheckout"));
        return;
      }
      window.location.assign(target);
    } catch (err) {
      if (isManualPayment(err)) setManualPayment(true);
      else {
        toast.error(err instanceof Error ? err.message : t("orders.payFailed"));
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
          ? t("orders.cancelledNow")
          : t("orders.cancelledLater", { date: formatDate(result.current_period_end ?? order.current_period_end) }),
      );
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("orders.cancelFailed"));
    }
  };

  const showReceipt = async (order: Order, number: string) => {
    try {
      setOpeningReceipt(number);
      setReceipt({ number, html: await api.getReceiptHtml(order.uuid, number) });
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : t("orders.receiptFailed"));
    } finally {
      setOpeningReceipt(null);
    }
  };

  const productCell = (o: Order) => (
    <div>
      <strong>{o.product_name ?? t("orders.productN", { id: o.product_id })}</strong>
      <div style={{ fontSize: 12, color: "var(--text-3)" }}>
        {formatPrice(o.price_cents, o.currency, o.billing_period_days)}
      </div>
      {o.receipts && o.receipts.length > 0 && (
        <div style={{ marginTop: 6, fontSize: 12 }}>
          <div style={{ color: "var(--text-2)", fontWeight: 600 }}>{t("orders.receipts")}</div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 4 }}>
            {o.receipts.map((r) => (
              <li key={r.number} style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                <span>{r.number} · {formatDate(r.issued_at)} · {formatMoney(r.amount_cents, r.currency)}</span>
                <button type="button" onClick={() => showReceipt(o, r.number)} disabled={openingReceipt === r.number}
                  aria-label={t("orders.receiptShowAria", { number: r.number })}
                  style={{ ...btnDefault, padding: "1px 8px", fontSize: 12 }}>
                  {t("orders.receiptShow")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
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
          <Link to={`/instances/${o.instance_uuid}`} style={linkStyle}>{t("orders.toServer")}</Link>
          {o.connection && <div style={{ marginTop: 4 }}><ConnectionAddress connection={o.connection} compact /></div>}
        </>
      )}
    </>
  );

  const action = (o: Order) => {
    // Bei überfälliger Zahlung ist der Server gesperrt: Bezahl-Button rot hervorheben
    const payButton = (label: string, urgent = false) => manualPayment ? (
      <span style={{ fontSize: 12, color: "var(--text-3)", maxWidth: 220 }}>
        {manualPaymentNotice()}
        {o.payment_purpose && <> {t("dash.rowPurpose")}: <strong className="mono" style={{ userSelect: "all" }}>{o.payment_purpose}</strong></>}
      </span>
    ) : (
      <button type="button" onClick={() => pay(o)} disabled={paying === o.uuid}
        style={{ ...(urgent ? btnDanger : btnPrimary), padding: "4px 12px", fontSize: 12, opacity: paying === o.uuid ? 0.6 : 1 }}>
        {paying === o.uuid ? "…" : label}
      </button>
    );
    if (o.status === "pending_payment") {
      return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {payButton(t("orders.payNow"))}
          <ConfirmButton size="sm" danger label={t("orders.cancelBtn")}
            confirmMessage={t("orders.cancelConfirm")} onConfirm={() => cancel(o)} />
        </div>
      );
    }
    if (o.status === "active" || o.status === "past_due") {
      return (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {/* Kostenlose Bestellungen haben nichts zu bezahlen: weder Bezahl-Button noch Überweisungshinweis */}
          {o.price_cents > 0 && payButton(t("orders.renewPay"), o.status === "past_due")}
          {!o.cancel_at_period_end && (
            <ConfirmButton size="sm" danger label={t("orders.cancelEnd")}
              confirmMessage={t("orders.cancelEndConfirm")}
              onConfirm={() => cancel(o)} />
          )}
        </div>
      );
    }
    if (o.status === "awaiting_provisioning") {
      return <span style={{ fontSize: 12, color: "var(--text-3)" }}>{t("orders.awaiting")}</span>;
    }
    return "–";
  };

  return (
    <PageLayout title={t("orders.title")}>
      <Toast {...toast} />
      {orders.length > 0 && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={30} />
        </div>
      )}
      {error && <ErrorState message={error} onRetry={() => load()} />}
      {loading ? (
        <LoadingState message={t("orders.loading")} />
      ) : orders.length === 0 && !error ? (
        <div>
          <EmptyState icon="🧾" message={t("orders.none")} />
          <p style={{ textAlign: "center" }}><Link to="/shop" style={linkStyle}>{t("orders.toShop")}</Link></p>
        </div>
      ) : (
        compact ? (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }} aria-label={t("orders.title")}>
            {orders.map((o) => (
              <li key={o.uuid} style={{ ...cardStyle, marginBottom: 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  {productCell(o)}
                  <StatusBadge status={o.status} size="sm" />
                </div>
                <dl style={{ margin: "12px 0", display: "grid", gridTemplateColumns: "max-content 1fr", gap: "6px 12px", fontSize: 14 }}>
                  <dt style={{ color: "var(--text-2)" }}>{t("orders.colEnd")}</dt>
                  <dd style={{ margin: 0 }}>{endCell(o)}</dd>
                  <dt style={{ color: "var(--text-2)" }}>{t("orders.colServer")}</dt>
                  <dd style={{ margin: 0 }}>{serverCell(o)}</dd>
                </dl>
                {action(o) !== "–" && <div>{action(o)}</div>}
              </li>
            ))}
          </ul>
        ) : (
        <div style={{ ...cardStyle, padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <caption style={{ position: "absolute", left: -9999 }}>{t("orders.title")}</caption>
            <thead>
              <tr style={{ backgroundColor: "var(--surface-2)" }}>
                <th scope="col" style={thStyle}>{t("orders.colProduct")}</th>
                <th scope="col" style={thStyle}>{t("orders.colStatus")}</th>
                <th scope="col" style={thStyle}>{t("orders.colEnd")}</th>
                <th scope="col" style={thStyle}>{t("orders.colServer")}</th>
                <th scope="col" style={thStyle}>{t("orders.colActions")}</th>
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
      {orders.some((o) => (o.receipts?.length ?? 0) > 0) && (
        <p style={{ fontSize: 12, color: "var(--text-3)", marginTop: 12 }}>{t("orders.receiptNote")}</p>
      )}
      {receipt && <ReceiptViewer number={receipt.number} html={receipt.html} onClose={() => setReceipt(null)} />}
    </PageLayout>
  );
}
