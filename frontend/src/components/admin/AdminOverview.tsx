import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type AgentMonitoringEntry, type BillingStatus, type Instance, type Order, type PaymentEvent, type RevenueStats } from "../../services/api";
import { t, dateLocale } from "../../i18n";
import { formatMoney } from "../../lib/money";
import { formatDateTime, formatTimeAgo } from "../../lib/dates";
import { dueWithin, plural, instanceCounts, mergeEvents, ordersInPeriod, problemNodes, revenueLastDays, revenueTrend, type RevenueSummary } from "../../lib/adminOverview";
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
      {failed ? <span className="lbl">{t("aover.tileFailed", { label })}</span> : children}
    </div>
  );
}

function Loading() {
  return <span className="lbl">{t("aover.loading")}</span>;
}

export function RevenueTile({ view, days, failed }: { view: RevenueView | null; days: number; failed?: boolean }) {
  const byCurrency = (view ? (view.kind === "exact" ? view.stats.by_currency : view.summary.byCurrency) : {}) ?? {};
  const currencies = Object.keys(byCurrency);
  const refunds = view?.kind === "exact" ? Object.entries(view.stats.refunded_cents_by_currency ?? {}).filter(([, c]) => c > 0) : [];
  return (
    <Tile label={t("aover.revenue", { n: days })} failed={failed && !view}>
      {!view ? <Loading /> : (
        <>
          {currencies.length === 0 ? <span className="big" data-testid="revenue-none">–</span> : currencies.map((c) => (
            <span key={c} className="big" data-testid={`revenue-${c}`}>{formatMoney(byCurrency[c], c)}</span>
          ))}
          <span className="lbl">{t("aover.revenue", { n: days })}</span>
          {view.kind === "exact" && view.stats.prev_by_currency !== undefined && currencies.map((c) => {
            const trend = revenueTrend(byCurrency[c], view.stats.prev_by_currency?.[c]);
            const percent = new Intl.NumberFormat(dateLocale(), { signDisplay: "exceptZero" }).format(trend.percent);
            return (
              <span key={c} className={`sub trend-${trend.kind}`} data-testid={`revenue-trend-${c}`}>
                {trend.kind === "none"
                  ? t("aover.trendNone", { c: currencies.length > 1 ? `${c}: ` : "" })
                  : t("aover.trend", { c: currencies.length > 1 ? `${c}: ` : "", percent })}
              </span>
            );
          })}
          <span className="sub">
            {view.kind === "exact"
              ? plural(view.stats.paid_count, "aover.paymentsOne", "aover.paymentsOther", { r: view.stats.renewals_count })
              : plural(view.summary.paidCount, "aover.paidOrdersApproxOne", "aover.paidOrdersApproxOther")}
          </span>
          {refunds.length > 0 && (
            <span className="sub" data-testid="revenue-refunds">{t("aover.refunded", { amount: refunds.map(([c, cents]) => formatMoney(cents, c)).join(", ") })}</span>
          )}
        </>
      )}
    </Tile>
  );
}

export function OrdersTile({ orders, days, failed }: { orders: Order[] | null; days: number; failed?: boolean }) {
  const stats = orders ? ordersInPeriod(orders, days) : null;
  return (
    <Tile label={t("aover.orders", { n: days })} failed={failed && !orders}>
      {!stats ? <Loading /> : (
        <>
          <span className="big" data-testid="orders-total">{stats.total}</span>
          <span className="lbl">{t("aover.orders", { n: days })}</span>
          <div className="legend">
            <span><span className="dot dot-ok" aria-hidden="true" />{t("aover.paid", { n: stats.paid })}</span>
            <span><span className="dot dot-warn" aria-hidden="true" />{t("aover.waiting", { n: stats.waiting })}</span>
            <span><span className="dot dot-danger" aria-hidden="true" />{t("aover.overdue", { n: stats.overdue })}</span>
          </div>
        </>
      )}
    </Tile>
  );
}

export function InstancesTile({ instances, problem, failed }: { instances: Instance[] | null; problem: AgentMonitoringEntry[]; failed?: boolean }) {
  const counts = instances ? instanceCounts(instances, problem) : null;
  return (
    <Tile label={t("aover.instancesRunning")} failed={failed && !instances}>
      {!counts ? <Loading /> : (
        <>
          <span className="big" data-testid="instances-running">{counts.running} / {counts.total}</span>
          <span className="lbl">{t("aover.instancesRunning")}</span>
          {counts.onProblemNodes > 0 && (
            <span className="sub text-danger">{t("aover.onProblemNodes", { n: counts.onProblemNodes, names: problem.map((a) => a.name).join(", ") })}</span>
          )}
        </>
      )}
    </Tile>
  );
}

export function TickTile({ status, failed }: { status: BillingStatus | null; failed?: boolean }) {
  const waiting = status?.awaiting_provisioning;
  return (
    <Tile label={t("aover.tick")} failed={failed && !status}>
      {!status ? <Loading /> : (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className={`dot ${status.healthy ? "dot-ok" : "dot-danger"}`} style={{ width: 12, height: 12 }} aria-hidden="true" />
            <span className="big" style={{ fontSize: 20 }}>{t("aover.tick")}</span>
          </div>
          <span className="lbl">
            {status.healthy ? t("aover.tickRunning") : t("aover.tickNotRunning")} · {t("aover.lastRun", { when: status.last_run_at ? formatTimeAgo(status.last_run_at) : t("aover.never") })}
          </span>
          <span className="sub">
            {plural(status.orders_needing_tick, "aover.ordersWaitingOne", "aover.ordersWaitingOther")}
            {waiting && waiting.count > 0 ? ` · ${t("aover.paidNoNode", { n: waiting.count })}` : ""}
          </span>
        </>
      )}
    </Tile>
  );
}

/** Eine Störungszeile je Node; der Name steht als mono-Span im Text. */
function nodeLine(a: AgentMonitoringEntry) {
  const [pre, post = ""] = t("aover.nodeLine", { name: "\u0000", state: a.health_status === "unreachable" ? t("aover.nodeUnreachable") : t("aover.nodeDegraded") }).split("\u0000");
  return (
    <>
      {pre}<span className="mono">{a.name}</span>{post} – {plural(a.instance_count, "aover.instancesAffectedOne", "aover.instancesAffectedOther")}
      {a.last_seen_at ? `. ${t("aover.lastHeartbeat", { when: formatDateTime(a.last_seen_at) })}` : "."}
    </>
  );
}

function Banners({ problem, events, due, tick }: {
  problem: AgentMonitoringEntry[]; events: PaymentEvent[] | null; due: Order[]; tick: BillingStatus | null;
}) {
  const warnings: string[] = [];
  if (events && events.length > 0) warnings.push(plural(events.length, "aover.warnEventsOne", "aover.warnEventsOther"));
  if (due.length > 0) warnings.push(plural(due.length, "aover.warnDueOne", "aover.warnDueOther"));
  if (tick && !tick.healthy) warnings.push(t("aover.warnTick"));
  if (tick?.awaiting_provisioning?.waiting_too_long) warnings.push(t("aover.warnWaitingTooLong"));
  return (
    <>
      {problem.length > 0 && (
        <div role="alert" className="banner banner-danger">
          <span className="dot dot-danger" aria-hidden="true" />
          <span className="banner-text">
            {problem.map((a, i) => (
              <span key={a.id}>
                {i > 0 && " "}{nodeLine(a)}
              </span>
            ))}
          </span>
          <Link to="/admin/agents/monitoring" className="btn btn-sm">{t("aover.openNode")}</Link>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="status" className="banner banner-warn">
          <span className="dot dot-warn" aria-hidden="true" />
          <span className="banner-text">{warnings.join(" ")}</span>
          <Link to={events && events.length > 0 ? "/admin/orders" : "/admin/system"} className="btn btn-sm">{t("aover.check")}</Link>
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

      <section className="tiles" aria-label={t("aover.metrics")}>
        <RevenueTile view={revenue.data} days={period} failed={revenue.failed} />
        <OrdersTile orders={orders.data} days={period} failed={orders.failed} />
        <InstancesTile instances={instances.data} problem={problem} failed={instances.failed} />
        <TickTile status={tick.data} failed={tick.failed} />
      </section>

      <div className="cols">
        {agents.failed && !agents.data ? (
          <section className="panel"><div className="panel-body"><p className="hint">{t("aover.nodesFailed")}</p></div></section>
        ) : <NodesPanel agents={agents.data} />}
        {events.failed && !events.data ? (
          <section className="panel"><div className="panel-body"><p className="hint">{t("aover.paymentsFailed")}</p></div></section>
        ) : <PaymentsPanel events={events.data} due={due} />}
      </div>
    </div>
  );
}
