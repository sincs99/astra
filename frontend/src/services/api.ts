/**
 * Zentraler API-Service fuer Astra.
 *
 * In Entwicklung: Vite-Proxy (/api -> localhost:5000)
 * In Produktion:  VITE_API_BASE_URL oder /api (hinter Nginx)
 */

import { friendlyApiMessage, networkErrorMessage } from "../lib/errors";

/** 401 bedeutet hier "falsches Passwort", nicht "Sitzung abgelaufen". */
const CREDENTIAL_ENDPOINTS = ["/auth/login", "/auth/change-password"];

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const TOKEN_KEY = "astra_access_token";

/**
 * Baut eine Websocket-URL basierend auf der aktuellen Seiten-URL.
 * http: -> ws:, https: -> wss:
 */
export function buildWsUrl(path: string): string {
  const wsBase = import.meta.env.VITE_WS_BASE_URL;
  if (wsBase) {
    return `${wsBase}${path}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

// ── Token-Verwaltung ───────────────────────────────────

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

/** Muss zum Backend passen (MIN_PASSWORD_LENGTH in accounts/service.py). */
export const MIN_PASSWORD_LENGTH = 8;

export function logout() {
  setAccessToken(null);
}

/**
 * Gibt eine simulierte User-ID zurueck (fuer Entwicklung).
 * Liest aus dem gespeicherten Token oder gibt 1 zurueck.
 */
export function getSimulatedUserId(): number {
  try {
    const token = getAccessToken();
    if (token) {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return payload.sub || payload.user_id || 1;
    }
  } catch {
    // Token nicht parsebar
  }
  return 1;
}

// ── Generischer Fetch-Wrapper ──────────────────────────

/** Fehler der API mit HTTP-Status und optionalem Fehlercode (z.B. "email_not_verified"). */
export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
  asText = false,
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // JWT-Token mitsenden wenn vorhanden
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiError(networkErrorMessage(), 0);
  }

  if (!response.ok) {
    // Abgelaufene/ungueltige Session: Token verwerfen und zum Login.
    // Ausgenommen: Endpunkte, die bei falschen Zugangsdaten selbst 401 liefern.
    if (response.status === 401 && !CREDENTIAL_ENDPOINTS.includes(endpoint) && token) {
      logout();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login?expired=1");
      }
    }
    const error = (await response.json().catch(() => ({}))) as Record<string, string>;
    throw new ApiError(
      friendlyApiMessage(response.status, error.error || `Request failed: ${response.status}`),
      response.status,
      error.code,
    );
  }

  return (asText ? await response.text() : await response.json()) as T;
}

// ── SSH-Key-Typen (M28) ────────────────────────────────

export interface SshKeyEntry {
  id: number;
  name: string;
  fingerprint: string;
  public_key: string;
  created_at: string;
}

export interface SshKeyCreateRequest {
  name: string;
  public_key: string;
}

// ── Auth-Typen ─────────────────────────────────────────

export interface LoginRequest {
  login: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  /** Gesetzt, wenn statt eines Authenticator-Codes ein Recovery-Code verwendet wurde (M60) */
  recovery_code_used?: boolean;
  recovery_codes_remaining?: number;
}

/** Antwort von /auth/login bei aktivem MFA, solange noch kein Code mitgeschickt wurde. */
export interface MfaRequiredResponse {
  requires_mfa: true;
  message: string;
}

export type LoginResult = LoginResponse | MfaRequiredResponse;

export interface MfaSetupResult {
  secret: string;
  provisioning_uri: string;
  message: string;
}

export interface MfaEnableResult {
  mfa_enabled: boolean;
  recovery_codes: string[];
  recovery_codes_remaining?: number;
  message: string;
}

export interface RecoveryCodesResult {
  recovery_codes: string[];
  recovery_codes_remaining: number;
  message: string;
}

export interface ApiKeyEntry {
  id: number;
  user_id: number;
  key_type: "account" | "application";
  identifier: string;
  memo: string | null;
  allowed_ips: string[] | null;
  permissions: string[] | null;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string | null;
}

/** Nach dem Anlegen enthaelt die Antwort genau einmal den Klartext-Token. */
export interface ApiKeyCreated extends ApiKeyEntry {
  raw_token: string;
}

/** Bei aktiver E-Mail-Verifizierung gibt es kein Token, sondern nur den Hinweis zur Bestaetigung. */
export type RegisterResponse =
  | LoginResponse
  | { verification_required: true; message: string; user: User };

// ── Phase 4: Produkte & Bestellungen ───────────────────

export interface ProductResources {
  memory: number;
  swap: number;
  disk: number;
  io: number;
  cpu: number;
}

/** Oeffentliche Felder (GET /client/products, ohne Login); Admins bekommen zusaetzlich die internen Felder. */
export interface Product {
  id: number;
  name: string;
  description: string | null;
  price_cents: number;
  currency: string;
  billing_period_days: number;
  resources: ProductResources;
  /** Optional: Name des Blueprints, falls das Backend ihn im oeffentlichen Produkt mitliefert */
  blueprint_name?: string | null;
  /** Nur Admin-Antworten */
  blueprint_id?: number;
  is_active?: boolean;
  max_instances_per_user?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

/** Body fuer POST/PATCH /admin/products: Ressourcen FLACH, nicht als `resources`-Objekt. */
export interface ProductInput {
  name: string;
  description: string | null;
  blueprint_id: number;
  memory: number;
  disk: number;
  cpu: number;
  swap: number;
  io: number;
  price_cents: number;
  currency: string;
  billing_period_days: number;
  is_active: boolean;
  max_instances_per_user: number | null;
}

export type OrderStatus =
  | "pending_payment"
  | "awaiting_provisioning"
  | "active"
  | "past_due"
  | "cancelled"
  | "expired"
  /** Voll erstattet oder Zahlungsstreit verloren (M59): Server gesperrt, nach der Karenzzeit geloescht */
  | "refunded";

export interface OrderConnection {
  host: string | null;
  ip?: string;
  port: number;
  address: string;
}

/** Vereinfachter Zahlungsbeleg (M62), keine Rechnung mit Umsatzsteuer. */
export interface OrderReceipt {
  number: string;
  issued_at: string;
  amount_cents: number;
  currency: string;
}

/** Bestellungen werden ueber `uuid` angesprochen (nicht ueber die numerische id). */
export interface Order {
  id: number;
  uuid: string;
  status: OrderStatus;
  product_id: number;
  product_name: string | null;
  instance_name: string;
  instance_uuid: string | null;
  instance_status: string | null;
  connection: OrderConnection | null;
  /** Schnappschuss zum Bestellzeitpunkt */
  price_cents: number;
  currency: string;
  billing_period_days: number;
  resources: Partial<ProductResources>;
  payment_reference: string | null;
  paid_at: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  /** Zeitpunkt der Sperre wegen ueberfaelliger Zahlung (UTC ohne Zeitzonen-Suffix) */
  past_due_at?: string | null;
  /** Geplante Loeschung: Ende der Karenzzeit bzw. Laufzeitende bei Kuendigung, sonst null */
  scheduled_deletion_at?: string | null;
  cancelled_at: string | null;
  /** Zahlungsbelege, aelteste zuerst; [] ohne Beleg (M62) */
  receipts?: OrderReceipt[];
  /** Zeitpunkt der Erstattung (UTC) bei Status refunded (M59) */
  refunded_at?: string | null;
  /** Zahlungsstreit (Dispute) offen: Server gesperrt, Status bleibt active/past_due (M59) */
  disputed?: boolean;
  created_at: string | null;
  /** Nur Admin-Antworten */
  user_id?: number;
  username?: string | null;
}

// ── Typen ──────────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  email_verified?: boolean;
  mfa_enabled?: boolean;
  /** Noch gueltige Recovery-Codes (0, wenn MFA aus ist) */
  mfa_recovery_codes_remaining?: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface Agent {
  id: number;
  uuid: string | null;
  name: string;
  fqdn: string;
  is_active: boolean;
  scheme: string;
  behind_proxy: boolean;
  daemon_connect: number;
  daemon_listen: number;
  daemon_sftp: number;
  daemon_base: string;
  upload_size: number;
  memory_total: number;
  disk_total: number;
  cpu_total: number;
  memory_overalloc: number;
  disk_overalloc: number;
  cpu_overalloc: number;
  daemon_token_id: string | null;
  has_daemon_credentials: boolean;
  last_seen_at: string | null;
  maintenance_mode: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentCreate {
  name: string;
  fqdn: string;
  scheme?: string;
  behind_proxy?: boolean;
  daemon_connect?: number;
  daemon_listen?: number;
  daemon_sftp?: number;
  daemon_base?: string;
  /** Kapazitaet (0 = kein Limit hinterlegt): Memory/Disk in MB, CPU in % (400 = 4 Kerne), Ueberallokation in % */
  memory_total?: number;
  disk_total?: number;
  cpu_total?: number;
  memory_overalloc?: number;
  disk_overalloc?: number;
  cpu_overalloc?: number;
}

export interface AgentUpdate {
  name?: string;
  fqdn?: string;
  is_active?: boolean;
  scheme?: string;
  behind_proxy?: boolean;
  daemon_connect?: number;
  daemon_listen?: number;
  daemon_sftp?: number;
  daemon_base?: string;
  upload_size?: number;
  /** Kapazitaet (0 = kein Limit hinterlegt): Memory/Disk in MB, CPU in % (400 = 4 Kerne), Ueberallokation in % */
  memory_total?: number;
  disk_total?: number;
  cpu_total?: number;
  memory_overalloc?: number;
  disk_overalloc?: number;
  cpu_overalloc?: number;
}

/** Antwort von GET /admin/agents/{id}/configuration – Inhalt der Wings config.yml */
export interface AgentConfiguration {
  agent_id: number;
  yaml: string;
  config: Record<string, unknown>;
}

export interface BlueprintVariable {
  name: string;
  description: string;
  env_var: string;
  default_value: string;
  user_viewable: boolean;
  user_editable: boolean;
}

/** Startup-Erkennung fuer Wings: Zeilen, bei denen der Server als "running" gilt. */
export interface BlueprintStartupConfig {
  done: string[];
  strip_ansi?: boolean;
}

export interface Blueprint {
  id: number;
  name: string;
  description: string | null;
  docker_image: string | null;
  startup_command: string | null;
  install_script: string | null;
  install_container: string | null;
  install_entrypoint: string | null;
  variables: BlueprintVariable[];
  config_schema: Record<string, unknown> | null;
  config_startup: BlueprintStartupConfig | null;
  config_stop: string | null;
  config_files: Record<string, unknown> | null;
  file_denylist: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface BlueprintCreate {
  name: string;
  description?: string;
  docker_image?: string;
  startup_command?: string;
  install_script?: string;
  install_container?: string;
  install_entrypoint?: string;
  variables?: BlueprintVariable[];
  config_startup?: BlueprintStartupConfig;
  config_stop?: string;
  config_files?: Record<string, unknown>;
  file_denylist?: string[];
}

export interface BlueprintUpdate {
  name?: string;
  description?: string;
  docker_image?: string;
  startup_command?: string;
  install_script?: string;
  install_container?: string;
  install_entrypoint?: string;
  variables?: BlueprintVariable[];
  config_startup?: BlueprintStartupConfig;
  config_stop?: string;
  config_files?: Record<string, unknown>;
  file_denylist?: string[];
}

export interface Endpoint {
  id: number;
  agent_id: number;
  instance_id: number | null;
  ip: string;
  port: number;
  is_locked: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface EndpointCreate {
  ip?: string;
  port: number;
  is_locked?: boolean;
}

export interface Instance {
  id: number;
  uuid: string;
  name: string;
  description: string | null;
  owner_id: number;
  agent_id: number;
  blueprint_id: number;
  primary_endpoint_id: number | null;
  status: string | null;
  container_state: string | null;
  installed_at: string | null;
  memory: number;
  swap: number;
  disk: number;
  io: number;
  cpu: number;
  image: string | null;
  startup_command: string | null;
  variable_values: Record<string, string>;
  suspended_reason: string | null;
  suspended_at: string | null;
  suspended_by_user_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  role?: "owner" | "collaborator" | "none";
  /** Verbindungsadresse (FQDN des Agents + Port des primaeren Endpoints); null ohne Endpoint */
  connection?: InstanceConnection | null;
}

export interface InstanceConnection {
  /** FQDN des Agents; null falls kein Agent geladen */
  host: string | null;
  ip?: string;
  port: number;
  /** SFTP-Port des Agents (optional, falls das Backend ihn mitliefert) */
  sftp_port?: number;
  /** Fertige Adresse, z.B. "node1.example.com:25565" */
  address: string;
}

export interface InstanceCreate {
  name: string;
  owner_id: number;
  /** Weggelassen/null: Astra waehlt automatisch einen Agent mit freiem Endpoint und genug Kapazitaet (M42) */
  agent_id?: number | null;
  blueprint_id: number;
  description?: string;
  endpoint_id?: number;
  memory?: number;
  swap?: number;
  disk?: number;
  io?: number;
  cpu?: number;
  image?: string;
  startup_command?: string;
}

export type PowerSignal = "start" | "stop" | "restart" | "kill";

export interface PowerActionResult {
  action: string;
  message: string;
}

export interface WebsocketCredentials {
  token: string;
  socket: string;
}

export interface ResourceStats {
  cpu_percent: number;
  memory_bytes: number;
  memory_limit_bytes: number;
  disk_bytes: number;
  network_rx_bytes: number;
  network_tx_bytes: number;
  uptime_seconds: number;
  container_status: string;
}

export interface FileEntry {
  name: string;
  path: string;
  is_file: boolean;
  is_directory: boolean;
  size: number;
  modified_at: string | null;
}

export interface FileListResult {
  directory: string;
  entries: FileEntry[];
}

export interface FileContentResult {
  path: string;
  content: string;
  size: number;
}

export interface FileActionResult {
  success: boolean;
  message: string;
}

export interface BackupEntry {
  id: number;
  uuid: string;
  instance_id: number;
  name: string;
  ignored_files: string | null;
  disk: string;
  checksum: string | null;
  bytes: number;
  is_successful: boolean;
  is_locked: boolean;
  completed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CollaboratorEntry {
  id: number;
  user_id: number;
  instance_id: number;
  permissions: string[];
  created_at: string | null;
  updated_at: string | null;
}

export const ALL_PERMISSIONS = [
  "control.console", "control.start", "control.stop", "control.restart",
  "file.read", "file.update", "file.delete",
  "backup.read", "backup.create", "backup.restore", "backup.delete",
];

export interface ActionEntry {
  id: number;
  routine_id: number;
  sequence: number;
  action_type: string;
  payload: Record<string, unknown> | null;
  delay_seconds: number;
  continue_on_failure: boolean;
  is_queued: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface RoutineEntry {
  id: number;
  instance_id: number;
  name: string;
  cron_minute: string;
  cron_hour: string;
  cron_day_month: string;
  cron_month: string;
  cron_day_week: string;
  is_active: boolean;
  is_processing: boolean;
  only_when_online: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  actions: ActionEntry[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ExecutionResult {
  routine: string;
  actions_executed: number;
  failed: boolean;
  results: Array<{ sequence: number; action_type: string; success: boolean; message: string }>;
}

export const ACTION_TYPES = ["send_command", "power_action", "create_backup", "delete_files"];

export interface ActivityLogEntry {
  id: number;
  event: string;
  actor_id: number | null;
  actor_type: string;
  subject_id: number | null;
  subject_type: string | null;
  description: string | null;
  properties: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string | null;
}

export interface WebhookEntry {
  id: number;
  uuid: string;
  endpoint_url: string;
  description: string | null;
  events: string[];
  secret_token: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface WebhookCreate {
  endpoint_url: string;
  events: string[];
  description?: string;
  secret_token?: string;
  is_active?: boolean;
}

export interface WebhookUpdate {
  endpoint_url?: string;
  events?: string[];
  description?: string;
  secret_token?: string;
  is_active?: boolean;
}

export interface WebhookEventInfo {
  event: string;
  description: string;
}

export interface WebhookTestResult {
  success: boolean;
  status_code: number | null;
  message: string;
}

// ── Fleet Monitoring Types (M22) ────────────────────────

export interface CapacitySummary {
  memory_total_mb: number;
  disk_total_mb: number;
  cpu_total_percent: number;
  memory_overalloc_percent: number;
  disk_overalloc_percent: number;
  cpu_overalloc_percent: number;
  effective_memory_mb: number;
  effective_disk_mb: number;
  effective_cpu_percent: number;
}

export interface UtilizationSummary {
  instance_count: number;
  used_memory_mb: number;
  used_disk_mb: number;
  used_cpu_percent: number;
  memory_utilization: number;
  disk_utilization: number;
  cpu_utilization: number;
}

export interface EndpointSummary {
  total: number;
  assigned: number;
  free: number;
  locked: number;
}

export interface AgentMonitoringEntry {
  id: number;
  name: string;
  fqdn: string;
  health_status: "healthy" | "stale" | "degraded" | "unreachable";
  is_active: boolean;
  is_stale: boolean;
  last_seen_at: string | null;
  maintenance_mode: boolean;
  maintenance_reason: string | null;
  maintenance_started_at: string | null;
  available_for_deployment: boolean;
  capacity: CapacitySummary;
  utilization: UtilizationSummary;
  instance_count: number;
  endpoint_summary: EndpointSummary;
  /** Optional: vom Backend, sobald der Daemon aktiv geprueft wird */
  daemon_reachable?: boolean | null;
  daemon_version?: string | null;
  daemon_error?: string | null;
}

export interface FleetSummary {
  total_agents: number;
  healthy_agents: number;
  stale_agents: number;
  degraded_agents: number;
  unreachable_agents: number;
  total_instances: number;
  total_memory_mb: number;
  used_memory_mb: number;
  memory_utilization: number;
  total_disk_mb: number;
  used_disk_mb: number;
  disk_utilization: number;
  total_cpu_percent: number;
  used_cpu_percent: number;
  cpu_utilization: number;
  total_endpoints: number;
  assigned_endpoints: number;
}

// ── Job Types (M23) ─────────────────────────────────────

export interface JobEntry {
  id: number;
  uuid: string;
  job_type: string;
  status: "pending" | "running" | "completed" | "failed" | "retrying";
  attempts: number;
  max_attempts: number;
  payload_summary: Record<string, unknown> | null;
  result: string | null;
  error: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  scheduled_at: string | null;
}

export interface JobListResult {
  items: JobEntry[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface JobSummary {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
}

export interface BillingStatus {
  healthy: boolean;
  /** ISO UTC mit Suffix; null wenn der Tick noch nie lief */
  last_run_at: string | null;
  age_seconds: number | null;
  max_age_minutes: number;
  orders_needing_tick: number;
  orders_by_status: Record<string, number>;
  last_summary: Record<string, unknown> | null;
  /** Bezahlte Bestellungen ohne Instance (warten auf freien Node); fehlt bei aelteren Backends */
  awaiting_provisioning?: {
    count: number;
    oldest_paid_at: string | null;
    oldest_wait_hours: number | null;
    warn_after_hours: number;
    waiting_too_long: boolean;
  };
}

export type PaymentEventStatus = "processed" | "ignored" | "unapplied" | "mismatch" | "received";

export interface PaymentEvent {
  id: number;
  event_id: string;
  provider: string;
  event_type: string;
  order_uuid: string | null;
  status: PaymentEventStatus;
  detail: string | null;
  received_at: string | null;
  processed_at: string | null;
}

// ── System / Version Types (M24) ────────────────────────

export interface SystemVersionInfo {
  version: string;
  release_phase: string;
  build_sha: string | null;
  build_date: string | null;
  build_ref: string | null;
  environment: string;
  service: string;
}

export interface MigrationStatus {
  current_head: string | null;
  applied_revision: string | null;
  is_up_to_date: boolean;
  pending_migrations: number;
  error: string | null;
}

export interface UpgradeStatus {
  version: string;
  build: {
    version: string;
    build_sha: string | null;
    build_date: string | null;
    build_ref: string | null;
  };
  environment: string;
  migration: MigrationStatus;
  upgrade_required: boolean;
}

export interface PreflightResult {
  checks: Record<string, string>;
  issues: string[];
  overall_status: string;
  compatible: boolean;
  timestamp: string;
}

// ── API-Methoden ───────────────────────────────────────

export const api = {
  /**
   * Meldet das aktuelle Token am Server ab (best effort, M61). Fehler werden ignoriert;
   * bewusst ohne request(), damit der 401-Handler den Endpunkt nie erneut aufruft.
   */
  logoutServer: async (): Promise<void> => {
    const token = getAccessToken();
    if (!token) return;
    try {
      await fetch(`${BASE_URL}/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    } catch {
      // Netzwerkproblem: lokal wird trotzdem abgemeldet
    }
  },

  // ── Auth ─────────────────────────────────────────────
  register: (username: string, email: string, password: string) =>
    request<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    }),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  /** `login` darf Benutzername oder E-Mail-Adresse sein. */
  resendVerification: (login: string) =>
    request<{ message: string }>("/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ login }),
    }),

  requestPasswordReset: (email: string) =>
    request<{ message: string }>("/auth/password-reset/request", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  confirmPasswordReset: (token: string, password: string) =>
    request<{ message: string }>("/auth/password-reset/confirm", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  login: (login: string, password: string, mfaCode?: string) =>
    request<LoginResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify(mfaCode ? { login, password, mfa_code: mfaCode } : { login, password }),
    }),

  // ── Konto: Passwort, MFA, API-Keys ───────────────────
  // Nach dem Wechsel sind alle alten Tokens ungültig; die Antwort enthält ein frisches für dieses Gerät
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ message: string; access_token?: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }).then((res) => {
      if (res.access_token) setAccessToken(res.access_token);
      return res;
    }),
  setupMfa: () => request<MfaSetupResult>("/auth/mfa/setup", { method: "POST" }),
  verifyMfa: (code: string) =>
    request<MfaEnableResult>("/auth/mfa/verify", { method: "POST", body: JSON.stringify({ code }) }),
  /** Neue Recovery-Codes erzeugen (alte werden ungueltig); falsches Passwort -> 403 invalid_password. */
  regenerateRecoveryCodes: (password: string) =>
    request<RecoveryCodesResult>("/auth/mfa/recovery-codes", { method: "POST", body: JSON.stringify({ password }) }),
  disableMfa: () => request<{ message: string }>("/auth/mfa/disable", { method: "POST" }),
  getApiKeys: () => request<ApiKeyEntry[]>("/auth/api-keys"),
  createApiKey: (data: { key_type?: "account" | "application"; memo?: string; allowed_ips?: string[] }) =>
    request<ApiKeyCreated>("/auth/api-keys", { method: "POST", body: JSON.stringify(data) }),
  deleteApiKey: (id: number) =>
    request<{ message: string }>(`/auth/api-keys/${id}`, { method: "DELETE" }),

  getCurrentUser: () => request<User>("/auth/me"),

  // ── Admin: Users ─────────────────────────────────────
  getUsers: () => request<User[]>("/admin/users"),

  // ── Admin: Agents ────────────────────────────────────
  getAgents: () => request<Agent[]>("/admin/agents"),
  createAgent: (data: AgentCreate) =>
    request<Agent>("/admin/agents", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateAgent: (agentId: number, data: AgentUpdate) =>
    request<Agent>(`/admin/agents/${agentId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  // M33: Wings config.yml fuer den Node
  getAgentConfiguration: (agentId: number) =>
    request<AgentConfiguration>(`/admin/agents/${agentId}/configuration`),
  // M33: Neue Node-Credentials (token_id + token) erzeugen
  rotateAgentCredentials: (agentId: number) =>
    request<{ message: string; agent: Agent }>(`/admin/agents/${agentId}/rotate-credentials`, {
      method: "POST",
    }),

  // ── Admin: Blueprints ────────────────────────────────
  getBlueprints: () => request<Blueprint[]>("/admin/blueprints"),
  createBlueprint: (data: BlueprintCreate) =>
    request<Blueprint>("/admin/blueprints", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  /** Pterodactyl-Egg-JSON importieren (Body = das Egg selbst). */
  importBlueprint: (egg: Record<string, unknown>) =>
    request<Blueprint>("/admin/blueprints/import", {
      method: "POST",
      body: JSON.stringify(egg),
    }),
  updateBlueprint: (id: number, data: BlueprintUpdate) =>
    request<Blueprint>(`/admin/blueprints/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteBlueprint: (id: number) =>
    request<{ message: string }>(`/admin/blueprints/${id}`, { method: "DELETE" }),

  // ── Admin: Endpoints ─────────────────────────────────
  getEndpoints: () => request<Endpoint[]>("/admin/endpoints"),
  createEndpoint: (agentId: number, data: EndpointCreate) =>
    request<Endpoint>(`/admin/agents/${agentId}/endpoints`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** Port-Bereich als Endpoints anlegen; bereits vorhandene ip:port werden uebersprungen. */
  createEndpointsBulk: (agentId: number, data: { ip?: string; port_start: number; port_end: number }) =>
    request<{ created: number; skipped: number; endpoints: Endpoint[] }>(
      `/admin/agents/${agentId}/endpoints/bulk`,
      { method: "POST", body: JSON.stringify(data) },
    ),

  // ── Admin: Instances ─────────────────────────────────
  getInstances: () => request<Instance[]>("/admin/instances"),
  createInstance: (data: InstanceCreate) =>
    request<Instance>("/admin/instances", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  /** Backups einer Instance fuer Admins (Pruefung vor dem Transfer). */
  getAdminInstanceBackups: (uuid: string) =>
    request<{ backups: BackupEntry[]; successful_count: number; last_successful_backup_at: string | null }>(
      `/admin/instances/${uuid}/backups`,
    ),
  transferInstance: (uuid: string, targetAgentId: number) =>
    request<Instance>(`/admin/instances/${uuid}/transfer`, {
      method: "POST",
      body: JSON.stringify({ target_agent_id: targetAgentId }),
    }),

  // ── Client: Instances ────────────────────────────────
  getClientInstances: () => request<Instance[]>("/client/instances"),
  getClientInstance: (uuid: string) =>
    request<Instance>(`/client/instances/${uuid}`),

  // ── Client: Power ────────────────────────────────────
  sendPowerAction: (uuid: string, signal: PowerSignal) =>
    request<PowerActionResult>(`/client/instances/${uuid}/power`, {
      method: "POST",
      body: JSON.stringify({ signal }),
    }),

  // ── Client: Reinstall / Config / Sync (M16) ─────────
  reinstallInstance: (uuid: string) =>
    request<{ uuid: string; status: string; message: string }>(
      `/client/instances/${uuid}/reinstall`,
      { method: "POST" }
    ),

  updateInstanceBuild: (uuid: string, changes: Record<string, unknown>) =>
    request<{ instance: Instance; synced: boolean; sync_message: string | null; changed_fields: string[] }>(
      `/client/instances/${uuid}/build`,
      { method: "PATCH", body: JSON.stringify(changes) }
    ),

  syncInstance: (uuid: string) =>
    request<{ success: boolean; message: string }>(
      `/client/instances/${uuid}/sync`,
      { method: "POST" }
    ),

  // ── Client: Runtime ──────────────────────────────────
  getWebsocketCredentials: (uuid: string) =>
    request<WebsocketCredentials>(`/client/instances/${uuid}/websocket`),

  getInstanceResources: (uuid: string) =>
    request<ResourceStats>(`/client/instances/${uuid}/resources`),

  // ── Client: Files ────────────────────────────────────
  listFiles: (uuid: string, directory: string = "/") =>
    request<FileListResult>(
      `/client/instances/${uuid}/files?directory=${encodeURIComponent(directory)}`
    ),

  readFile: (uuid: string, path: string) =>
    request<FileContentResult>(
      `/client/instances/${uuid}/files/content?path=${encodeURIComponent(path)}`
    ),

  writeFile: (uuid: string, path: string, content: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/write`, {
      method: "POST",
      body: JSON.stringify({ path, content }),
    }),

  deleteFile: (uuid: string, path: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/delete`, {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  createDirectory: (uuid: string, path: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/create-directory`, {
      method: "POST",
      body: JSON.stringify({ path }),
    }),

  renameFile: (uuid: string, source: string, target: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/rename`, {
      method: "POST",
      body: JSON.stringify({ source, target }),
    }),

  compressFiles: (uuid: string, files: string[], destination: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/compress`, {
      method: "POST",
      body: JSON.stringify({ files, destination }),
    }),

  decompressFile: (uuid: string, file: string, destination: string) =>
    request<FileActionResult>(`/client/instances/${uuid}/files/decompress`, {
      method: "POST",
      body: JSON.stringify({ file, destination }),
    }),

  updateVariableValues: (uuid: string, values: Record<string, string>) =>
    request<{ variable_values: Record<string, string>; rejected: string[] }>(
      `/client/instances/${uuid}/variables`,
      { method: "PATCH", body: JSON.stringify(values) }
    ),

  // ── Client: Backups ──────────────────────────────────
  getBackups: (uuid: string) =>
    request<BackupEntry[]>(`/client/instances/${uuid}/backups`),

  createBackup: (uuid: string, name: string) =>
    request<BackupEntry>(`/client/instances/${uuid}/backups`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  restoreBackup: (uuid: string, backupUuid: string) =>
    request<{ message: string; instance_status: string | null }>(
      `/client/instances/${uuid}/backups/${backupUuid}/restore`,
      { method: "POST" }
    ),

  deleteBackup: (uuid: string, backupUuid: string) =>
    request<{ message: string }>(
      `/client/instances/${uuid}/backups/${backupUuid}`,
      { method: "DELETE" }
    ),

  // ── Client: Collaborators ────────────────────────────
  getCollaborators: (uuid: string) =>
    request<CollaboratorEntry[]>(`/client/instances/${uuid}/collaborators`),

  addCollaborator: (uuid: string, userId: number, permissions: string[]) =>
    request<CollaboratorEntry>(`/client/instances/${uuid}/collaborators`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, permissions }),
    }),

  updateCollaborator: (uuid: string, collabId: number, permissions: string[]) =>
    request<CollaboratorEntry>(`/client/instances/${uuid}/collaborators/${collabId}`, {
      method: "PATCH",
      body: JSON.stringify({ permissions }),
    }),

  deleteCollaborator: (uuid: string, collabId: number) =>
    request<{ message: string }>(`/client/instances/${uuid}/collaborators/${collabId}`, {
      method: "DELETE",
    }),

  // ── Client: Routines ─────────────────────────────────
  getRoutines: (uuid: string) =>
    request<RoutineEntry[]>(`/client/instances/${uuid}/routines`),

  createRoutine: (uuid: string, data: Record<string, unknown>) =>
    request<RoutineEntry>(`/client/instances/${uuid}/routines`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateRoutine: (uuid: string, routineId: number, data: Record<string, unknown>) =>
    request<RoutineEntry>(`/client/instances/${uuid}/routines/${routineId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteRoutine: (uuid: string, routineId: number) =>
    request<{ message: string }>(`/client/instances/${uuid}/routines/${routineId}`, {
      method: "DELETE",
    }),

  executeRoutine: (uuid: string, routineId: number) =>
    request<ExecutionResult>(`/client/instances/${uuid}/routines/${routineId}/execute`, {
      method: "POST",
    }),

  addRoutineAction: (uuid: string, routineId: number, data: Record<string, unknown>) =>
    request<ActionEntry>(`/client/instances/${uuid}/routines/${routineId}/actions`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateRoutineAction: (uuid: string, routineId: number, actionId: number, data: Record<string, unknown>) =>
    request<ActionEntry>(`/client/instances/${uuid}/routines/${routineId}/actions/${actionId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteRoutineAction: (uuid: string, routineId: number, actionId: number) =>
    request<{ message: string }>(`/client/instances/${uuid}/routines/${routineId}/actions/${actionId}`, {
      method: "DELETE",
    }),

  // ── Client: Activity ─────────────────────────────────
  getInstanceActivity: (uuid: string, limit: number = 50) =>
    request<ActivityLogEntry[]>(`/client/instances/${uuid}/activity?limit=${limit}`),

  // ── Admin: Activity ──────────────────────────────────
  getAdminActivity: (params?: { event?: string; page?: number; per_page?: number }) => {
    const p = new URLSearchParams();
    if (params?.event) p.set("event", params.event);
    if (params?.page) p.set("page", String(params.page));
    if (params?.per_page) p.set("per_page", String(params.per_page));
    return request<{ items: ActivityLogEntry[]; total: number; page: number; per_page: number }>(
      `/admin/activity?${p.toString()}`
    );
  },

  // ── Admin: Webhooks ───────────────────────────────────
  getWebhooks: () => request<WebhookEntry[]>("/admin/webhooks"),

  createWebhook: (data: WebhookCreate) =>
    request<WebhookEntry>("/admin/webhooks", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateWebhook: (id: number, data: WebhookUpdate) =>
    request<WebhookEntry>(`/admin/webhooks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteWebhook: (id: number) =>
    request<{ message: string }>(`/admin/webhooks/${id}`, {
      method: "DELETE",
    }),

  testWebhook: (id: number) =>
    request<WebhookTestResult>(`/admin/webhooks/${id}/test`, {
      method: "POST",
    }),

  getWebhookEvents: () => request<WebhookEventInfo[]>("/admin/webhooks/events"),

  // ── Admin: Runner-Info ────────────────────────────────
  getRunnerInfo: () =>
    request<{ adapter: string; timeout: { connect: number; read: number }; debug: boolean }>(
      "/admin/runner/info"
    ),

  // ── Admin: Database Providers (M18) ──────────────────
  getDatabaseProviders: () => request<Record<string, unknown>[]>("/admin/database-providers"),
  createDatabaseProvider: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/admin/database-providers", {
      method: "POST", body: JSON.stringify(data),
    }),
  updateDatabaseProvider: (id: number, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/admin/database-providers/${id}`, {
      method: "PATCH", body: JSON.stringify(data),
    }),
  deleteDatabaseProvider: (id: number) =>
    request<{ message: string }>(`/admin/database-providers/${id}`, { method: "DELETE" }),

  // ── Client: Instance Databases (M18) ─────────────────
  getDatabases: (uuid: string) =>
    request<Record<string, unknown>[]>(`/client/instances/${uuid}/databases`),
  createDatabase: (uuid: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/client/instances/${uuid}/databases`, {
      method: "POST", body: JSON.stringify(data),
    }),
  rotateDatabasePassword: (uuid: string, dbId: number) =>
    request<Record<string, unknown>>(`/client/instances/${uuid}/databases/${dbId}/rotate-password`, {
      method: "POST",
    }),
  deleteDatabase: (uuid: string, dbId: number) =>
    request<{ message: string }>(`/client/instances/${uuid}/databases/${dbId}`, { method: "DELETE" }),

  // ── Admin: Fleet Monitoring (M22) ─────────────────────
  getAgentsMonitoring: (params?: { health?: string; search?: string; stale_threshold?: number }) => {
    const p = new URLSearchParams();
    if (params?.health) p.set("health", params.health);
    if (params?.search) p.set("search", params.search);
    if (params?.stale_threshold) p.set("stale_threshold", String(params.stale_threshold));
    const qs = p.toString();
    return request<AgentMonitoringEntry[]>(`/admin/agents/monitoring${qs ? `?${qs}` : ""}`);
  },

  getAgentMonitoring: (agentId: number) =>
    request<AgentMonitoringEntry>(`/admin/agents/${agentId}/monitoring`),

  getFleetSummary: () => request<FleetSummary>("/admin/fleet/summary"),

  // ── Admin: Jobs (M23) ─────────────────────────────────
  getJobs: (params?: { status?: string; type?: string; page?: number; per_page?: number }) => {
    const p = new URLSearchParams();
    if (params?.status) p.set("status", params.status);
    if (params?.type) p.set("type", params.type);
    if (params?.page) p.set("page", String(params.page));
    if (params?.per_page) p.set("per_page", String(params.per_page));
    const qs = p.toString();
    return request<JobListResult>(`/admin/jobs${qs ? `?${qs}` : ""}`);
  },

  getJob: (jobId: number) => request<JobEntry>(`/admin/jobs/${jobId}`),

  getJobsSummary: () => request<JobSummary>("/admin/jobs/summary"),

  // ── Admin: System / Version (M24) ─────────────────────
  getSystemVersion: () => request<SystemVersionInfo>("/admin/system/version"),
  getUpgradeStatus: () => request<UpgradeStatus>("/admin/system/upgrade-status"),
  getPreflight: () => request<PreflightResult>("/admin/system/preflight"),
  getPaymentEvents: (params?: { status?: PaymentEventStatus; limit?: number }) => {
    const p = new URLSearchParams();
    if (params?.status) p.set("status", params.status);
    if (params?.limit) p.set("limit", String(params.limit));
    const qs = p.toString();
    return request<PaymentEvent[]>(`/admin/payment-events${qs ? `?${qs}` : ""}`);
  },
  getBillingStatus: () => request<BillingStatus>("/admin/billing/status"),

  // ── Admin: Agent Maintenance (M25) ────────────────────
  enableAgentMaintenance: (agentId: number, payload?: { reason?: string }) =>
    request<{ message: string; agent: Record<string, unknown> }>(
      `/admin/agents/${agentId}/maintenance`,
      { method: "POST", body: JSON.stringify(payload || {}) }
    ),

  disableAgentMaintenance: (agentId: number) =>
    request<{ message: string; agent: Record<string, unknown> }>(
      `/admin/agents/${agentId}/maintenance`,
      { method: "DELETE" }
    ),

  // ── Phase 4: Produkte (Admin) ────────────────────────
  getAdminProducts: () => request<Product[]>("/admin/products"),
  createProduct: (data: ProductInput) =>
    request<Product>("/admin/products", { method: "POST", body: JSON.stringify(data) }),
  updateProduct: (id: number, data: Partial<ProductInput>) =>
    request<Product>(`/admin/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProduct: (id: number) =>
    request<{ message?: string }>(`/admin/products/${id}`, { method: "DELETE" }),

  // ── Phase 4: Shop & Bestellungen (Kunde) ─────────────
  /** Oeffentlich: nur aktive Pakete ohne interne Felder. */
  getShopProducts: () => request<Product[]>("/client/products"),
  /** `name` ist optional; ohne Name vergibt das Backend einen. */
  createOrder: (productId: number, name?: string) =>
    request<Order>("/client/orders", {
      method: "POST",
      body: JSON.stringify(name ? { product_id: productId, name } : { product_id: productId }),
    }),
  getMyOrders: () => request<Order[]>("/client/orders"),
  /** Fertig gerenderte HTML-Seite eines Belegs (per Token geholt, ein normaler Link traegt keinen Authorization-Header). */
  getReceiptHtml: (orderUuid: string, number: string) =>
    request<string>(`/client/orders/${orderUuid}/receipt?number=${encodeURIComponent(number)}&format=html`, {}, true),
  /** Welcher Zahlungsweg aktiv ist: "manual" (Ueberweisung) oder "stripe" (online). */
  getBillingInfo: () =>
    request<{ payment_provider: "manual" | "stripe" | string; online_payment: boolean }>("/client/billing-info"),
  /** Startet die Zahlung (Stripe Checkout). 409 "manual", solange kein Zahlungsanbieter konfiguriert ist. */
  createCheckout: (uuid: string) =>
    request<{ checkout_url: string }>(`/client/orders/${uuid}/checkout`, { method: "POST", body: JSON.stringify({}) }),
  /** pending_payment: sofort storniert; active: zum Laufzeitende gekuendigt (cancel_at_period_end). */
  cancelOrder: (uuid: string) =>
    request<Order>(`/client/orders/${uuid}/cancel`, { method: "POST", body: JSON.stringify({}) }),

  // ── Phase 4: Bestellungen (Admin) ────────────────────
  getAdminOrders: (status?: OrderStatus | "") =>
    request<Order[]>(`/admin/orders${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  /** Bei awaiting_provisioning erneut bereitstellen (Zahlung wird nicht doppelt verbucht). */
  markOrderPaid: (uuid: string, paymentReference?: string) =>
    request<Order>(`/admin/orders/${uuid}/mark-paid`, {
      method: "POST",
      body: JSON.stringify(paymentReference ? { payment_reference: paymentReference } : {}),
    }),

  // ── Instance loeschen (M43) ───────────────────────────
  /** Owner: Body {confirm} muss dem Instance-Namen entsprechen. */
  deleteInstance: (uuid: string, confirmName: string) =>
    request<{ uuid: string; message: string }>(`/client/instances/${uuid}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm: confirmName }),
    }),
  /** Admin: optional `force` bricht laufende Vorgaenge ab. */
  adminDeleteInstance: (uuid: string, force = false) =>
    request<{ uuid: string; message: string; runner_cleanup?: string; forced?: boolean }>(`/admin/instances/${uuid}`, {
      method: "DELETE",
      body: JSON.stringify(force ? { force: true } : {}),
    }),

  // ── Admin: Suspension (M29) ───────────────────────────
  suspendInstance: (uuid: string, reason?: string) =>
    request<{ message: string; instance: Instance }>(`/admin/instances/${uuid}/suspend`, {
      method: "POST",
      body: JSON.stringify(reason ? { reason } : {}),
    }),

  unsuspendInstance: (uuid: string) =>
    request<{ message: string; instance: Instance }>(`/admin/instances/${uuid}/unsuspend`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  // ── Client: SSH Keys (M28) ─────────────────────────────
  getSshKeys: () => request<SshKeyEntry[]>("/client/account/ssh-keys"),

  createSshKey: (payload: SshKeyCreateRequest) =>
    request<SshKeyEntry>("/client/account/ssh-keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateSshKeyName: (keyId: number, name: string) =>
    request<SshKeyEntry>(`/client/account/ssh-keys/${keyId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  deleteSshKey: (keyId: number) =>
    request<{ message: string }>(`/client/account/ssh-keys/${keyId}`, {
      method: "DELETE",
    }),
};
