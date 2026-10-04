import { useEffect, useRef, useState } from "react";
import { api, type InvoiceRow } from "../services/api";
import { formatDate } from "../lib/dates";
import { formatMoney } from "../lib/money";
import { t } from "../i18n";
import { PageLayout, ScrollRegion, Toast, useToast } from "../components/ui";

/** "2026-10" -> erster und letzter Tag des Monats als JJJJ-MM-TT. */
export function monthRange(month: string): { from: string; to: string } | null {
  const m = /^(\d{4})-(\d{2})$/.exec(month);
  if (!m) return null;
  const year = Number(m[1]);
  const mon = Number(m[2]);
  if (mon < 1 || mon > 12) return null;
  const last = new Date(Date.UTC(year, mon, 0)).getUTCDate();
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}` };
}

const currentMonth = () => new Date().toISOString().slice(0, 7);

/** Admin: Rechnungen und Gutschriften eines Monats für die Buchhaltung, mit CSV-Export (M70). */
export function AdminInvoicesPage() {
  const toast = useToast();
  const [month, setMonth] = useState(currentMonth);
  const [rows, setRows] = useState<InvoiceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const latest = useRef(0);

  const range = monthRange(month);

  const load = async () => {
    if (!range) return;
    const mine = ++latest.current;
    try {
      setLoading(true);
      setError(null);
      const result = await api.getInvoices(range.from, range.to);
      if (mine === latest.current) setRows(result);
    } catch (err) {
      if (mine === latest.current) setError(err instanceof Error && err.message ? err.message : t("ainv.loadFailed"));
    } finally {
      if (mine === latest.current) setLoading(false);
    }
  };

  useEffect(() => { load(); }, [month]);

  const download = async () => {
    if (!range) return;
    try {
      setDownloading(true);
      const csv = await api.getInvoicesCsv(range.from, range.to);
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `rechnungen-${month}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : t("ainv.downloadFailed"));
    } finally {
      setDownloading(false);
    }
  };

  const actions = (
    <button type="button" className="btn btn-sm" disabled={!range || downloading} onClick={download}>
      {downloading ? t("ainv.downloading") : t("ainv.csv")}
    </button>
  );

  return (
    <PageLayout title={t("ainv.title")} subtitle={t("ainv.subtitle")} actions={actions} maxWidth={1200}>
      <Toast {...toast} />
      <div className="stack">
        <div className="field" style={{ maxWidth: 220 }}>
          <label htmlFor="inv-month">{t("ainv.month")}</label>
          <input id="inv-month" type="month" className="inp" value={month} max={currentMonth()}
            onChange={(e) => setMonth(e.target.value)} />
        </div>

        {error && (
          <div role="alert" className="banner banner-danger">
            <span className="dot dot-danger" aria-hidden="true" />
            <div className="banner-text"><strong>{t("common.error")}</strong> {error}</div>
            <button type="button" className="btn btn-sm" onClick={load}>{t("common.retry")}</button>
          </div>
        )}

        {!range ? (
          <div className="card-empty" role="status">{t("ainv.pickMonth")}</div>
        ) : loading ? (
          <p className="hint" role="status">{t("ainv.loading")}</p>
        ) : rows.length === 0 && !error ? (
          <div className="card-empty" role="status">{t("ainv.empty")}</div>
        ) : rows.length > 0 && (
          <div className="panel">
            <ScrollRegion label={t("ainv.tableLabel")}>
              <table className="tbl tbl-cards">
                <caption className="sr-only">{t("ainv.title")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("ainv.colNumber")}</th>
                    <th scope="col">{t("ainv.colKind")}</th>
                    <th scope="col">{t("ainv.colDate")}</th>
                    <th scope="col">{t("ainv.colCustomer")}</th>
                    <th scope="col" className="num">{t("ainv.colNet")}</th>
                    <th scope="col" className="num">{t("ainv.colVat")}</th>
                    <th scope="col" className="num">{t("ainv.colGross")}</th>
                    <th scope="col">{t("ainv.colCurrency")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.number}>
                      <td data-label={t("ainv.colNumber")} className="mono">{r.number}</td>
                      <td data-label={t("ainv.colKind")}>{t(r.kind === "credit_note" ? "ainv.kindCreditNote" : "ainv.kindInvoice")}</td>
                      <td data-label={t("ainv.colDate")}>{formatDate(r.issued_at)}</td>
                      <td data-label={t("ainv.colCustomer")}>{r.customer_name ?? r.customer ?? r.username ?? "–"}</td>
                      <td data-label={t("ainv.colNet")} className="num mono">{formatMoney(r.net_cents, r.currency)}</td>
                      <td data-label={t("ainv.colVat")} className="num mono">{formatMoney(r.vat_cents, r.currency)}</td>
                      <td data-label={t("ainv.colGross")} className="num mono">{formatMoney(r.gross_cents, r.currency)}</td>
                      <td data-label={t("ainv.colCurrency")} className="mono">{r.currency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
