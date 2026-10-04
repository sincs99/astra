import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Order, type AgentMonitoringEntry, type PaymentEvent, type RevenueStats } from "../../services/api";
import { cardStyle, linkStyle, StatusBadge, statusLabel } from "../ui";
import { UtilizationBar } from "../UtilizationBar";
import { formatMoney } from "../../lib/money";
import { formatDateTime } from "../../lib/dates";
import { countByStatus, fleetLoad, mergeEvents, revenueLastDays, OVERVIEW_STATUSES, type RevenueSummary } from "../../lib/adminOverview";
import { useAutoRefresh } from "../../hooks/useAutoRefresh";

/** Gemeinsamer Rahmen einer Kachel; Ladefehler blenden nur diese Kachel ein, nicht die ganze Seite. */
function Tile({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} style={{ ...cardStyle, marginBottom: 0 }}>
      <h2 id={id} style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700 }}>{title}</h2>
      {children}
    </section>
  );
}

const muted = { margin: 0, fontSize: 13, color: "var(--fg-muted)" } as const;
const bigNumber = { fontSize: 28, fontWeight: 700, margin: "0 0 4px" } as const;

/** Hook: laedt eine Quelle, aktualisiert alle 60 s und faengt Fehler pro Kachel ab. */
function useTileData<T>(load: () => Promise<T>): { data: T | null; failed: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const run = useCallback(async () => {
    try { setData(await load()); setFailed(false); } catch { setFailed(true); }
  }, [load]);
  useEffect(() => { run(); }, [run]);
  useAutoRefresh(run, 60000, true);
  return { data, failed };
}

const loadOrders = () => api.getAdminOrders();
const loadAgents = () => api.getAgentsMonitoring();
const loadEvents = async (): Promise<PaymentEvent[]> => {
  const [mismatch, unapplied] = await Promise.all([
    api.getPaymentEvents({ status: "mismatch", limit: 10 }),
    api.getPaymentEvents({ status: "unapplied", limit: 10 }),
  ]);
  return mergeEvents(mismatch, unapplied);
};

function Unavailable() {
  return <p style={muted}>Daten konnten nicht geladen werden.</p>;
}

/** Umsatzdaten: exakt aus GET /admin/stats/revenue, bei älterem Backend (404) geschätzt aus der Bestellliste. */
export type RevenueView =
  | { kind: "exact"; stats: RevenueStats }
  | { kind: "estimate"; summary: RevenueSummary };

export async function loadRevenue(): Promise<RevenueView> {
  try {
    return { kind: "exact", stats: await api.getRevenueStats(30) };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { kind: "estimate", summary: revenueLastDays(await api.getAdminOrders()) };
    }
    throw err;
  }
}

export function RevenueTile({ view }: { view: RevenueView | null }) {
  const byCurrency = view ? (view.kind === "exact" ? view.stats.by_currency : view.summary.byCurrency) : {};
  const currencies = Object.keys(byCurrency);
  const refunds = view?.kind === "exact" ? Object.entries(view.stats.refunded_cents_by_currency ?? {}).filter(([, c]) => c > 0) : [];
  return (
    <Tile id="tile-revenue" title="Umsatz, letzte 30 Tage">
      {!view ? <p style={muted}>Wird geladen…</p> : currencies.length === 0 ? (
        <p style={muted}>Keine bezahlten Bestellungen im Zeitraum.</p>
      ) : (
        <>
          {currencies.map((c) => (
            <p key={c} style={bigNumber} data-testid={`revenue-${c}`}>{formatMoney(byCurrency[c], c)}</p>
          ))}
          <p style={muted}>
            {view.kind === "exact"
              ? `${view.stats.paid_count} Zahlung(en), davon ${view.stats.renewals_count} Verlängerung(en)`
              : `${view.summary.paidCount} bezahlte Bestellung(en)`}
          </p>
        </>
      )}
      {refunds.length > 0 && (
        <p style={{ ...muted, marginTop: 8 }} data-testid="revenue-refunds">
          Erstattet im Zeitraum: {refunds.map(([c, cents]) => formatMoney(cents, c)).join(", ")} (nicht abgezogen)
        </p>
      )}
      {view?.kind === "estimate" && (
        <p style={{ ...muted, marginTop: 8, fontSize: 12 }}>
          Näherung: gezählt wird die letzte Zahlung je Bestellung; frühere Verlängerungen fehlen.
        </p>
      )}
    </Tile>
  );
}

export function OrdersTile({ orders }: { orders: Order[] | null }) {
  const counts = orders ? countByStatus(orders) : null;
  return (
    <Tile id="tile-orders" title="Bestellungen">
      {!counts ? <p style={muted}>Wird geladen…</p> : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
          {OVERVIEW_STATUSES.map((s) => (
            <li key={s} style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
              <Link to={`/admin/orders?status=${s}`} style={linkStyle}>{statusLabel(s)}</Link>
              <strong data-testid={`orders-${s}`}>{counts[s]}</strong>
            </li>
          ))}
        </ul>
      )}
    </Tile>
  );
}

export function FleetTile({ agents }: { agents: AgentMonitoringEntry[] | null }) {
  const load = agents ? fleetLoad(agents) : null;
  return (
    <Tile id="tile-fleet" title="Node-Auslastung">
      {!load ? <p style={muted}>Wird geladen…</p> : load.agentCount === 0 ? (
        <p style={muted}>Keine aktiven Agents. <Link to="/admin/agents" style={linkStyle}>Agent anlegen</Link></p>
      ) : (
        <>
          <div style={{ display: "grid", gap: 12 }}>
            <UtilizationBar label="Memory" unit="MB" used={load.memory.used} total={load.memory.total} percent={load.memory.percent} />
            <UtilizationBar label="Disk" unit="MB" used={load.disk.used} total={load.disk.total} percent={load.disk.percent} />
            <UtilizationBar label="CPU" unit="%" used={load.cpu.used} total={load.cpu.total} percent={load.cpu.percent} />
          </div>
          <p style={{ ...muted, marginTop: 10 }}>
            {load.agentCount} aktive(r) Agent(s)
            {load.busiest && <>, am höchsten ausgelastet: <strong>{load.busiest.name}</strong> ({load.busiest.percent} %)</>}
            {load.withoutLimit > 0 && <>; {load.withoutLimit} ohne hinterlegte Kapazität</>}
            . <Link to="/admin/agents/monitoring" style={linkStyle}>Fleet Monitoring</Link>
          </p>
        </>
      )}
    </Tile>
  );
}

export function PaymentEventsTile({ events }: { events: PaymentEvent[] | null }) {
  return (
    <Tile id="tile-events" title="Zahlungsereignisse mit Handlungsbedarf">
      {!events ? <p style={muted}>Wird geladen…</p> : events.length === 0 ? (
        <p style={muted}>Keine Abweichungen oder nicht zugeordneten Zahlungen.</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
          {events.slice(0, 5).map((e) => (
            <li key={e.id} style={{ fontSize: 13 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <StatusBadge status={e.status} size="sm" />
                <span style={{ color: "var(--fg-muted)" }}>{formatDateTime(e.received_at)}</span>
                {e.order_uuid && (
                  <Link to={`/admin/orders`} style={linkStyle}>Bestellung {e.order_uuid.slice(0, 8)}</Link>
                )}
              </div>
              {e.detail && <div style={{ color: "var(--fg)", marginTop: 2, wordBreak: "break-word" }}>{e.detail}</div>}
            </li>
          ))}
        </ul>
      )}
      <p style={{ ...muted, marginTop: 10, fontSize: 12 }}>
        Beträge, die nicht zur Bestellung passen, wurden nicht freigeschaltet. Bei „Erstattung prüfen“ ist Geld
        eingegangen, die Bestellung war schon beendet: Erstattung im Zahlungsanbieter veranlassen.
      </p>
    </Tile>
  );
}

/** Die drei datengetriebenen Kacheln; jede Quelle faellt einzeln aus, ohne die anderen zu stoeren. */
export function OverviewTiles() {
  const orders = useTileData(loadOrders);
  const revenue = useTileData(loadRevenue);
  const agents = useTileData(loadAgents);
  const events = useTileData(loadEvents);
  return (
    <>
      {revenue.failed && !revenue.data ? <Tile id="tile-revenue-err" title="Umsatz"><Unavailable /></Tile> : <RevenueTile view={revenue.data} />}
      {orders.failed && !orders.data ? <Tile id="tile-orders-err" title="Bestellungen"><Unavailable /></Tile> : <OrdersTile orders={orders.data} />}
      {agents.failed && !agents.data ? <Tile id="tile-fleet-err" title="Node-Auslastung"><Unavailable /></Tile> : <FleetTile agents={agents.data} />}
      {events.failed && !events.data ? <Tile id="tile-events-err" title="Zahlungsereignisse"><Unavailable /></Tile> : <PaymentEventsTile events={events.data} />}
    </>
  );
}
