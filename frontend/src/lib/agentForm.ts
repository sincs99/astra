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
  isActive: boolean;
  /** Solange false, folgt der Connect-Port automatisch dem Listen-Port */
  connectTouched: boolean;
}

export const EMPTY_AGENT_FORM: AgentFormValues = {
  name: "", fqdn: "", scheme: "https", behindProxy: false,
  connect: "8080", listen: "8080", sftp: "2022",
  base: "/var/lib/pterodactyl/volumes", uploadSize: "100",
  isActive: true, connectTouched: false,
};

export function agentToForm(a: Agent): AgentFormValues {
  return {
    name: a.name, fqdn: a.fqdn, scheme: a.scheme, behindProxy: a.behind_proxy,
    connect: String(a.daemon_connect), listen: String(a.daemon_listen), sftp: String(a.daemon_sftp),
    base: a.daemon_base, uploadSize: String(a.upload_size), isActive: a.is_active,
    connectTouched: true,
  };
}

export function validPort(value: string): number | null {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 65535 ? n : null;
}

/** Liefert den API-Payload oder eine Fehlermeldung (string). */
export function toAgentPayload(v: AgentFormValues): AgentUpdate | string {
  if (!v.name.trim() || !v.fqdn.trim()) return "Name und FQDN sind erforderlich.";
  const connect = validPort(v.connect);
  const listen = validPort(v.listen);
  const sftp = validPort(v.sftp);
  if (connect === null) return "Connect-Port muss zwischen 1 und 65535 liegen.";
  if (listen === null) return "Listen-Port muss zwischen 1 und 65535 liegen.";
  if (sftp === null) return "SFTP-Port muss zwischen 1 und 65535 liegen.";
  const upload = Number(v.uploadSize);
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
  };
}
