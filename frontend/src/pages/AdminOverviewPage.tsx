import { useState } from "react";
import { Link } from "react-router-dom";
import { PageLayout } from "../components/ui";
import { AdminOverview, PERIODS, REFRESH_MS, type Period } from "../components/admin/AdminOverview";

/** Admin-Startseite: Warnungen, Kennzahlen, Node-Auslastung und auffällige Zahlungen. */
export function AdminOverviewPage() {
  const [period, setPeriod] = useState<Period>(30);
  const actions = (
    <>
      <label htmlFor="period" className="sr-only">Zeitraum</label>
      <select id="period" className="inp" style={{ width: "auto", height: 32, minHeight: 32 }} value={period}
        onChange={(e) => setPeriod(Number(e.target.value) as Period)}>
        {PERIODS.map((p) => <option key={p} value={p}>Letzte {p} Tage</option>)}
      </select>
      <Link to="/admin/orders?status=pending_payment" className="btn btn-sm btn-primary">Als bezahlt markieren</Link>
    </>
  );
  return (
    <PageLayout title="Übersicht" subtitle={`aktualisiert alle ${REFRESH_MS / 1000} s`} actions={actions} maxWidth={1200}>
      <AdminOverview period={period} />
    </PageLayout>
  );
}
