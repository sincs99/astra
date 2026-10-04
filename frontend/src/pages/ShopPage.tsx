import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, isAuthenticated, type Order, type Product } from "../services/api";
import { loginUrl } from "../lib/redirect";
import { formatMoney, formatPeriod, formatPrice } from "../lib/money";
import { formatMemory } from "../lib/dashboard";
import { useCheckout } from "../hooks/useCheckout";
import { manualPaymentNotice } from "../legal/payment";
import { dateLocale, t } from "../i18n";
import { PageLayout, LoadingState, ErrorState, EmptyState, Toast, useToast } from "../components/ui";
import { Icon } from "../components/ui/Icon";

function specsOf(p: Product): string {
  const r = p.resources;
  return t("shop.specs", { ram: formatMemory(r.memory, dateLocale()), cpu: r.cpu, disk: formatMemory(r.disk, dateLocale()) });
}

/** Neuer Server (Kunden-Shop): Paket wählen, benennen, bezahlen; Zusammenfassung rechts. */
export function ShopPage() {
  const toast = useToast();
  // Vorauswahl über /shop?plan=<id> (Link von der Landingpage)
  const [searchParams] = useSearchParams();
  const planParam = Number(searchParams.get("plan"));
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [serverName, setServerName] = useState("");
  const [onlinePayment, setOnlinePayment] = useState(false);
  const [busy, setBusy] = useState(false);
  const loggedIn = isAuthenticated();
  const [placed, setPlaced] = useState<Order | null>(null);
  const { pay } = useCheckout(toast.error);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const [list, billing] = await Promise.all([
        api.getShopProducts(),
        api.getBillingInfo().catch(() => null),
      ]);
      setProducts(list);
      setSelected((cur) => cur ?? list.find((p) => p.id === planParam)?.id ?? list[0]?.id ?? null);
      if (billing) setOnlinePayment(billing.online_payment);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("shop.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const product = products.find((p) => p.id === selected) ?? null;
  const free = !!product && product.price_cents <= 0;
  const online = onlinePayment && !free;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!product) return;
    // Der Servername ist optional; ohne Eingabe vergibt das Backend einen
    const name = serverName.trim();
    try {
      setBusy(true);
      const order = await api.createOrder(product.id, name || undefined);
      if (online) {
        // Direkt zur Zahlung; schlägt das fehl, bleibt die Bestellung offen und ist unter "Meine Bestellungen" bezahlbar
        const outcome = await pay(order);
        if (outcome === "redirected") return;
      }
      setPlaced(order);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("shop.orderFailed"));
    } finally {
      setBusy(false);
    }
  };

  const submitLabel = busy ? "…" : free ? t("shop.orderFree") : online ? t("shop.continuePay") : t("shop.confirm");

  return (
    <PageLayout title={t("shop.title")} subtitle={t("shop.subtitle")} maxWidth={1200}>
      <Toast {...toast} />

      {placed && (
        <div role="status" className="banner" style={{ background: "var(--tint-green)", borderColor: "var(--border-green)", marginBottom: 20 }}>
          <span className="dot dot-ok" aria-hidden="true" />
          <span className="banner-text">
            <strong>{t("shop.placed")}</strong>{" "}
            {placed.status === "active"
              ? t("shop.placed.active")
              : placed.status === "awaiting_provisioning"
                ? t("shop.placed.awaiting")
                : t("shop.placed.pending")}
          </span>
          <Link to="/orders" className="btn btn-sm">{t("shop.toOrders")}</Link>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message={t("shop.loading")} />
      ) : products.length === 0 && !error ? (
        <EmptyState icon="🛒" message={t("shop.none")} />
      ) : (
        <div className="shop-layout">
          <form className="shop-form" onSubmit={submit}>
            <fieldset className="fieldset">
              <legend className="step"><span className="num" aria-hidden="true">1</span>{t("shop.step1")}</legend>
              <div className="pkgs" role="radiogroup" aria-label={t("shop.planGroup")}>
                {products.map((p) => (
                  <label key={p.id} className="pcard" htmlFor={`plan-${p.id}`}>
                    <input id={`plan-${p.id}`} type="radio" name="plan" value={p.id} checked={selected === p.id}
                      onChange={() => setSelected(p.id)} />
                    <span className="pcard-head">
                      <span style={{ fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 8 }}>
                        {selected === p.id && <Icon name="check" size={16} />}{p.name}
                      </span>
                      <span className="mono pcard-price">{formatMoney(p.price_cents, p.currency)}</span>
                    </span>
                    {p.blueprint_name && <span className="card-sub">{p.blueprint_name}</span>}
                    <span className="card-sub">{specsOf(p)}</span>
                    <span className="card-sub">{formatPeriod(p.billing_period_days)}</span>
                    {p.description && <span className="hint">{p.description}</span>}
                  </label>
                ))}
              </div>
              <span className="hint">{t("shop.perPeriodHint")}</span>
            </fieldset>

            <fieldset className="fieldset">
              <legend className="step"><span className="num" aria-hidden="true">2</span>{t("shop.step2")}</legend>
              <div className="field" style={{ maxWidth: 420 }}>
                <label htmlFor="server-name">{t("shop.serverName")}</label>
                <input id="server-name" className="inp" type="text" value={serverName} maxLength={191}
                  onChange={(e) => setServerName(e.target.value)} placeholder={t("shop.serverNamePh")} />
                <span className="hint">{t("shop.nameHint")}</span>
              </div>
            </fieldset>

            <fieldset className="fieldset">
              <legend className="step"><span className="num" aria-hidden="true">3</span>{t("shop.step3")}</legend>
              <div className="pcard" style={{ cursor: "default", borderColor: "var(--accent)", boxShadow: "0 0 0 1px var(--accent) inset", gap: 10, maxWidth: 520 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 600 }}>
                  <Icon name={free ? "check" : online ? "card" : "bank"} size={16} />
                  {free ? t("shop.payFreeTitle") : online ? t("shop.payCardTitle") : t("shop.payTransferTitle")}
                </span>
                <span className="card-sub">{free ? t("shop.payFreeText") : online ? t("shop.payCardText") : t("shop.payTransferText")}</span>
                {!online && !free && (
                  <div className="box-console"><span className="kv"><span>{manualPaymentNotice()}</span></span></div>
                )}
              </div>
              {loggedIn ? (
                <div>
                  <button type="submit" className="btn btn-primary btn-lg" disabled={busy || !product}>{submitLabel}</button>
                </div>
              ) : (
                <div>
                  <p className="hint" style={{ marginBottom: 8 }}>{t("shop.loginHint")}</p>
                  <Link to={loginUrl("/shop")} className="btn btn-primary btn-lg">{t("shop.loginToOrder")}</Link>
                </div>
              )}
            </fieldset>
          </form>

          <aside className="summary" aria-label={t("shop.summary")}>
            <span className="summary-title">{t("shop.summary")}</span>
            {product ? (
              <>
                <div className="kv"><span>{t("shop.sumPlan")}</span><span>{product.name}</span></div>
                {product.blueprint_name && <div className="kv"><span>{t("shop.sumGame")}</span><span>{product.blueprint_name}</span></div>}
                <div className="kv"><span>{t("shop.sumName")}</span><span>{serverName.trim() || t("shop.autoName")}</span></div>
                <div className="kv"><span>{t("shop.sumTerm")}</span><span>{t("shop.sumTermValue", { period: formatPeriod(product.billing_period_days) })}</span></div>
                <div className="sep" />
                <div className="summary-total">
                  <span style={{ fontWeight: 500 }}>{t("shop.sumTotal")}</span>
                  <span className="mono" aria-label={formatPrice(product.price_cents, product.currency, product.billing_period_days)}>
                    {formatMoney(product.price_cents, product.currency)}
                  </span>
                </div>
              </>
            ) : (
              <span className="hint">{t("shop.noPlan")}</span>
            )}
          </aside>
        </div>
      )}
    </PageLayout>
  );
}
