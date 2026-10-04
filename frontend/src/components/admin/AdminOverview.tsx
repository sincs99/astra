import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type AgentMonitoringEntry, type BillingStatus, type Instance, type Order, type PaymentEvent, type RevenueStats } from "../../services/api";
import { formatMoney } from "../../lib/money";
import { formatDateTime, formatTimeAgo } from "../../lib/dates";
import { dueWithin, instanceCounts, mergeEvents, ordersInPeriod, problemNodes, revenueLastDays, type RevenueSummary } from "../../lib/adminOverview";
import { useAutoRefresh } from "../../hooks/useAutoRefresh";
import { NodesPanel } from "./NodesPanel";
import { PaymentsPanel } from "./PaymentsPanel";

export const REFRESH_MS = 30_000;
export const PERIODS = [7, 30, 90] as const;
export type Period = (typeof PERIODS)[number];

/** Lädt eine Quelle, aktualisiert regelmäßig und fängt Fehler pro Kachel ab (die übrigen bleiben sichtbar). */
function useSource<T>(load: () => Promise<T>): { data: T | null; failed: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const run = useCallback(async () => {
    try { setData(await load()); setFailed(false); } catch { setFailed(true); }
  }, [load]);
  useEffect(() => { run(); }, [run]);
  useAutoRefresh(run, REFRESH_MS, true);
  return { data, failed };
}

/** Umsatz: exakt aus GET /admin/stats/revenue, bei älterem Backend (404) geschätzt aus der Bestellliste. */
export type RevenueView =
  | { kind: "exact"; stats: RevenueStats }
  | { kind: "estimate"; summary: RevenueSummary };

export async function loadRevenue(days: number): Promise<RevenueView> {
  try {
    return { kind: "exact", stats: await api.getRevenueStats(days) };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { kind: "estimate", summary: revenueLastDays(await api.getAdminOrders(), days) };
    }
    throw err;
  }
}

const loadEvents = async (): Promise<PaymentEvent[]> => {
  const [mismatch, unapplied] = await Promise.all([
    api.getPaymentEvents({ status: "mismatch", limit: 10 }),
    api.getPaymentEvents({ status: "unapplied", limit: 10 }),
  ]);
  return mergeEvents(mismatch, unapplied);
};

function Tile({ label, children, failed }: { label: string; children: React.ReactNode; failed?: boolean }) {
  return (
    <div className="tile" role="group" aria-label={label}>
      {failed ? <span className="lbl">{label}: Daten konnten nicht geladen werden.</span> : children}
    </div>
  );
}

function Loading() {
  return <span className="lbl">Wird geladen…</span>;
}

export function RevenueTile({ view, days, failed }: { view: RevenueView | null; days: number; failed?: boolean }) {
  const byCurrency = (view ? (view.kind === "exact" ? view.stats.by_currency : view.summary.byCurrency) : {}) ?? {};
  const currencies = Object.keys(byCurrency);
  const refunds = view?.kind === "exact" ? Object.entries(view.stats.refunded_cents_by_currency ?? {}).filter(([, c]) => c > 0) : [];
  return (
    <Tile label={`Umsatz ${days} Tage`} failed={failed && !view}>
      {!view ? <Loading /> : (
        <>
          {currencies.length === 0 ? <span className="big" data-testid="revenue-none">–</span> : currencies.map((c) => (
            <span key={c} className="big" data-testid={`revenue-${c}`}>{formatMoney(byCurrency[c], c)}</span>
          ))}
          <span className="lbl">Umsatz {days} Tage</span>
          <span className="sub">
            {view.kind === "exact"
              ? `${view.stats.paid_count} Zahlung(en), davon ${view.stats.renewals_count} Verlängerung(en)`
              : `${view.summary.paidCount} bezahlte Bestellung(en), Näherung`}
          </span>
          {refunds.length > 0 && (
            <span className="sub" data-testid="revenue-refunds">Erstattet: {refunds.map(([c, cents]) => formatMoney(cents, c)).join(", ")} (nicht abgezogen)</span>
          )}
        </>
      )}
    </Tile>
  );
}

export function OrdersTile({ orders, days, failed }: { orders: Order[] | null; days: number; failed?: boolean }) {
  const stats = orders ? ordersInPeriod(orders, days) : null;
  return (
    <Tile label={`Bestellungen ${days} Tage`} failed={failed && !orders}>
      {!stats ? <Loading /> : (
        <>
          <span className="big" data-testid="orders-total">{stats.total}</span>
          <span className="lbl">Bestellungen {days} Tage</span>
          <div className="legend">
            <span><span className="dot dot-ok" aria-hidden="true" />{stats.paid} bezahlt</span>
            <span><span className="dot dot-warn" aria-hidden="true" />{stats.waiting} wartend</span>
            <span><span className="dot dot-danger" aria-hidden="true" />{stats.overdue} überfällig</span>
          </div>
        </>
      )}
    </Tile>
  );
}

export function InstancesTile({ instances, problem, failed }: { instances: Instance[] | null; problem: AgentMonitoringEntry[]; failed?: boolean }) {
  const counts = instances ? instanceCounts(instances, problem) : null;
  return (
    <Tile label="Instances laufen" failed={failed && !instances}>
      {!counts ? <Loading /> : (
        <>
          <span className="big" data-testid="instances-running">{counts.running} / {counts.total}</span>
          <span className="lbl">Instances laufen</span>
          {counts.onProblemNodes > 0 && (
            <span className="sub text-danger">{counts.onProblemNodes} auf gestörten Nodes ({problem.map((a) => a.name).join(", ")})</span>
          )}
        </>
      )}
    </Tile>
  );
}

export function TickTile({ status, failed }: { status: BillingStatus | null; failed?: boolean }) {
  const waiting = status?.awaiting_provisioning;
  return (
    <Tile label="Abrechnungs-Tick" failed={failed && !status}>
      {!status ? <Loading /> : (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className={`dot ${status.healthy ? "dot-ok" : "dot-danger"}`} style={{ width: 12, height: 12 }} aria-hidden="true" />
            <span className="big" style={{ fontSize: 20 }}>Abrechnungs-Tick</span>
          </div>
          <span className="lbl">
            {status.healthy ? "läuft" : "läuft nicht"} · letzter Lauf {status.last_run_at ? `${formatTimeAgo(status.last_run_at)}` : "noch nie"}
          </span>
          <span className="sub">
            {status.orders_needing_tick} Bestellung(en) warten auf den Tick
            {waiting && waiting.count > 0 ? ` · ${waiting.count} bezahlt ohne freien Node` : ""}
          </span>
        </>
      )}
    </Tile>
  );
}

function Banners({ problem, events, due, tick }: {
  problem: AgentMonitoringEntry[]; events: PaymentEvent[] | null; due: Order[]; tick: BillingStatus | null;
}) {
  const warnings: string[] = [];
  if (events && events.length > 0) warnings.push(`${events.length} Zahlung(en) mit Fehlstatus warten auf Prüfung.`);
  if (due.length > 0) warnings.push(`${due.length} Bestellung(en) laufen in 24 h ab.`);
  if (tick && !tick.healthy) warnings.push("Abrechnungs-Tick läuft nicht: Container billing prüfen.");
  if (tick?.awaiting_provisioning?.waiting_too_long) warnings.push("Bezahlte Bestellung wartet zu lange auf einen Node: Kapazität prüfen.");
  return (
    <>
      {problem.length > 0 && (
        <div role="alert" className="banner banner-danger">
          <span className="dot dot-danger" aria-hidden="true" />
          <span className="banner-text">
            {problem.map((a, i) => (
              <span key={a.id}>
                {i > 0 && " "}Node <span className="mono">{a.name}</span> {a.health_status === "unreachable" ? "nicht erreichbar" : "beeinträchtigt"}
                {" "}– {a.instance_count} Instances betroffen{a.last_seen_at ? `. Letzter Heartbeat ${formatDateTime(a.last_seen_at)}.` : "."}
              </span>
            ))}
          </span>
          <Link to="/admin/agents/monitoring" className="btn btn-sm">Node öffnen</Link>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="status" className="banner banner-warn">
          <span className="dot dot-warn" aria-hidden="true" />
          <span className="banner-text">{warnings.join(" ")}</span>
          <Link to={events && events.length > 0 ? "/admin/orders" : "/admin/system"} className="btn btn-sm">Prüfen</Link>
        </div>
      )}
    </>
  );
}

/** Admin-Übersicht nach design/mockups/AdminOverview.html; jede Datenquelle fällt einzeln aus. */
export function AdminOverview({ period }: { period: Period }) {
  const loadRev = useCallback(() => loadRevenue(period), [period]);
  const revenue = useSource(loadRev);
  const orders = useSource(api.getAdminOrders);
  const agents = useSource(api.getAgentsMonitoring);
  const instances = useSource(api.getInstances);
  const events = useSource(loadEvents);
  const tick = useSource(api.getBillingStatus);

  const problem = agents.data ? problemNodes(agents.data) : [];
  const due = orders.data ? dueWithin(orders.data, 24) : [];

  return (
    <div className="stack">
      <Banners problem={problem} events={events.data} due={due} tick={tick.data} />

      <section className="tiles" aria-label="Kennzahlen">
        <RevenueTile view={revenue.data} days={period} failed={revenue.failed} />
        <OrdersTile orders={orders.data} days={period} failed={orders.failed} />
        <InstancesTile instances={instances.data} problem={problem} failed={instances.failed} />
        <TickTile status={tick.data} failed={tick.failed} />
      </section>

      <div className="cols">
        {agents.failed && !agents.data ? (
          <section className="panel"><div className="panel-body"><p className="hint">Node-Auslastung: Daten konnten nicht geladen werden.</p></div></section>
        ) : <NodesPanel agents={agents.data} />}
        {events.failed && !events.data ? (
          <section className="panel"><div className="panel-body"><p className="hint">Zahlungen: Daten konnten nicht geladen werden.</p></div></section>
        ) : <PaymentsPanel events={events.data} due={due} />}
      </div>
    </div>
  );
}
