import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { useAutoRefresh } from "../hooks/useAutoRefresh";
import { cardStyle, linkStyle } from "./ui";

interface Counts {
  pending: number;
  awaiting: number;
}

/**
 * Admin-Dashboard: offene Bestellungen (wartet auf Zahlung / auf Bereitstellung),
 * damit Zahlungseingänge nicht übersehen werden. Fehler blenden die Karte still aus.
 */
export function OpenOrdersCard() {
  const [counts, setCounts] = useState<Counts | null>(null);

  const load = useCallback(async () => {
    try {
      const [pending, awaiting] = await Promise.all([
        api.getAdminOrders("pending_payment"),
        api.getAdminOrders("awaiting_provisioning"),
      ]);
      setCounts({ pending: pending.length, awaiting: awaiting.length });
    } catch {
      setCounts(null);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useAutoRefresh(load, 30000, true);

  if (!counts) return null;
  const total = counts.pending + counts.awaiting;

  return (
    <section aria-labelledby="open-orders-title"
      style={{ ...cardStyle, borderColor: total > 0 ? "var(--border-orange)" : "var(--border)", backgroundColor: total > 0 ? "var(--tint-yellow)" : "var(--bg-card)" }}>
      <h2 id="open-orders-title" style={{ margin: "0 0 8px", fontSize: 16 }}>
        Offene Bestellungen: <span data-testid="open-orders-total">{total}</span>
      </h2>
      {total === 0 ? (
        <p style={{ margin: 0, fontSize: 13, color: "var(--fg-muted)" }}>Keine offenen Bestellungen.</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
          {counts.pending > 0 && (
            <li>
              <Link to="/admin/orders?status=pending_payment" style={linkStyle}>
                {counts.pending} warten auf Zahlung
              </Link>
            </li>
          )}
          {counts.awaiting > 0 && (
            <li>
              <Link to="/admin/orders?status=awaiting_provisioning" style={linkStyle}>
                {counts.awaiting} bezahlt, warten auf Bereitstellung
              </Link>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
