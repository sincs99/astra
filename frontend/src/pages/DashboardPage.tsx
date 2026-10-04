import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, type Instance, type Order, type PowerSignal } from "../services/api";
import { BillingTickCard } from "../components/BillingTickCard";
import { OpenOrdersCard } from "../components/OpenOrdersCard";
import { ServerCard } from "../components/dashboard/ServerCard";
import { OrderCard } from "../components/dashboard/OrderCard";
import { PaymentBanners } from "../components/dashboard/PaymentBanners";
import { Icon } from "../components/ui/Icon";
import { useCurrentUser } from "../hooks/useCurrentUser";
import { useCheckout } from "../hooks/useCheckout";
import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { isRunning, orderForInstance, pendingPayment, waitingForCapacity } from "../lib/dashboard";
import { t } from "../i18n";
import { PageLayout, AutoRefreshToggle, Toast, useToast, LoadingState, ErrorState } from "../components/ui";

/** Kunden-Dashboard "Meine Server": Serverkarten, Hinweise zu offenen Zahlungen, Bestellungen ohne Server. */
export function DashboardPage() {
  const [instances, setInstances] = useState<Instance[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [onlinePayment, setOnlinePayment] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const touch = useMediaQuery("(max-width: 760px)");
  const { pay, paying } = useCheckout(toast.error);

  // Meldung von der vorherigen Seite (z.B. nach dem Löschen einer Instance), nur einmal anzeigen
  useEffect(() => {
    const message = (location.state as { toast?: string } | null)?.toast;
    if (message) {
      toast.success(message);
      navigate(location.pathname, { replace: true, state: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("dashboard");

  const load = useCallback(async (silent = false) => {
    try {
      if (!silent) { setLoading(true); setError(null); }
      const [list, myOrders, billing] = await Promise.all([
        api.getClientInstances(),
        // Bestellungen sind für die Anzeige von Laufzeit und Zahlungshinweisen nützlich, aber nicht kritisch
        api.getMyOrders().catch(() => [] as Order[]),
        api.getBillingInfo().catch(() => null),
      ]);
      setInstances(list);
      setOrders(myOrders);
      if (billing) setOnlinePayment(billing.online_payment);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : t("dash.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useAutoRefresh(() => load(true), 15000, autoRefresh);

  const user = useCurrentUser();

  const power = async (inst: Instance, signal: PowerSignal) => {
    try {
      setActing(inst.uuid);
      const result = await api.sendPowerAction(inst.uuid, signal);
      toast.success(result.message);
      setTimeout(() => load(true), 800);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("dash.actionFailed"));
    } finally {
      setActing(null);
    }
  };

  // Bezahlen und Verlängern laufen über denselben Checkout; ohne Online-Zahlung geht es zu den Bestellungen
  const payOrder = async (order: Order) => {
    const outcome = await pay(order);
    if (outcome === "manual") { setOnlinePayment(false); navigate("/orders"); }
    if (outcome === "stale") await load(true);
  };

  const cancelOrder = async (order: Order) => {
    try {
      await api.cancelOrder(order.uuid);
      toast.success(t("dash.cancelled"));
      await load(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("orders.cancelFailed"));
    }
  };

  const pending = pendingPayment(orders);
  const waiting = waitingForCapacity(orders);
  const running = instances.filter(isRunning).length;
  const subtitle = instances.length === 0
    ? t("dash.subtitleNone")
    : instances.length === 1 ? t("dash.subtitleOne", { m: running }) : t("dash.subtitle", { n: instances.length, m: running });

  const newServer = touch ? (
    <Link to="/shop" className="btn btn-primary btn-touch btn-icon" aria-label={t("dash.newServer")}><Icon name="plus" size={18} /></Link>
  ) : (
    <Link to="/shop" className="btn btn-primary"><Icon name="plus" size={16} />{t("dash.newServer")}</Link>
  );

  const isEmpty = instances.length === 0 && pending.length === 0 && waiting.length === 0;

  return (
    <PageLayout title={t("dash.title")} subtitle={subtitle} actions={newServer} maxWidth={1200}>
      <Toast {...toast} />

      <div className="stack">
        {user?.is_admin && <BillingTickCard onlyWhenUnhealthy />}
        {user?.is_admin && <OpenOrdersCard />}

        {error && <ErrorState message={error} onRetry={() => load()} />}

        <PaymentBanners orders={pending} onlinePayment={onlinePayment} paying={paying} onPay={payOrder} />

        {loading ? (
          <LoadingState />
        ) : isEmpty ? (
          <div className="card-empty">
            <p style={{ margin: "0 0 8px" }}>{user?.is_admin ? t("dash.noInstancesAdmin") : t("dash.empty")}</p>
            {!user?.is_admin && <Link to="/shop">{t("dash.emptyAction")}</Link>}
          </div>
        ) : (
          <section className="cards-grid" aria-label={t("dash.cardsLabel")}>
            {instances.map((inst) => (
              <ServerCard key={inst.uuid} instance={inst} order={orderForInstance(orders, inst.uuid)}
                acting={acting === inst.uuid} onPower={power} onRenew={payOrder} onlinePayment={onlinePayment} />
            ))}
            {[...pending, ...waiting].map((o) => (
              <OrderCard key={o.uuid} order={o} onlinePayment={onlinePayment} paying={paying === o.uuid} onPay={payOrder} onCancel={cancelOrder} />
            ))}
          </section>
        )}

        {!loading && !isEmpty && <p className="hint">{t("dash.footnote")}</p>}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />
        </div>
      </div>
    </PageLayout>
  );
}
