import { t } from "../i18n";
import type { Agent, AgentUpdate } from "../services/api";

export interface AgentFormValues {
  name: string;
  fqdn: string;
  scheme: string;
  behindProxy: boolean;
  /** Port, ueber den das Panel Wings erreicht (z.B. 443 hinter Caddy) */
  connect: string;
  /** Port, auf dem Wings lokal lauscht (z.B. 8080) */
  listen: string;
  sftp: string;
  base: string;
  uploadSize: string;
  /** Kapazitaet; 0 = kein Limit */
  memoryTotal: string;
  diskTotal: string;
  cpuTotal: string;
  memoryOveralloc: string;
  diskOveralloc: string;
  cpuOveralloc: string;
  isActive: boolean;
  /** Solange false, folgt der Connect-Port automatisch dem Listen-Port */
  connectTouched: boolean;
}

export const EMPTY_AGENT_FORM: AgentFormValues = {
  name: "", fqdn: "", scheme: "https", behindProxy: false,
  connect: "8080", listen: "8080", sftp: "2022",
  base: "/var/lib/pterodactyl/volumes", uploadSize: "100",
  memoryTotal: "0", diskTotal: "0", cpuTotal: "0",
  memoryOveralloc: "0", diskOveralloc: "0", cpuOveralloc: "0",
  isActive: true, connectTouched: false,
};

export function agentToForm(a: Agent): AgentFormValues {
  return {
    name: a.name, fqdn: a.fqdn, scheme: a.scheme, behindProxy: a.behind_proxy,
    connect: String(a.daemon_connect), listen: String(a.daemon_listen), sftp: String(a.daemon_sftp),
    base: a.daemon_base, uploadSize: String(a.upload_size),
    memoryTotal: String(a.memory_total ?? 0), diskTotal: String(a.disk_total ?? 0), cpuTotal: String(a.cpu_total ?? 0),
    memoryOveralloc: String(a.memory_overalloc ?? 0), diskOveralloc: String(a.disk_overalloc ?? 0), cpuOveralloc: String(a.cpu_overalloc ?? 0), isActive: a.is_active,
    connectTouched: true,
  };
}

export function validPort(value: string): number | null {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 65535 ? n : null;
}

/** Liefert den API-Payload oder eine Fehlermeldung (string). */
export function toAgentPayload(v: AgentFormValues): AgentUpdate | string {
  if (!v.name.trim() || !v.fqdn.trim()) return t("sform.agentNameFqdn");
  const connect = validPort(v.connect);
  const listen = validPort(v.listen);
  const sftp = validPort(v.sftp);
  if (connect === null) return t("sform.agentPort", { field: "Connect-Port" });
  if (listen === null) return t("sform.agentPort", { field: "Listen-Port" });
  if (sftp === null) return t("sform.agentPort", { field: "SFTP-Port" });
  const upload = Number(v.uploadSize);
  const total = (value: string) => { const n = Number(value); return Number.isInteger(n) && n >= 0 ? n : null; };
  const over = (value: string) => { const n = total(value); return n !== null && n <= 1000 ? n : null; };
  const memoryTotal = total(v.memoryTotal);
  const diskTotal = total(v.diskTotal);
  const cpuTotal = total(v.cpuTotal);
  if (memoryTotal === null) return t("sform.agentTotal", { field: "Memory" });
  if (diskTotal === null) return t("sform.agentTotal", { field: "Disk" });
  if (cpuTotal === null) return t("sform.agentTotal", { field: "CPU" });
  const memoryOveralloc = over(v.memoryOveralloc);
  const diskOveralloc = over(v.diskOveralloc);
  const cpuOveralloc = over(v.cpuOveralloc);
  if (memoryOveralloc === null) return t("sform.agentOver", { field: "Memory" });
  if (diskOveralloc === null) return t("sform.agentOver", { field: "Disk" });
  if (cpuOveralloc === null) return t("sform.agentOver", { field: "CPU" });
  return {
    name: v.name.trim(),
    fqdn: v.fqdn.trim(),
    scheme: v.scheme,
    behind_proxy: v.behindProxy,
    daemon_connect: connect,
    daemon_listen: listen,
    daemon_sftp: sftp,
    daemon_base: v.base.trim() || "/var/lib/pterodactyl/volumes",
    upload_size: Number.isFinite(upload) && upload > 0 ? upload : 100,
    is_active: v.isActive,
    memory_total: memoryTotal,
    disk_total: diskTotal,
    cpu_total: cpuTotal,
    memory_overalloc: memoryOveralloc,
    disk_overalloc: diskOveralloc,
    cpu_overalloc: cpuOveralloc,
  };
}
