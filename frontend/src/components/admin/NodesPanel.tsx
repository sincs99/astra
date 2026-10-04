import { Link } from "react-router-dom";
import { StatusBadge } from "../ui/StatusBadge";
import { formatMemory } from "../../lib/dashboard";
import { nodeBar, plural, type NodeBar } from "../../lib/adminOverview";
import { dateLocale, t } from "../../i18n";
import type { AgentMonitoringEntry } from "../../services/api";

function Bar({ bar, noData }: { bar: NodeBar; noData: boolean }) {
  const locale = dateLocale();
  if (bar.capacity <= 0) {
    return (
      <div className="kv"><span>{bar.label}</span><span className="mono" style={{ color: "var(--text-3)" }}>{t("aover.noLimit")}</span></div>
    );
  }
  const pct = bar.percent ?? 0;
  const tone = pct > 100 ? "danger" : pct >= 80 ? "warn" : "";
  // Überbucht: mehr vergeben als nominal vorhanden -> der Überschuss wird schraffiert
  const solid = bar.overbooked && bar.used > 0 ? Math.min(100, (bar.nominal / bar.used) * Math.min(pct, 100)) : Math.min(pct, 100);
  const hatched = bar.overbooked ? Math.min(100, pct) - solid : 0;
  return (
    <>
      <div className="kv">
        <span>{bar.label}</span>
        <span className={`mono${tone ? ` text-${tone}` : ""}`}>
          {formatMemory(bar.used, locale)} / {formatMemory(bar.capacity, locale)}{bar.overbooked ? ` · ${t("aover.overbooked")}` : ""}
        </span>
      </div>
      <div className={`bar${tone ? ` bar-${tone}` : ""} bar-stack${noData ? " bar-nodata" : ""}`} role="progressbar"
        aria-label={`${bar.label} ${pct} %`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(pct, 100)}>
        <span style={{ width: `${solid}%`, background: tone === "danger" ? "var(--danger)" : tone === "warn" ? "var(--warn)" : "var(--accent)" }} />
        {hatched > 0 && <span className="bar-hatch" style={{ width: `${hatched}%` }} />}
      </div>
    </>
  );
}

export function NodesPanel({ agents }: { agents: AgentMonitoringEntry[] | null }) {
  return (
    <section className="panel" aria-labelledby="nodes-title">
      <div className="panel-head">
        <h2 id="nodes-title">{t("aover.nodesTitle")}</h2>
        <Link to="/admin/agents/monitoring" style={{ fontSize: 13, textDecoration: "none" }}>{t("aover.allNodes")}</Link>
      </div>
      <div className="panel-body">
        {!agents ? (
          <p className="hint">{t("aover.loading")}</p>
        ) : agents.filter((a) => a.is_active).length === 0 ? (
          <p className="hint">{t("aover.noActiveNodes")} <Link to="/admin/agents">{t("aover.createNode")}</Link></p>
        ) : agents.filter((a) => a.is_active).map((a) => {
          const unreachable = a.health_status === "unreachable";
          return (
            <div key={a.id} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span className="mono" style={{ fontWeight: 500 }}>{a.name}</span>
                <StatusBadge status={a.maintenance_mode ? "maintenance" : a.health_status} />
                <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--text-3)" }}>{plural(a.instance_count, "aover.instancesCountOne", "aover.instancesCountOther")}</span>
              </div>
              <Bar noData={unreachable} bar={nodeBar(t("aover.ram"), a.utilization.used_memory_mb, a.capacity.memory_total_mb, a.capacity.effective_memory_mb)} />
              <Bar noData={unreachable} bar={nodeBar(t("aover.disk"), a.utilization.used_disk_mb, a.capacity.disk_total_mb, a.capacity.effective_disk_mb)} />
            </div>
          );
        })}
      </div>
    </section>
  );
}
