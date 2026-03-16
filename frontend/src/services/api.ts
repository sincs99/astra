/**
 * Zentraler API-Service fuer Astra.
 *
 * In Entwicklung: Vite-Proxy (/api -> localhost:5000)
 * In Produktion:  VITE_API_BASE_URL oder /api (hinter Nginx)
 */

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

async function request<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
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

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      (error as Record<string, string>).error ||
        `Request failed: ${response.status}`
    );
  }

  return (await response.json()) as T;
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
}

// ── Typen ──────────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  email: string;
  is_admin: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface Agent {
  id: number;
  name: string;
  fqdn: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentCreate {
  name: string;
  fqdn: string;
}

export interface BlueprintVariable {
  name: string;
  description: string;
  env_var: string;
  default_value: string;
  user_viewable: boolean;
  user_editable: boolean;
}

export interface Blueprint {
  id: number;
  name: string;
  description: string | null;
  docker_image: string | null;
  startup_command: string | null;
  install_script: string | null;
  variables: BlueprintVariable[];
  config_schema: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BlueprintCreate {
  name: string;
  description?: string;
  docker_image?: string;
  startup_command?: string;
  install_script?: string;
  variables?: BlueprintVariable[];
}

export interface BlueprintUpdate {
  name?: string;
  description?: string;
  docker_image?: string;
  startup_command?: string;
  install_script?: string;
  variables?: BlueprintVariable[];
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
}

export interface InstanceCreate {
  name: string;
  owner_id: number;
  agent_id: number;
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
  // ── Auth ─────────────────────────────────────────────
  login: (login: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }),

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

  // ── Admin: Blueprints ────────────────────────────────
  getBlueprints: () => request<Blueprint[]>("/admin/blueprints"),
  createBlueprint: (data: BlueprintCreate) =>
    request<Blueprint>("/admin/blueprints", {
      method: "POST",
      body: JSON.stringify(data),
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

  // ── Admin: Instances ─────────────────────────────────
  getInstances: () => request<Instance[]>("/admin/instances"),
  createInstance: (data: InstanceCreate) =>
    request<Instance>("/admin/instances", {
      method: "POST",
      body: JSON.stringify(data),
    }),
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

  // ── Agent: Callbacks (fuer lokale Tests) ──────────────
  reportInstallResult: (uuid: string, successful: boolean) =>
    request<{ uuid: string; status: string; message: string }>(
      `/agent/instances/${uuid}/install`,
      {
        method: "POST",
        body: JSON.stringify({ successful }),
      }
    ),

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
