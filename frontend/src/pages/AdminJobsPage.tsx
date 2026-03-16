import { useEffect, useState } from "react";
import { api, type JobEntry, type JobSummary } from "../services/api";
import {
  PageLayout, StatusBadge, LoadingState, EmptyState, ErrorState,
  cardStyle, inputStyle, labelStyle, btnDefault, thStyle, tdStyle,
} from "../components/ui";

type StatusFilter = "" | "pending" | "running" | "completed" | "failed" | "retrying";

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

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [jobData, summaryData] = await Promise.all([
        api.getJobs({ status: statusFilter || undefined, type: typeFilter || undefined, page, per_page: 50 }),
        api.getJobsSummary(),
      ]);
      setJobs(jobData.items);
      setTotal(jobData.total);
      setPages(jobData.pages);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [statusFilter, typeFilter, page]);

  return (
    <PageLayout title="Background Jobs">

      {/* Summary Kacheln */}
      {summary && (
        <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
          <MiniCard label="Gesamt" value={summary.total} />
          <MiniCard label="Pending" value={summary.by_status.pending || 0} color="#1976d2" />
          <MiniCard label="Running" value={summary.by_status.running || 0} color="#f57c00" />
          <MiniCard label="Completed" value={summary.by_status.completed || 0} color="#4caf50" />
          <MiniCard label="Failed" value={summary.by_status.failed || 0} color="#d32f2f" />
          <MiniCard label="Retrying" value={summary.by_status.retrying || 0} color="#9c27b0" />
        </div>
      )}

      {/* Filter */}
      <div style={{ ...cardStyle, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <label style={labelStyle}>Status</label>
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value as StatusFilter); setPage(1); }} style={inputStyle}>
            <option value="">Alle</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="retrying">Retrying</option>
          </select>
        </div>
        <div>
          <label style={labelStyle}>Typ</label>
          <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1); }} style={inputStyle}>
            <option value="">Alle</option>
            {summary && Object.keys(summary.by_type).map(t => (
              <option key={t} value={t}>{t} ({summary.by_type[t]})</option>
            ))}
          </select>
        </div>
        <button onClick={loadData} style={{ ...btnDefault, alignSelf: "flex-end" }}>
          ↻ Aktualisieren
        </button>
        <span style={{ fontSize: 13, color: "#888", alignSelf: "flex-end" }}>
          {total} Jobs total, Seite {page}/{pages || 1}
        </span>
      </div>

      {error && <ErrorState message={error} onRetry={loadData} />}

      {loading ? (
        <LoadingState message="Jobs werden geladen..." />
      ) : jobs.length === 0 ? (
        <EmptyState icon="⚙️" message="Keine Jobs gefunden." />
      ) : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #e0e0e0" }}>
              <thead>
                <tr style={{ backgroundColor: "#f5f5f5" }}>
                  <th style={thStyle}>ID</th>
                  <th style={thStyle}>Typ</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Versuche</th>
                  <th style={thStyle}>Erstellt</th>
                  <th style={thStyle}>Gestartet</th>
                  <th style={thStyle}>Beendet</th>
                  <th style={thStyle}>Ergebnis / Fehler</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td style={tdStyle}>
                      <span title={job.uuid} style={{ fontSize: 12, fontFamily: "monospace" }}>#{job.id}</span>
                    </td>
                    <td style={tdStyle}><code style={{ fontSize: 12 }}>{job.job_type}</code></td>
                    <td style={tdStyle}><StatusBadge status={job.status} size="sm" /></td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>{job.attempts}/{job.max_attempts}</td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>{formatDate(job.created_at)}</td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>{formatDate(job.started_at)}</td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>{formatDate(job.finished_at)}</td>
                    <td style={{ ...tdStyle, fontSize: 12, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {job.error ? (
                        <span style={{ color: "#d32f2f" }} title={job.error}>
                          {job.error.substring(0, 80)}{job.error.length > 80 ? "..." : ""}
                        </span>
                      ) : job.result ? (
                        <span style={{ color: "#4caf50" }} title={job.result}>
                          {job.result.substring(0, 80)}{job.result.length > 80 ? "..." : ""}
                        </span>
                      ) : (
                        <span style={{ color: "#999" }}>-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={btnDefault}>Prev</button>
              <span style={{ padding: "8px 12px" }}>Seite {page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => setPage(p => p + 1)} style={btnDefault}>Next</button>
            </div>
          )}
        </>
      )}
    </PageLayout>
  );
}

function MiniCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ ...cardStyle, textAlign: "center", padding: "10px 18px", minWidth: 80 }}>
      <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || "#333" }}>{value}</div>
    </div>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("de-CH", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" });
  } catch { return iso; }
}
