import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
      setError(err instanceof Error ? err.message : "Produkte konnten nicht geladen werden");
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
      toast.error(err instanceof Error ? err.message : "Bestellung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageLayout title="Shop" maxWidth={1000}>
      <Toast {...toast} />

      {placed && (
        <div role="status" style={{ padding: "12px 16px", marginBottom: 16, backgroundColor: "#e8f5e9", color: "#2e7d32", borderRadius: 8 }}>
          <strong>Bestellung eingegangen.</strong>{" "}
          {placed.status === "active"
            ? "Dein Server wurde bereitgestellt."
            : placed.status === "awaiting_provisioning"
              ? "Dein Server wird bereitgestellt, sobald Platz frei ist."
              : "Dein Server wird nach Zahlungseingang freigeschaltet."}{" "}
          <Link to="/orders" style={linkStyle}>Zu meinen Bestellungen</Link>
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {loading ? (
        <LoadingState message="Produkte werden geladen..." />
      ) : products.length === 0 && !error ? (
        <EmptyState icon="🛒" message="Aktuell sind keine Produkte verfügbar." />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
          {products.map((p) => (
            <article key={p.id} style={{ ...cardStyle, marginBottom: 0, display: "flex", flexDirection: "column" }} aria-labelledby={`product-${p.id}`}>
              <h2 id={`product-${p.id}`} style={{ margin: "0 0 4px", fontSize: 18 }}>{p.name}</h2>
              {p.blueprint_name && <div style={{ fontSize: 12, color: "#666" }}>{p.blueprint_name}</div>}
              {p.description && <p style={{ fontSize: 13, color: "#444" }}>{p.description}</p>}
              <div style={{ fontSize: 22, fontWeight: 700, margin: "8px 0" }}>
                {formatPrice(p.price_cents, p.currency, p.billing_period_days)}
              </div>
              <ul style={{ margin: "0 0 12px", paddingLeft: 18, fontSize: 13, color: "#444" }}>
                <li>{p.resources.memory} MB RAM</li>
                <li>{p.resources.disk} MB Disk</li>
                <li>{p.resources.cpu}% CPU</li>
              </ul>

              <div style={{ marginTop: "auto" }}>
                {ordering === p.id ? (
                  <form onSubmit={(e) => submit(e, p)} noValidate>
                    <label htmlFor={`server-name-${p.id}`} style={labelStyle}>Servername (optional)</label>
                    <input id={`server-name-${p.id}`} type="text" autoFocus value={serverName}
                      onChange={(e) => setServerName(e.target.value)} placeholder="wird sonst automatisch vergeben" style={inputStyle} />
                    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                      <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }}>
                        {busy ? "…" : "Verbindlich bestellen"}
                      </button>
                      <button type="button" onClick={() => setOrdering(null)} disabled={busy} style={btnDefault}>Abbrechen</button>
                    </div>
                  </form>
                ) : !loggedIn ? (
                  <Link to={loginUrl("/shop")} aria-label={`${p.name} bestellen (Anmeldung erforderlich)`}
                    style={{ ...btnPrimary, display: "block", textAlign: "center", textDecoration: "none", boxSizing: "border-box" }}>
                    Anmelden und bestellen
                  </Link>
                ) : (
                  <button type="button" onClick={() => startOrder(p.id)} style={{ ...btnPrimary, width: "100%" }}
                    aria-label={`${p.name} bestellen`}>
                    Bestellen
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
