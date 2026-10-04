import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { useEffect, useState } from "react";
import { api, type JobEntry, type JobSummary } from "../services/api";
import { PageLayout, AutoRefreshToggle, StatusBadge, statusLabel } from "../components/ui";
import { formatLogTime } from "../lib/dates";
import { t } from "../i18n";

type StatusFilter = "" | "pending" | "running" | "completed" | "failed" | "retrying";

const STATUSES: Exclude<StatusFilter, "">[] = ["pending", "running", "completed", "failed", "retrying"];

export function AdminJobsPage() {
  const [jobs, setJobs] = useState<JobEntry[]>([]);
  const [summary, setSummary] = useState<JobSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [typeFilter, setTypeFilter] = useState("");

  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("jobs");

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      if (!silent) setError(null);
      const [jobData, summaryData] = await Promise.all([
        api.getJobs({ status: statusFilter || undefined, type: typeFilter || undefined, page, per_page: 50 }),
        api.getJobsSummary(),
      ]);
      setJobs(jobData.items);
      setTotal(jobData.total);
      setPages(jobData.pages);
      setSummary(summaryData);
    } catch (err) {
      // Bei stillem Refresh vorhandene Daten nicht durch Fehler ersetzen
      if (!silent) setError(err instanceof Error ? err.message : t("asys.jobs.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [statusFilter, typeFilter, page]);

  useAutoRefresh(() => loadData(true), 15000, autoRefresh);

  const refreshButton = (
    <button type="button" className="btn btn-sm" onClick={() => loadData()}>{t("asys.jobs.refresh")}</button>
  );

  return (
    <PageLayout title={t("asys.jobs.title")} actions={refreshButton}>
      <div className="stack">
        {summary && (
          <div className="tiles" role="group" aria-label={t("asys.jobs.summaryLabel")}>
            <Tile label={t("asys.jobs.tileTotal")} value={summary.total} />
            {STATUSES.map((s) => (
              <Tile key={s} label={statusLabel(s)} value={summary.by_status?.[s] || 0} />
            ))}
          </div>
        )}

        <section className="panel">
          <div className="panel-body" style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="field">
              <label htmlFor="jobs-status">{t("asys.jobs.filterStatus")}</label>
              <select id="jobs-status" className="inp" value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setPage(1); }}>
                <option value="">{t("asys.jobs.all")}</option>
                {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="jobs-type">{t("asys.jobs.filterType")}</label>
              <select id="jobs-type" className="inp" value={typeFilter}
                onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}>
                <option value="">{t("asys.jobs.all")}</option>
                {summary && Object.keys(summary.by_type ?? {}).map((ty) => (
                  <option key={ty} value={ty}>{ty} ({summary.by_type?.[ty]})</option>
                ))}
              </select>
            </div>
            <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />
            <span className="hint" style={{ paddingBottom: 10 }}>
              {t("asys.jobs.totalInfo", { total, page, pages: pages || 1 })}
            </span>
          </div>
        </section>

        {error && (
          <div className="banner banner-danger" role="alert">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text">{error}</span>
            <button type="button" className="btn btn-sm" onClick={() => loadData()}>{t("common.retry")}</button>
          </div>
        )}

        {loading ? (
          <p className="hint" role="status" aria-busy="true">{t("asys.jobs.loading")}</p>
        ) : jobs.length === 0 ? (
          !error && <div className="card-empty">{t("asys.jobs.empty")}</div>
        ) : (
          <section className="panel">
            <div role="region" aria-label={t("asys.jobs.tableLabel")} tabIndex={0} style={{ overflowX: "auto" }}>
              <table className="tbl tbl-cards">
                <thead>
                  <tr>
                    <th scope="col">{t("asys.jobs.colId")}</th>
                    <th scope="col">{t("asys.jobs.colType")}</th>
                    <th scope="col">{t("asys.jobs.colStatus")}</th>
                    <th scope="col">{t("asys.jobs.colAttempts")}</th>
                    <th scope="col">{t("asys.jobs.colCreated")}</th>
                    <th scope="col">{t("asys.jobs.colStarted")}</th>
                    <th scope="col">{t("asys.jobs.colFinished")}</th>
                    <th scope="col">{t("asys.jobs.colResult")}</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id}>
                      <td data-label={t("asys.jobs.colId")}><span className="mono" title={job.uuid}>#{job.id}</span></td>
                      <td data-label={t("asys.jobs.colType")}><span className="mono">{job.job_type}</span></td>
                      <td data-label={t("asys.jobs.colStatus")}><StatusBadge status={job.status} size="sm" /></td>
                      <td data-label={t("asys.jobs.colAttempts")} className="mono">{job.attempts}/{job.max_attempts}</td>
                      <td data-label={t("asys.jobs.colCreated")} style={{ whiteSpace: "nowrap" }}>{formatLogTime(job.created_at)}</td>
                      <td data-label={t("asys.jobs.colStarted")} style={{ whiteSpace: "nowrap" }}>{formatLogTime(job.started_at)}</td>
                      <td data-label={t("asys.jobs.colFinished")} style={{ whiteSpace: "nowrap" }}>{formatLogTime(job.finished_at)}</td>
                      <td data-label={t("asys.jobs.colResult")} style={{ maxWidth: 300, overflowWrap: "anywhere" }}>
                        {job.error ? (
                          <span className="text-danger" title={job.error}>{clip(job.error)}</span>
                        ) : job.result ? (
                          <span title={job.result}>{clip(job.result)}</span>
                        ) : (
                          <span className="hint">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pages > 1 && (
              <nav className="panel-foot" aria-label={t("asys.jobs.pagination")} style={{ justifyContent: "center", alignItems: "center" }}>
                <button type="button" className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>{t("asys.jobs.prev")}</button>
                <span>{t("asys.jobs.pageOf", { page, pages })}</span>
                <button type="button" className="btn btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>{t("asys.jobs.next")}</button>
              </nav>
            )}
          </section>
        )}
      </div>
    </PageLayout>
  );
}

function clip(s: string): string {
  return s.length > 80 ? `${s.substring(0, 80)}...` : s;
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="tile">
      <div className="big">{value}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}
