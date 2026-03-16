import { useEffect, useState, useMemo } from "react";
import {
  api,
  type AgentMonitoringEntry,
  type FleetSummary,
} from "../services/api";

type HealthFilter = "" | "healthy" | "stale" | "degraded" | "unreachable";
type SortKey = "name" | "last_seen_at" | "memory" | "disk" | "cpu" | "instances";

export function AdminAgentsMonitoringPage() {
  const [agents, setAgents] = useState<AgentMonitoringEntry[]>([]);
  const [summary, setSummary] = useState<FleetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Suche
  const [healthFilter, setHealthFilter] = useState<HealthFilter>("");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [agentData, summaryData] = await Promise.all([
        api.getAgentsMonitoring({
          health: healthFilter || undefined,
          search: search.trim() || undefined,
        }),
        api.getFleetSummary(),
      ]);
      setAgents(agentData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [healthFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      loadData();
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Sortierung client-seitig
  const sortedAgents = useMemo(() => {
    const sorted = [...agents].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "last_seen_at":
          cmp = (a.last_seen_at || "").localeCompare(b.last_seen_at || "");
          break;
        case "memory":
          cmp = a.utilization.memory_utilization - b.utilization.memory_utilization;
          break;
        case "disk":
          cmp = a.utilization.disk_utilization - b.utilization.disk_utilization;
          break;
        case "cpu":
          cmp = a.utilization.cpu_utilization - b.utilization.cpu_utilization;
          break;
        case "instances":
          cmp = a.instance_count - b.instance_count;
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
    return sorted;
  }, [agents, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const sortIndicator = (key: SortKey) =>
    sortKey === key ? (sortAsc ? " ▲" : " ▼") : "";

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 24 }}>
      <h1>🖥️ Fleet Monitoring</h1>

      {/* ── Fleet Summary Kacheln ──────────────────────── */}
      {summary && <FleetSummaryCards summary={summary} />}

      {/* ── Filter & Suche ─────────────────────────────── */}
      <div style={{ ...cardStyle, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <label style={labelStyle}>Status-Filter</label>
          <select
            value={healthFilter}
            onChange={(e) => setHealthFilter(e.target.value as HealthFilter)}
            style={inputStyle}
          >
            <option value="">Alle</option>
            <option value="healthy">🟢 Healthy</option>
            <option value="stale">🟡 Stale</option>
            <option value="degraded">🔴 Degraded</option>
            <option value="unreachable">⚫ Unreachable</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Suche (Name / FQDN)</label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="z.B. node01 oder astra.dev"
            style={{ ...inputStyle, width: "100%" }}
          />
        </div>
        <button onClick={loadData} style={{ ...btnStyle, alignSelf: "flex-end" }}>
          ↻ Aktualisieren
        </button>
      </div>

      {/* ── Fehleranzeige ──────────────────────────────── */}
      {error && <div style={errorStyle}>{error}</div>}

      {/* ── Agent-Tabelle ──────────────────────────────── */}
      {loading ? (
        <p>Wird geladen...</p>
      ) : sortedAgents.length === 0 ? (
        <p style={{ color: "#888" }}>Keine Agents gefunden.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
            <thead>
              <tr>
                <th style={thStyle} onClick={() => toggleSort("name")}>
                  Agent{sortIndicator("name")}
                </th>
                <th style={thStyle}>Status</th>
                <th style={thStyle} onClick={() => toggleSort("last_seen_at")}>
                  Zuletzt gesehen{sortIndicator("last_seen_at")}
                </th>
                <th style={thStyle} onClick={() => toggleSort("instances")}>
                  Instances{sortIndicator("instances")}
                </th>
                <th style={thStyle} onClick={() => toggleSort("memory")}>
                  Memory{sortIndicator("memory")}
                </th>
                <th style={thStyle} onClick={() => toggleSort("disk")}>
                  Disk{sortIndicator("disk")}
                </th>
                <th style={thStyle} onClick={() => toggleSort("cpu")}>
                  CPU{sortIndicator("cpu")}
                </th>
                <th style={thStyle}>Endpoints</th>
                <th style={thStyle}>Maintenance</th>
              </tr>
            </thead>
            <tbody>
              {sortedAgents.map((agent) => (
                <AgentRow key={agent.id} agent={agent} onRefresh={loadData} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Navigation ─────────────────────────────────── */}
      <div style={{ marginTop: 32, paddingTop: 16, borderTop: "1px solid #eee" }}>
        <a href="/admin/agents" style={linkStyle}>← Zurück zu Agents</a>
        <a href="/" style={{ ...linkStyle, marginLeft: 16 }}>Dashboard</a>
      </div>
    </div>
  );
}

// ── Fleet Summary Cards ──────────────────────────────────

function FleetSummaryCards({ summary }: { summary: FleetSummary }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 }}>
      <SummaryCard
        label="Agents"
        value={summary.total_agents}
        detail={`🟢 ${summary.healthy_agents} · 🟡 ${summary.stale_agents} · 🔴 ${summary.degraded_agents} · ⚫ ${summary.unreachable_agents}`}
      />
      <SummaryCard
        label="Instances"
        value={summary.total_instances}
      />
      <SummaryCard
        label="Memory"
        value={`${summary.memory_utilization}%`}
        detail={`${formatMB(summary.used_memory_mb)} / ${formatMB(summary.total_memory_mb)}`}
        color={utilizationColor(summary.memory_utilization)}
      />
      <SummaryCard
        label="Disk"
        value={`${summary.disk_utilization}%`}
        detail={`${formatMB(summary.used_disk_mb)} / ${formatMB(summary.total_disk_mb)}`}
        color={utilizationColor(summary.disk_utilization)}
      />
      <SummaryCard
        label="CPU"
        value={`${summary.cpu_utilization}%`}
        detail={`${summary.used_cpu_percent}% / ${summary.total_cpu_percent}%`}
        color={utilizationColor(summary.cpu_utilization)}
      />
      <SummaryCard
        label="Endpoints"
        value={summary.assigned_endpoints}
        detail={`von ${summary.total_endpoints} belegt`}
      />
    </div>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  color,
}: {
  label: string;
  value: string | number;
  detail?: string;
  color?: string;
}) {
  return (
    <div style={{ ...cardStyle, textAlign: "center", padding: 14 }}>
      <div style={{ fontSize: 12, color: "#888", textTransform: "uppercase", fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || "#333", marginTop: 4 }}>
        {value}
      </div>
      {detail && (
        <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>{detail}</div>
      )}
    </div>
  );
}

// ── Agent Row ────────────────────────────────────────────

function AgentRow({ agent, onRefresh }: { agent: AgentMonitoringEntry; onRefresh: () => void }) {
  const u = agent.utilization;
  const c = agent.capacity;
  const ep = agent.endpoint_summary;

  return (
    <tr style={{ borderBottom: "1px solid #eee" }}>
      {/* Name + FQDN */}
      <td style={tdStyle}>
        <div>
          <strong>{agent.name}</strong>
          <div style={{ fontSize: 11, color: "#888" }}>{agent.fqdn}</div>
        </div>
      </td>

      {/* Health Status */}
      <td style={tdStyle}>
        <HealthBadge status={agent.health_status} />
      </td>

      {/* Last Seen */}
      <td style={tdStyle}>
        {agent.last_seen_at ? (
          <span title={agent.last_seen_at}>
            {formatTimeAgo(agent.last_seen_at)}
          </span>
        ) : (
          <span style={{ color: "#999" }}>nie</span>
        )}
      </td>

      {/* Instances */}
      <td style={{ ...tdStyle, textAlign: "center" }}>
        {agent.instance_count}
      </td>

      {/* Memory */}
      <td style={tdStyle}>
        <UtilizationBar
          used={u.used_memory_mb}
          total={c.effective_memory_mb}
          percent={u.memory_utilization}
          unit="MB"
        />
      </td>

      {/* Disk */}
      <td style={tdStyle}>
        <UtilizationBar
          used={u.used_disk_mb}
          total={c.effective_disk_mb}
          percent={u.disk_utilization}
          unit="MB"
        />
      </td>

      {/* CPU */}
      <td style={tdStyle}>
        <UtilizationBar
          used={u.used_cpu_percent}
          total={c.effective_cpu_percent}
          percent={u.cpu_utilization}
          unit="%"
        />
      </td>

      {/* Endpoints */}
      <td style={{ ...tdStyle, fontSize: 12 }}>
        {ep.total > 0 ? (
          <span>
            {ep.assigned}/{ep.total}
            {ep.locked > 0 && <span style={{ color: "#999" }}> (🔒{ep.locked})</span>}
          </span>
        ) : (
          <span style={{ color: "#999" }}>-</span>
        )}
      </td>

      {/* Maintenance (M25) */}
      <td style={{ ...tdStyle, textAlign: "center" }}>
        <MaintenanceToggle agent={agent} onRefresh={onRefresh} />
      </td>
    </tr>
  );
}

// ── Maintenance Toggle (M25) ─────────────────────────────

function MaintenanceToggle({ agent, onRefresh }: { agent: AgentMonitoringEntry; onRefresh: () => void }) {
  const [toggling, setToggling] = useState(false);

  const handleToggle = async () => {
    const action = agent.maintenance_mode ? "deaktivieren" : "aktivieren";
    if (!confirm(`Maintenance fuer "${agent.name}" ${action}?`)) return;

    setToggling(true);
    try {
      if (agent.maintenance_mode) {
        await api.disableAgentMaintenance(agent.id);
      } else {
        const reason = prompt("Grund (optional):");
        await api.enableAgentMaintenance(agent.id, reason ? { reason } : {});
      }
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Fehler");
    } finally {
      setToggling(false);
    }
  };

  return (
    <div>
      {agent.maintenance_mode ? (
        <span style={{
          display: "inline-block", padding: "2px 8px", borderRadius: 10,
          fontSize: 11, fontWeight: 600, backgroundColor: "#fff3e0", color: "#e65100",
        }}>
          MAINTENANCE
        </span>
      ) : null}
      {agent.maintenance_reason && (
        <div style={{ fontSize: 10, color: "#888", marginTop: 2 }} title={agent.maintenance_reason}>
          {agent.maintenance_reason.substring(0, 30)}
        </div>
      )}
      <button
        onClick={handleToggle}
        disabled={toggling}
        style={{
          marginTop: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer",
          border: "1px solid #ccc", borderRadius: 4, backgroundColor: agent.maintenance_mode ? "#e8f5e9" : "#fff3e0",
        }}
      >
        {toggling ? "..." : agent.maintenance_mode ? "Deaktivieren" : "Aktivieren"}
      </button>
    </div>
  );
}

// ── Health Badge ─────────────────────────────────────────

function HealthBadge({ status }: { status: string }) {
  const config: Record<string, { emoji: string; bg: string; label: string }> = {
    healthy: { emoji: "🟢", bg: "#e6f9e6", label: "Healthy" },
    stale: { emoji: "🟡", bg: "#fff8e1", label: "Stale" },
    degraded: { emoji: "🔴", bg: "#fee", label: "Degraded" },
    unreachable: { emoji: "⚫", bg: "#f0f0f0", label: "Unreachable" },
  };
  const c = config[status] || { emoji: "❓", bg: "#f0f0f0", label: status };

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        backgroundColor: c.bg,
      }}
    >
      {c.emoji} {c.label}
    </span>
  );
}

// ── Utilization Bar ──────────────────────────────────────

function UtilizationBar({
  used,
  total,
  percent,
  unit,
}: {
  used: number;
  total: number;
  percent: number;
  unit: string;
}) {
  if (total <= 0) {
    return <span style={{ color: "#999", fontSize: 12 }}>n/a</span>;
  }

  const color = utilizationColor(percent);

  return (
    <div style={{ minWidth: 100 }}>
      <div
        style={{
          height: 6,
          borderRadius: 3,
          backgroundColor: "#eee",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(percent, 100)}%`,
            height: "100%",
            backgroundColor: color,
            borderRadius: 3,
            transition: "width 0.3s",
          }}
        />
      </div>
      <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
        {formatValue(used, unit)} / {formatValue(total, unit)} ({percent}%)
      </div>
    </div>
  );
}

// ── Hilfsfunktionen ──────────────────────────────────────

function utilizationColor(percent: number): string {
  if (percent >= 90) return "#d32f2f";
  if (percent >= 70) return "#f57c00";
  if (percent >= 50) return "#fbc02d";
  return "#4caf50";
}

function formatMB(mb: number): string {
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb} MB`;
}

function formatValue(val: number, unit: string): string {
  if (unit === "MB") return formatMB(val);
  return `${val}${unit}`;
}

function formatTimeAgo(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000);

    if (diff < 60) return "gerade eben";
    if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
    if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
    return `vor ${Math.floor(diff / 86400)} Tagen`;
  } catch {
    return isoStr;
  }
}

// ── Styles ───────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
};

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontWeight: 600,
  fontSize: 12,
  color: "#666",
};

const inputStyle: React.CSSProperties = {
  padding: 8,
  boxSizing: "border-box",
  borderRadius: 4,
  border: "1px solid #ccc",
};

const btnStyle: React.CSSProperties = {
  padding: "8px 20px",
  cursor: "pointer",
  whiteSpace: "nowrap",
  borderRadius: 4,
  border: "1px solid #ccc",
  backgroundColor: "#f8f8f8",
};

const errorStyle: React.CSSProperties = {
  padding: 12,
  marginBottom: 16,
  backgroundColor: "#fee",
  border: "1px solid #c00",
  borderRadius: 4,
  color: "#c00",
};

const thStyle: React.CSSProperties = {
  padding: 10,
  textAlign: "left",
  borderBottom: "2px solid #ddd",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  userSelect: "none",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: 10,
  verticalAlign: "middle",
};

const linkStyle: React.CSSProperties = {
  color: "#1976d2",
  textDecoration: "none",
  fontWeight: 500,
};
