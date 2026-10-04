import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Icon } from "../components/ui/Icon";
import { RemindButton } from "../components/admin/RemindButton";
import { api, type Order, type OrderStatus } from "../services/api";
import { OrderNotice } from "../components/OrderNotice";
import { formatDate } from "../lib/dates";
import { formatPrice } from "../lib/money";
import { t } from "../i18n";
import {
  PageLayout, StatusBadge, ConfirmButton, Toast, useToast, ScrollRegion,
} from "../components/ui";

const STATUS_VALUES: OrderStatus[] = ["pending_payment", "awaiting_provisioning", "active", "past_due", "cancelled", "expired", "refunded"];

// active/past_due: mark-paid ist eine Verlaengerung und verlangt eine Zahlungsreferenz
const isRenewal = (o: Order) => o.status === "active" || o.status === "past_due";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

/** Dialog "Als bezahlt markieren": Referenz mit Verwendungszweck vorbelegt, Fokusfalle, Escape schliesst. */
function MarkPaidDialog({ order, busy, onSubmit, onClose }: {
  order: Order; busy: boolean; onSubmit: (reference: string) => void; onClose: () => void;
}) {
  const renewal = isRenewal(order);
  const [reference, setReference] = useState(order.payment_purpose ?? "");
  const panelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    inputRef.current?.select();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onCloseRef.current(); return; }
      if (e.key !== "Tab" || !panelRef.current) return;
      const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !panelRef.current.contains(active))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (active === last || !panelRef.current.contains(active))) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); opener?.focus?.(); };
  }, []);

  const title = renewal ? t("aorders.dialogRenewTitle", { id: order.id }) : t("aorders.dialogPaidTitle", { id: order.id });
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "color-mix(in srgb, var(--console) 60%, transparent)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}
      onClick={onClose}>
      <div ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="aorders-dialog-title" className="panel"
        style={{ width: "min(460px, 100%)", boxShadow: "var(--shadow-dialog)" }} onClick={(e) => e.stopPropagation()}>
        <div className="panel-head"><h2 id="aorders-dialog-title">{title}</h2></div>
        <form className="panel-body" onSubmit={(e) => { e.preventDefault(); onSubmit(reference); }}>
          <div className="field">
            <label htmlFor="aorders-ref">{renewal ? t("aorders.refRequired") : t("aorders.refOptional")}</label>
            <input id="aorders-ref" ref={inputRef} className="inp mono" type="text" value={reference} required={renewal}
              aria-describedby={order.payment_purpose ? "aorders-ref-hint" : undefined}
              onChange={(e) => setReference(e.target.value)} />
            {order.payment_purpose && <p id="aorders-ref-hint" className="hint">{t("aorders.refPrefilled")}</p>}
          </div>
          <div className="row-actions">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "…" : renewal ? t("aorders.bookRenewal") : t("aorders.confirmPaid")}
            </button>
            <button type="button" className="btn" onClick={onClose}>{t("common.cancel")}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** Admin: Bestellungen filtern, Zahlung bestaetigen (legt die Instance an) oder erneut bereitstellen. */
export function AdminOrdersPage() {
  const toast = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  // Filter ueber ?status=... vorbelegbar (z.B. vom Dashboard); unbekannte Werte werden ignoriert
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = searchParams.get("status") ?? "";
  const [status, setStatusState] = useState<OrderStatus | "">(STATUS_VALUES.includes(initial as OrderStatus) ? (initial as OrderStatus) : "");
  // Suche ueber ?q=... (verzoegert an die API, Treffer in Zweck, Servername, Kunde, UUID-Anfang)
  const [query, setQuery] = useState((searchParams.get("q") ?? "").slice(0, 100));
  const [search, setSearch] = useState(query.trim());
  const syncUrl = (nextStatus: OrderStatus | "", nextQuery: string) => {
    const params: Record<string, string> = {};
    if (nextStatus) params.status = nextStatus;
    if (nextQuery.trim()) params.q = nextQuery.trim();
    setSearchParams(params, { replace: true });
  };
  const setStatus = (value: OrderStatus | "") => {
    setStatusState(value);
    syncUrl(value, query);
  };
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query.trim());
      syncUrl(status, query);
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);
  const latest = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paying, setPaying] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const mine = ++latest.current;
    try {
      setLoading(true);
      setError(null);
      const result = await api.getAdminOrders(status, search);
      if (mine === latest.current) setOrders(result);
    } catch (err) {
      if (mine === latest.current) setError(err instanceof Error ? err.message : t("aorders.loadFailed"));
    } finally {
      if (mine === latest.current) setLoading(false);
    }
  };

  useEffect(() => { load(); }, [status, search]);

  const waiting = orders.filter((o) => o.status === "awaiting_provisioning").length;

  const markPaid = async (order: Order, paymentReference?: string) => {
    const ref = paymentReference?.trim();
    if (isRenewal(order) && !ref) {
      toast.error(t("aorders.refNeeded"));
      return;
    }
    try {
      setBusy(true);
      const result = await api.markOrderPaid(order.uuid, ref || undefined);
      if (isRenewal(order)) {
        toast.success(t("aorders.renewed", { id: order.id, date: formatDate(result.current_period_end) }));
      } else if (result.status === "awaiting_provisioning") {
        toast.warning(t("aorders.paidNoCapacity", { id: order.id }));
      } else {
        toast.success(order.status === "awaiting_provisioning"
          ? t("aorders.provisioned", { id: order.id })
          : t("aorders.markedPaid", { id: order.id }));
      }
      setPaying(null);
      await load();
    } catch (err) {
      // z.B. 409 "Kein Agent mit genug Kapazitaet ...": Text des Backends unveraendert zeigen
      toast.error(err instanceof Error ? err.message : t("aorders.actionFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageLayout title={t("aorders.title")} maxWidth={1200}>
      <Toast {...toast} />
      <div className="stack">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "1 1 260px", maxWidth: 420 }}>
          <label htmlFor="order-search">{t("aorders.searchLabel")}</label>
          <div style={{ display: "flex", gap: 6 }}>
            <input id="order-search" type="search" className="inp" value={query} maxLength={100} autoComplete="off"
              placeholder={t("aorders.searchPlaceholder")}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape" && query) { e.preventDefault(); setQuery(""); } }} />
            {query && (
              <button type="button" className="btn btn-icon" aria-label={t("aorders.searchClear")} title={t("aorders.searchClear")}
                onClick={() => setQuery("")}><Icon name="close" size={14} /></button>
            )}
          </div>
        </div>
        <div className="field" style={{ width: 260 }}>
          <label htmlFor="order-status">{t("aorders.filterLabel")}</label>
          <select id="order-status" className="inp" value={status} onChange={(e) => setStatus(e.target.value as OrderStatus | "")}>
            <option value="">{t("aorders.filterAll")}</option>
            {STATUS_VALUES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
          </select>
        </div>
        </div>

        {waiting > 0 && (
          <div role="status" className="banner banner-warn">
            <span className="dot dot-warn" aria-hidden="true" />
            <div className="banner-text">
              <strong>{t(waiting === 1 ? "aorders.waitingOne" : "aorders.waitingMany", { n: waiting })}</strong>{" "}
              {t("aorders.waitingHint")}
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="banner banner-danger">
            <span className="dot dot-danger" aria-hidden="true" />
            <div className="banner-text"><strong>{t("common.error")}</strong> {error}</div>
            <button type="button" className="btn btn-sm" onClick={load}>{t("common.retry")}</button>
          </div>
        )}

        {loading ? (
          <p className="hint" role="status">{t("aorders.loading")}</p>
        ) : orders.length === 0 && !error ? (
          <div className="card-empty" role="status">{search ? t("aorders.noMatches", { q: search }) : t("aorders.empty")}</div>
        ) : orders.length > 0 && (
          <div className="panel">
            <ScrollRegion label={t("aorders.tableLabel")}>
              <table className="tbl tbl-cards">
                <caption className="sr-only">{t("aorders.title")}</caption>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">{t("aorders.colCustomer")}</th>
                    <th scope="col">{t("aorders.colProduct")}</th>
                    <th scope="col">{t("aorders.colStatus")}</th>
                    <th scope="col">{t("aorders.colPeriodEnd")}</th>
                    <th scope="col">{t("aorders.colInstance")}</th>
                    <th scope="col">{t("aorders.colActions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.uuid} style={o.status === "awaiting_provisioning" ? { background: "var(--warn-soft)" } : undefined}>
                      <td data-label="#">{o.id}</td>
                      <td data-label={t("aorders.colCustomer")}>{o.username ?? t("aorders.userFallback", { id: o.user_id ?? "?" })}</td>
                      <td data-label={t("aorders.colProduct")}>
                        {o.product_name ?? t("aorders.productFallback", { id: o.product_id })}
                        {o.blueprint_name && <div className="hint">{o.blueprint_name}</div>}
                        <div className="hint">{formatPrice(o.price_cents, o.currency, o.billing_period_days)}</div>
                      </td>
                      <td data-label={t("aorders.colStatus")}>
                        <StatusBadge status={o.status} size="sm" />
                        {o.payment_reference && <div className="hint">{t("aorders.refLine", { ref: o.payment_reference })}</div>}
                        {o.payment_purpose && <div className="hint mono">{t("aorders.purposeLine", { purpose: o.payment_purpose })}</div>}
                        {o.receipts && o.receipts.length > 0 && (
                          <div className="hint">{t("aorders.receiptsLine", { numbers: o.receipts.map((r) => r.number).join(", ") })}</div>
                        )}
                      </td>
                      <td data-label={t("aorders.colPeriodEnd")}>
                        {formatDate(o.current_period_end)}
                        <OrderNotice order={o} />
                      </td>
                      <td data-label={t("aorders.colInstance")}>
                        {o.instance_name}
                        {o.instance_uuid && <div><code className="mono hint">{o.instance_uuid.slice(0, 8)}</code></div>}
                      </td>
                      <td data-label={t("aorders.colActions")}>
                        {o.status === "pending_payment" || isRenewal(o) ? (
                          <div className="row-actions">
                            <button type="button" className="btn btn-sm" onClick={() => setPaying(o)}>
                              {isRenewal(o) ? t("aorders.renewAction") : t("aorders.markPaid")}
                            </button>
                            <RemindButton order={o} />
                          </div>
                        ) : o.status === "awaiting_provisioning" ? (
                          <ConfirmButton label={t("aorders.reprovision")} size="sm"
                            confirmMessage={t("aorders.reprovisionConfirm", { id: o.id })}
                            onConfirm={() => markPaid(o)} />
                        ) : "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </div>
        )}
      </div>
      {paying && <MarkPaidDialog order={paying} busy={busy} onSubmit={(ref) => markPaid(paying, ref)} onClose={() => setPaying(null)} />}
    </PageLayout>
  );
}
