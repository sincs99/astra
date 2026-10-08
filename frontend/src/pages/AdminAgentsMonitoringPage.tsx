import { useAutoRefresh, useAutoRefreshSetting } from "../hooks/useAutoRefresh";
import { useEffect, useState, useMemo } from "react";
import { api, type AgentMonitoringEntry, type FleetSummary } from "../services/api";
import { DaemonInfo, LoadBar } from "../components/admin/AgentParts";
import { PageLayout, AutoRefreshToggle, StatusBadge, ConfirmButton, ScrollRegion } from "../components/ui";
import { Icon } from "../components/ui/Icon";
import { formatTimeAgo } from "../lib/dates";
import { formatMemory } from "../lib/dashboard";
import { dateLocale, t } from "../i18n";

type HealthFilter = "" | "healthy" | "stale" | "degraded" | "unreachable";
type SortKey = "name" | "last_seen_at" | "memory" | "disk" | "cpu" | "instances";

export function AdminAgentsMonitoringPage() {
  const [agents, setAgents] = useState<AgentMonitoringEntry[]>([]);
  const [summary, setSummary] = useState<FleetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [healthFilter, setHealthFilter] = useState<HealthFilter>("");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortAsc, setSortAsc] = useState(true);

  const [autoRefresh, setAutoRefresh] = useAutoRefreshSetting("monitoring");

  const loadData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      if (!silent) setError(null);
      const [agentData, summaryData] = await Promise.all([
        api.getAgentsMonitoring({ health: healthFilter || undefined, search: search.trim() || undefined }),
        api.getFleetSummary(),
      ]);
      setAgents(agentData);
      setSummary(summaryData);
    } catch (err) {
      // Bei stillem Refresh vorhandene Daten nicht durch Fehler ersetzen
      if (!silent) setError(err instanceof Error ? err.message : t("aagents.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, [healthFilter]);

  useAutoRefresh(() => loadData(true), 15000, autoRefresh);

  useEffect(() => {
    const timer = setTimeout(() => { loadData(); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const sortedAgents = useMemo(() => {
    return [...agents].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "name": cmp = a.name.localeCompare(b.name); break;
        case "last_seen_at": cmp = (a.last_seen_at || "").localeCompare(b.last_seen_at || ""); break;
        case "memory": cmp = a.utilization.memory_utilization - b.utilization.memory_utilization; break;
        case "disk": cmp = a.utilization.disk_utilization - b.utilization.disk_utilization; break;
        case "cpu": cmp = a.utilization.cpu_utilization - b.utilization.cpu_utilization; break;
        case "instances": cmp = a.instance_count - b.instance_count; break;
      }
      return sortAsc ? cmp : -cmp;
    });
  }, [agents, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const sortTh = (key: SortKey, label: string) => (
    <th scope="col" aria-sort={sortKey === key ? (sortAsc ? "ascending" : "descending") : "none"}>
      <button type="button" className="btn-ghost" onClick={() => toggleSort(key)} aria-label={t("aagents.m.sortAria", { col: label })}
        style={{ font: "inherit", color: "inherit", background: "transparent", border: 0, padding: 0, cursor: "pointer", display: "inline-flex", gap: 4, alignItems: "center" }}>
        {label}
        <span aria-hidden="true">{sortKey === key ? (sortAsc ? "▲" : "▼") : ""}</span>
      </button>
    </th>
  );

  const [actionError, setActionError] = useState<string | null>(null);

  return (
    <PageLayout title={t("aagents.m.title")} subtitle={t("aagents.m.subtitle")}
      actions={<AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} intervalSeconds={15} />}>
      <div className="stack">
        {summary && <FleetSummaryTiles summary={summary} />}

        {/* Filter & Suche */}
        <div className="card" style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field">
            <label htmlFor="mon-filter">{t("aagents.m.filter")}</label>
            <select id="mon-filter" className="inp" value={healthFilter} onChange={e => setHealthFilter(e.target.value as HealthFilter)}>
              <option value="">{t("aagents.m.filterAll")}</option>
              <option value="healthy">{t("status.healthy")}</option>
              <option value="stale">{t("status.stale")}</option>
              <option value="degraded">{t("status.degraded")}</option>
              <option value="unreachable">{t("status.unreachable")}</option>
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 220px" }}>
            <label htmlFor="mon-search">{t("aagents.m.search")}</label>
            <input id="mon-search" className="inp" type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder={t("aagents.m.searchPh")} />
          </div>
          <button type="button" className="btn" onClick={() => loadData()}>
            <Icon name="restart" size={14} />{t("aagents.m.refresh")}
          </button>
        </div>

        {error && (
          <div className="banner banner-danger" role="alert">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text"><strong>{t("aagents.m.errorTitle")}:</strong> {error}</span>
            <button type="button" className="btn btn-sm" onClick={() => loadData()}>{t("aagents.retry")}</button>
          </div>
        )}
        {actionError && (
          <div className="banner banner-danger" role="alert">
            <span className="dot dot-danger" aria-hidden="true" />
            <span className="banner-text">{actionError}</span>
          </div>
        )}

        {/* Agent-Tabelle */}
        {loading ? (
          <p className="hint" role="status">{t("aagents.m.loading")}</p>
        ) : sortedAgents.length === 0 ? (
          !error && <div className="card-empty">{t("aagents.m.empty")}</div>
        ) : (
          <section className="panel">
            <ScrollRegion label={t("aagents.m.tableAria")}>
              <table className="tbl tbl-cards">
                <thead>
                  <tr>
                    {sortTh("name", t("aagents.m.colAgent"))}
                    <th scope="col">{t("aagents.m.colStatus")}</th>
                    {sortTh("last_seen_at", t("aagents.m.colSeen"))}
                    {sortTh("instances", t("aagents.m.colInstances"))}
                    {sortTh("memory", t("aagents.m.colMemory"))}
                    {sortTh("disk", t("aagents.m.colDisk"))}
                    {sortTh("cpu", t("aagents.m.colCpu"))}
                    <th scope="col">{t("aagents.m.colEndpoints")}</th>
                    <th scope="col">{t("aagents.m.colMaintenance")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedAgents.map(agent => (
                    <AgentRow key={agent.id} agent={agent} onRefresh={() => loadData(true)} onError={setActionError} />
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </section>
        )}
      </div>
    </PageLayout>
  );
}

// ── Fleet Summary ────────────────────────────────────────

function FleetSummaryTiles({ summary }: { summary: FleetSummary }) {
  const loc = dateLocale();
  const tone = (p: number) => (p > 100 ? " text-danger" : p >= 80 ? " text-warn" : "");
  return (
    <div className="tiles" role="group" aria-label={t("aagents.m.sum.aria")}>
      <div className="tile">
        <span className="lbl">{t("aagents.m.sum.agents")}</span>
        <span className="big">{summary.total_agents}</span>
        <div className="legend">
          <span><span className="dot dot-ok" aria-hidden="true" />{summary.healthy_agents} {t("aagents.m.sum.healthy")}</span>
          <span><span className="dot dot-warn" aria-hidden="true" />{summary.stale_agents} {t("aagents.m.sum.stale")}</span>
          <span><span className="dot dot-danger" aria-hidden="true" />{summary.degraded_agents} {t("aagents.m.sum.degraded")}</span>
          <span>{summary.unreachable_agents} {t("aagents.m.sum.unreachable")}</span>
        </div>
      </div>
      <div className="tile">
        <span className="lbl">{t("aagents.m.sum.instances")}</span>
        <span className="big">{summary.total_instances}</span>
      </div>
      <div className="tile">
        <span className="lbl">{t("aagents.memory")}</span>
        <span className={`big${tone(summary.memory_utilization)}`}>{summary.memory_utilization} %</span>
        <span className="sub mono">{formatMemory(summary.used_memory_mb, loc)} / {formatMemory(summary.total_memory_mb, loc)}</span>
      </div>
      <div className="tile">
        <span className="lbl">{t("aagents.disk")}</span>
        <span className={`big${tone(summary.disk_utilization)}`}>{summary.disk_utilization} %</span>
        <span className="sub mono">{formatMemory(summary.used_disk_mb, loc)} / {formatMemory(summary.total_disk_mb, loc)}</span>
      </div>
      <div className="tile">
        <span className="lbl">{t("aagents.cpu")}</span>
        <span className={`big${tone(summary.cpu_utilization)}`}>{summary.cpu_utilization} %</span>
        <span className="sub mono">{summary.used_cpu_percent} % / {summary.total_cpu_percent} %</span>
      </div>
      <div className="tile">
        <span className="lbl">{t("aagents.m.sum.endpoints")}</span>
        <span className="big">{summary.assigned_endpoints}</span>
        <span className="sub">{t("aagents.m.sum.endpointsDetail", { total: summary.total_endpoints })}</span>
      </div>
    </div>
  );
}

// ── Agent Row ────────────────────────────────────────────

function AgentRow({ agent, onRefresh, onError }: { agent: AgentMonitoringEntry; onRefresh: () => void; onError: (m: string | null) => void }) {
  const u = agent.utilization;
  const c = agent.capacity;
  const ep = agent.endpoint_summary;

  return (
    <tr>
      <td data-label={t("aagents.m.colAgent")}>
        <div>
          <strong>{agent.name}</strong>
          <div className="hint mono">{agent.fqdn}</div>
        </div>
      </td>
      <td data-label={t("aagents.m.colStatus")}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
          <StatusBadge status={agent.health_status} size="sm" />
          <DaemonInfo {...agent} />
        </div>
      </td>
      <td data-label={t("aagents.m.colSeen")}>
        {agent.last_seen_at ? (
          <span title={agent.last_seen_at}>{formatTimeAgo(agent.last_seen_at)}</span>
        ) : (
          <span className="hint">{t("aagents.m.never")}</span>
        )}
      </td>
      <td data-label={t("aagents.m.colInstances")}>{agent.instance_count}</td>
      <td data-label={t("aagents.m.colMemory")}>
        <LoadBar label={t("aagents.memory")} used={u.used_memory_mb} total={c.effective_memory_mb} percent={u.memory_utilization} unit="MB" capacityRequired />
      </td>
      <td data-label={t("aagents.m.colDisk")}>
        <LoadBar label={t("aagents.disk")} used={u.used_disk_mb} total={c.effective_disk_mb} percent={u.disk_utilization} unit="MB" capacityRequired />
      </td>
      <td data-label={t("aagents.m.colCpu")}>
        <LoadBar label={t("aagents.cpu")} used={u.used_cpu_percent} total={c.effective_cpu_percent} percent={u.cpu_utilization} unit="%" />
      </td>
      <td data-label={t("aagents.m.colEndpoints")}>
        {ep.total > 0 ? (
          <span className="mono">{ep.assigned}/{ep.total}{ep.locked > 0 && <span className="hint"> ({ep.locked} {t("aagents.m.locked")})</span>}</span>
        ) : (
          <span className="hint">{t("aagents.dash")}</span>
        )}
      </td>
      <td data-label={t("aagents.m.colMaintenance")}>
        <MaintenanceToggle agent={agent} onRefresh={onRefresh} onError={onError} />
      </td>
    </tr>
  );
}

// ── Maintenance Toggle ────────────────────────────────────

function MaintenanceToggle({ agent, onRefresh, onError }: { agent: AgentMonitoringEntry; onRefresh: () => void; onError: (m: string | null) => void }) {
  const handleToggle = async () => {
    onError(null);
    try {
      if (agent.maintenance_mode) {
        await api.disableAgentMaintenance(agent.id);
      } else {
        const reason = prompt(t("aagents.m.maint.reason"));
        await api.enableAgentMaintenance(agent.id, reason ? { reason } : {});
      }
      onRefresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : t("aagents.m.maint.failed"));
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
      {agent.maintenance_mode && <StatusBadge status="maintenance" size="sm" />}
      {agent.maintenance_reason && (
        <div className="hint" title={agent.maintenance_reason}>{agent.maintenance_reason.substring(0, 30)}</div>
      )}
      <ConfirmButton
        label={agent.maintenance_mode ? t("aagents.m.maint.disable") : t("aagents.m.maint.enable")}
        confirmMessage={agent.maintenance_mode
          ? t("aagents.m.maint.disableConfirm", { name: agent.name })
          : t("aagents.m.maint.enableConfirm", { name: agent.name })}
        onConfirm={handleToggle}
        size="sm"
      />
    </div>
  );
}
