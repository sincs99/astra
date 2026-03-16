import { useEffect, useState } from "react";
import { api, type JobEntry, type JobSummary } from "../services/api";

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
        api.getJobs({
          status: statusFilter || undefined,
          type: typeFilter || undefined,
          page,
          per_page: 50,
        }),
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

  useEffect(() => {
    loadData();
  }, [statusFilter, typeFilter, page]);

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <h1>Background Jobs</h1>

      {/* Summary */}
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
        <button onClick={loadData} style={{ ...btnStyle, alignSelf: "flex-end" }}>
          Aktualisieren
        </button>
        <span style={{ fontSize: 13, color: "#888", alignSelf: "flex-end" }}>
          {total} Jobs total, Seite {page}/{pages || 1}
        </span>
      </div>

      {error && <div style={errorStyle}>{error}</div>}

      {loading ? (
        <p>Wird geladen...</p>
      ) : jobs.length === 0 ? (
        <p style={{ color: "#888" }}>Keine Jobs gefunden.</p>
      ) : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
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
                  <tr key={job.id} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={tdStyle}>
                      <span title={job.uuid} style={{ fontSize: 12, fontFamily: "monospace" }}>
                        #{job.id}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <code style={{ fontSize: 12 }}>{job.job_type}</code>
                    </td>
                    <td style={tdStyle}>
                      <StatusBadge status={job.status} />
                    </td>
                    <td style={{ ...tdStyle, textAlign: "center" }}>
                      {job.attempts}/{job.max_attempts}
                    </td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>
                      {formatDate(job.created_at)}
                    </td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>
                      {formatDate(job.started_at)}
                    </td>
                    <td style={{ ...tdStyle, fontSize: 12, whiteSpace: "nowrap" }}>
                      {formatDate(job.finished_at)}
                    </td>
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

          {/* Pagination */}
          {pages > 1 && (
            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={btnStyle}>Prev</button>
              <span style={{ padding: "8px 12px" }}>Seite {page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => setPage(p => p + 1)} style={btnStyle}>Next</button>
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 32, paddingTop: 16, borderTop: "1px solid #eee" }}>
        <a href="/" style={linkStyle}>Dashboard</a>
        <a href="/admin/agents/monitoring" style={{ ...linkStyle, marginLeft: 16 }}>Fleet Monitoring</a>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { bg: string; color: string }> = {
    pending: { bg: "#e3f2fd", color: "#1976d2" },
    running: { bg: "#fff3e0", color: "#f57c00" },
    completed: { bg: "#e8f5e9", color: "#4caf50" },
    failed: { bg: "#ffebee", color: "#d32f2f" },
    retrying: { bg: "#f3e5f5", color: "#9c27b0" },
  };
  const c = cfg[status] || { bg: "#f5f5f5", color: "#666" };
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 12,
      fontSize: 12, fontWeight: 600, backgroundColor: c.bg, color: c.color,
    }}>
      {status}
    </span>
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

const cardStyle: React.CSSProperties = { border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 };
const labelStyle: React.CSSProperties = { display: "block", marginBottom: 4, fontWeight: 600, fontSize: 12, color: "#666" };
const inputStyle: React.CSSProperties = { padding: 8, borderRadius: 4, border: "1px solid #ccc" };
const btnStyle: React.CSSProperties = { padding: "8px 16px", cursor: "pointer", borderRadius: 4, border: "1px solid #ccc", backgroundColor: "#f8f8f8" };
const errorStyle: React.CSSProperties = { padding: 12, marginBottom: 16, backgroundColor: "#fee", border: "1px solid #c00", borderRadius: 4, color: "#c00" };
const thStyle: React.CSSProperties = { padding: 10, textAlign: "left", borderBottom: "2px solid #ddd", fontSize: 13, fontWeight: 600, whiteSpace: "nowrap" };
const tdStyle: React.CSSProperties = { padding: 10, verticalAlign: "middle" };
const linkStyle: React.CSSProperties = { color: "#1976d2", textDecoration: "none", fontWeight: 500 };
