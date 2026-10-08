import { StatusBadge } from "../ui/StatusBadge";
import { formatMemory } from "../../lib/dashboard";
import { dateLocale, t } from "../../i18n";
import type { AgentMonitoringEntry } from "../../services/api";

type DaemonProps = Pick<AgentMonitoringEntry, "daemon_reachable" | "daemon_version" | "daemon_error">;

/** Wings-Erreichbarkeit als Badge plus Version; ohne Daemon-Prüfung des Backends wird nichts angezeigt. */
export function DaemonInfo({ daemon_reachable, daemon_version, daemon_error }: DaemonProps) {
  if (daemon_reachable === undefined || daemon_reachable === null) return null;
  return (
    <>
      <span title={!daemon_reachable && daemon_error ? daemon_error : undefined}>
        <StatusBadge status={daemon_reachable ? "ok" : "failed"} label={daemon_reachable ? t("aagents.wingsOk") : t("aagents.wingsDown")} size="sm" />
      </span>
      {daemon_version && <span className="hint">{t("aagents.wingsVersion", { version: daemon_version })}</span>}
    </>
  );
}

function fmt(value: number, unit: string): string {
  return unit === "MB" ? formatMemory(value, dateLocale()) : `${value} ${unit}`;
}

/** Auslastungsbalken (.bar): ab 80 % --warn, über 100 % --danger; ohne Kapazität "kein Limit". */
export function LoadBar({ label, used, total, percent, unit, showLabel = false, capacityRequired = false }: {
  label: string; used: number; total: number; percent: number; unit: string; showLabel?: boolean;
  /** Memory/Disk brauchen eine hinterlegte Kapazität: bei 0 steht ein klarer Hinweis statt "0 %" ("kein Limit" gilt nur für CPU) */
  capacityRequired?: boolean;
}) {
  if (total <= 0) {
    const text = capacityRequired
      ? (used > 0 ? t("aagents.capacityMissingUsed", { used: fmt(used, unit) }) : t("aagents.capacityMissing"))
      : (used > 0 ? t("aagents.noLimitUsed", { used: fmt(used, unit) }) : t("aagents.noLimit"));
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 120 }}>
        {showLabel && <span className="hint">{label}</span>}
        <span className={capacityRequired ? "hint text-warn" : "hint"}>{text}</span>
      </div>
    );
  }
  const pct = Math.round(percent);
  const tone = pct > 100 ? "danger" : pct >= 80 ? "warn" : "";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 120 }}>
      {showLabel && <span className="hint">{label}</span>}
      <div className={`bar${tone ? ` bar-${tone}` : ""}`} role="progressbar" aria-label={t("aagents.barAria", { label, pct })}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(pct, 100)}>
        <span style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className={`mono${tone ? ` text-${tone}` : ""}`} style={{ fontSize: "var(--fs-hint)" }}>
        {fmt(used, unit)} / {fmt(total, unit)} ({pct} %)
      </span>
    </div>
  );
}
