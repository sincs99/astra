// Gemeinsame Helfer fuer die E2E-Skripte (flow.mjs, a11y.mjs): Konfiguration, API-Aufrufe, Grunddaten, Browser-Start.
import { existsSync } from "node:fs";
import { chromium } from "playwright-core";

export const BASE = process.env.E2E_BASE_URL ?? "http://localhost:4190";
export const API = process.env.E2E_API_URL ?? "http://localhost:5000/api";
// Vorinstalliertes Chromium (z.B. Cloud-Umgebung) oder das von `npx playwright-core install chromium` geladene
export const PREINSTALLED = "/opt/pw-browsers/chromium";
export const CHROMIUM = process.env.CHROMIUM_PATH ?? (existsSync(PREINSTALLED) ? PREINSTALLED : undefined);
export const ADMIN = { login: process.env.E2E_ADMIN_USER ?? "admin", password: process.env.E2E_ADMIN_PASSWORD ?? "adminpass123" };
export const run = Date.now().toString(36);
export const customer = { username: `kunde_${run}`, email: `kunde_${run}@example.com`, password: "kundenpass123" };
export const serverName = `E2E Server ${run}`;

export async function api(method, path, body, token) {
  const res = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${JSON.stringify(data)}`);
  return data;
}

/** Admin-Grunddaten per API anlegen (ein Blueprint, ein Node mit Endpoints, ein Paket). */
export async function seed() {
  const { access_token: token } = await api("POST", "/auth/login", ADMIN);
  const blueprint = await api("POST", "/admin/blueprints", {
    name: `E2E Blueprint ${run}`, docker_image: "itzg/minecraft-server", startup_command: "java -jar server.jar",
  }, token);
  const agent = await api("POST", "/admin/agents", {
    name: `E2E-Node-${run}`, fqdn: `e2e-${run}.example.com`, memory_total: 16384, disk_total: 500000, cpu_total: 800,
  }, token);
  const start = 30000 + Math.floor(Math.random() * 20000);
  await api("POST", `/admin/agents/${agent.id}/endpoints/bulk`, { ip: "0.0.0.0", port_start: start, port_end: start + 5 }, token);
  const product = await api("POST", "/admin/products", {
    name: `E2E-Paket ${run}`, blueprint_id: blueprint.id, memory: 1024, disk: 5120, cpu: 100, price_cents: 499,
  }, token);
  return product;
}

export function launchBrowser() {
  return chromium.launch({ ...(CHROMIUM ? { executablePath: CHROMIUM } : {}), args: ["--no-sandbox"] });
}
