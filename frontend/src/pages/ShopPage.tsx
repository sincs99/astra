import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { t } from "../i18n";
import { api, type Order, type Product } from "../services/api";
import { isAuthenticated } from "../services/api";
import { loginUrl } from "../lib/redirect";
import { formatPrice } from "../lib/money";
import {
  PageLayout, LoadingState, ErrorState, EmptyState, Toast, useToast,
  cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, linkStyle,
} from "../components/ui";

/** Kunden-Shop: aktive Produkte als Karten, Bestellung mit Servername. */
export function ShopPage() {
  const toast = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ordering, setOrdering] = useState<number | null>(null);
  const [serverName, setServerName] = useState("");
  const [busy, setBusy] = useState(false);
  const loggedIn = isAuthenticated();
  const [placed, setPlaced] = useState<Order | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setProducts(await api.getShopProducts());
    } catch (err) {
      setError(err instanceof Error ? err.message : t("shop.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const startOrder = (id: number) => { setOrdering(id); setServerName(""); setPlaced(null); };

  const submit = async (e: React.FormEvent, product: Product) => {
    e.preventDefault();
    // Der Servername ist optional; ohne Eingabe vergibt das Backend einen
    const name = serverName.trim();
    try {
      setBusy(true);
      setPlaced(await api.createOrder(product.id, name || undefined));
      setOrdering(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("shop.orderFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageLayout title={t("shop.title")} maxWidth={1000}>
      <Toast {...toast} />

      {placed && (
        <div role="status" style={{ padding: "12px 16px", marginBottom: 16, backgroundColor: "var(--tint-green)", color: "var(--c-green)", borderRadius: 8 }}>
          <strong>{t("shop.placed")}</strong>{" "}
          {placed.status === "active"
            ? t("shop.placed.active")
            : placed.status === "awaiting_provisioning"
              ? t("shop.placed.awaiting")
              : t("shop.placed.pending")}{" "}
          <Link to="/orders" style={linkStyle}>{t("shop.toOrders")}</Link>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message={t("shop.loading")} />
      ) : products.length === 0 && !error ? (
        <EmptyState icon="🛒" message={t("shop.none")} />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {products.map((p) => (
            <article key={p.id} style={{ ...cardStyle, marginBottom: 0, display: "flex", flexDirection: "column" }} aria-labelledby={`product-${p.id}`}>
              <h2 id={`product-${p.id}`} style={{ margin: "0 0 4px", fontSize: 18 }}>{p.name}</h2>
              {p.blueprint_name && <div style={{ fontSize: 12, color: "var(--fg-muted)" }}>{p.blueprint_name}</div>}
              {p.description && <p style={{ fontSize: 13, color: "var(--fg)" }}>{p.description}</p>}
              <div style={{ fontSize: 22, fontWeight: 700, margin: "8px 0" }}>
                {formatPrice(p.price_cents, p.currency, p.billing_period_days)}
              </div>
              <ul style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 13, color: "var(--fg)" }}>
                <li>{p.resources.memory} MB {t("shop.ram")}</li>
                <li>{p.resources.disk} MB Disk</li>
                <li>{p.resources.cpu}% CPU</li>
              </ul>

              <div style={{ marginTop: "auto" }}>
                {ordering === p.id ? (
                  <form onSubmit={(e) => submit(e, p)} noValidate>
                    <label htmlFor={`server-name-${p.id}`} style={labelStyle}>{t("shop.serverName")}</label>
                    <input id={`server-name-${p.id}`} type="text" autoFocus value={serverName}
                      onChange={(e) => setServerName(e.target.value)} placeholder={t("shop.serverNamePh")} style={inputStyle} />
                    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                      <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                        {busy ? "…" : t("shop.confirm")}
                      </button>
                      <button type="button" onClick={() => setOrdering(null)} disabled={busy} style={btnDefault}>{t("shop.cancel")}</button>
                    </div>
                  </form>
                ) : !loggedIn ? (
                  <Link to={loginUrl("/shop")} aria-label={t("shop.orderLoginAria", { name: p.name })}
                    style={{ ...btnPrimary, display: "block", textAlign: "center", textDecoration: "none", boxSizing: "border-box" }}>
                    {t("shop.loginToOrder")}
                  </Link>
                ) : (
                  <button type="button" onClick={() => startOrder(p.id)} style={{ ...btnPrimary, width: "100%" }}
                    aria-label={t("shop.orderAria", { name: p.name })}>
                    {t("shop.order")}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </PageLayout>
  );
}
