// E2E-Durchlauf gegen das echte Backend (Stub-Runner, manuelle Zahlung).
// Start ueber e2e/run-local.sh (startet Backend + Frontend und ruft dieses Skript auf).
import { BASE, ADMIN, customer, serverName, seed, launchBrowser } from "./lib.mjs";

let step = 0;
const log = (msg) => console.log(`[e2e] ${++step}. ${msg}`);

async function expectVisible(page, locator, what, timeout = 10000) {
  try {
    await locator.waitFor({ state: "visible", timeout });
  } catch {
    await page.screenshot({ path: `e2e-fehler-${step}.png`, fullPage: true }).catch(() => {});
    throw new Error(`Nicht sichtbar: ${what} (URL ${page.url()})`);
  }
}

const browser = await launchBrowser();
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
  await cust.locator("label.pcard", { hasText: product.name }).click();
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
  await adm.getByRole("dialog").getByRole("button", { name: "Bezahlt bestätigen" }).click();
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
