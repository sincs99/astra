// E2E-Durchlauf gegen das echte Backend (Stub-Runner, manuelle Zahlung).
// Start ueber e2e/run-local.sh (startet Backend + Frontend und ruft dieses Skript auf).
import { existsSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:4190";
const API = process.env.E2E_API_URL ?? "http://localhost:5000/api";
// Vorinstalliertes Chromium (z.B. Cloud-Umgebung) oder das von `npx playwright-core install chromium` geladene
const PREINSTALLED = "/opt/pw-browsers/chromium";
const CHROMIUM = process.env.CHROMIUM_PATH ?? (existsSync(PREINSTALLED) ? PREINSTALLED : undefined);
const ADMIN = { login: process.env.E2E_ADMIN_USER ?? "admin", password: process.env.E2E_ADMIN_PASSWORD ?? "adminpass123" };
const run = Date.now().toString(36);
const customer = { username: `kunde_${run}`, email: `kunde_${run}@example.com`, password: "kundenpass123" };
const serverName = `E2E Server ${run}`;

async function api(method, path, body, token) {
  const res = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${JSON.stringify(data)}`);
  return data;
}

let step = 0;
const log = (msg) => console.log(`[e2e] ${++step}. ${msg}`);

/** Admin-Grunddaten per API anlegen (ein Blueprint, ein Node mit Endpoints, ein Paket). */
async function seed() {
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

async function expectVisible(page, locator, what, timeout = 10000) {
  try {
    await locator.waitFor({ state: "visible", timeout });
  } catch {
    await page.screenshot({ path: `e2e-fehler-${step}.png`, fullPage: true }).catch(() => {});
    throw new Error(`Nicht sichtbar: ${what} (URL ${page.url()})`);
  }
}

const browser = await chromium.launch({ ...(CHROMIUM ? { executablePath: CHROMIUM } : {}), args: ["--no-sandbox"] });
try {
  const product = await seed();
  log(`Grunddaten angelegt (Paket "${product.name}")`);

  // ── Kunde: Registrierung, Login, Bestellung ───────────────
  const cust = await (await browser.newContext()).newPage();
  await cust.goto(`${BASE}/register`);
  await cust.getByLabel("Benutzername").fill(customer.username);
  await cust.getByLabel("E-Mail").fill(customer.email);
  await cust.getByLabel("Passwort", { exact: true }).fill(customer.password);
  await cust.getByLabel("Passwort wiederholen").fill(customer.password);
  await cust.getByLabel(/AGB/).check();
  await cust.getByRole("button", { name: "Konto erstellen" }).click();
  log("Kunde registriert");

  // Je nach Konfiguration folgt Login-Seite oder direkt das Dashboard
  await cust.waitForURL(/\/(login|$)/, { timeout: 10000 });
  if (cust.url().includes("/login")) {
    await cust.getByLabel("Benutzername oder E-Mail").fill(customer.username);
    await cust.getByLabel("Passwort", { exact: true }).fill(customer.password);
    await cust.getByRole("button", { name: /Anmelden/ }).click();
  }
  await expectVisible(cust, cust.getByRole("heading", { name: "Meine Server" }), "Meine Server nach Login");
  log("Kunde eingeloggt");

  await cust.goto(`${BASE}/shop`);
  await cust.getByRole("button", { name: `${product.name} bestellen` }).click();
  await cust.getByLabel("Servername (optional)").fill(serverName);
  await cust.getByRole("button", { name: "Verbindlich bestellen" }).click();
  await expectVisible(cust, cust.getByText("Bestellung eingegangen."), "Bestätigung im Shop");
  await cust.getByRole("link", { name: "Zu meinen Bestellungen" }).click();
  await cust.waitForURL(/\/orders/, { timeout: 10000 });
  await expectVisible(cust, cust.getByText(serverName).first(), "Bestellung in der Liste");
  await expectVisible(cust, cust.getByText("Zahlung ausstehend").first(), "Status Zahlung ausstehend");
  log("Bestellung aufgegeben (Zahlung ausstehend)");

  // ── Admin: als bezahlt markieren ──────────────────────────
  const adm = await (await browser.newContext()).newPage();
  await adm.goto(`${BASE}/login`);
  await adm.getByLabel("Benutzername oder E-Mail").fill(ADMIN.login);
  await adm.getByLabel("Passwort", { exact: true }).fill(ADMIN.password);
  await adm.getByRole("button", { name: /Anmelden/ }).click();
  await adm.waitForURL(`${BASE}/`, { timeout: 10000 });
  await adm.goto(`${BASE}/admin/orders`);
  const row = adm.getByRole("row").filter({ hasText: serverName });
  await expectVisible(adm, row, "Bestellung in der Admin-Liste");
  await row.getByRole("button", { name: "Als bezahlt markieren" }).click();
  await row.getByRole("button", { name: "Bezahlt bestätigen" }).click();
  await expectVisible(adm, adm.getByText(/als bezahlt markiert/), "Bestätigung 'als bezahlt markiert'");
  log("Admin hat die Bestellung als bezahlt markiert");

  // ── Kunde sieht den Server im Dashboard ───────────────────
  await cust.goto(`${BASE}/`);
  await expectVisible(cust, cust.getByRole("link", { name: serverName }), "Server-Karte im Kunden-Dashboard");
  log("Kunde sieht den Server im Dashboard");

  console.log("[e2e] OK");
} finally {
  await browser.close();
}
