import { useState } from "react";
import { Link } from "react-router-dom";
import { PageLayout } from "../components/ui";
import { t } from "../i18n";
import { AdminOverview, PERIODS, REFRESH_MS, type Period } from "../components/admin/AdminOverview";

/** Admin-Startseite: Warnungen, Kennzahlen, Node-Auslastung und auffällige Zahlungen. */
export function AdminOverviewPage() {
  const [period, setPeriod] = useState<Period>(30);
  const actions = (
    <>
      <label htmlFor="period" className="sr-only">{t("aover.period")}</label>
      <select id="period" className="inp" style={{ width: "auto", height: 32, minHeight: 32 }} value={period}
        onChange={(e) => setPeriod(Number(e.target.value) as Period)}>
        {PERIODS.map((p) => <option key={p} value={p}>{t("aover.periodDays", { n: p })}</option>)}
      </select>
      <Link to="/admin/orders?status=pending_payment" className="btn btn-sm btn-primary">{t("aover.markPaid")}</Link>
    </>
  );
  return (
    <PageLayout title={t("aover.title")} subtitle={t("aover.subtitle", { n: REFRESH_MS / 1000 })} actions={actions} maxWidth={1200}>
      <AdminOverview period={period} />
    </PageLayout>
  );
}
