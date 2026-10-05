// Barrierefreiheitspruefung (axe-core, WCAG A/AA) gegen die Preview mit echtem Backend.
// Start ueber e2e/run-local.sh (nach flow.mjs). Exit 1 mit lesbarer Liste, wenn Verstoesse gefunden werden.
// axe-core kommt aus node_modules (kein CDN).
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { BASE, ADMIN, customer, serverName, api, seed, launchBrowser } from "./lib.mjs";

const axeSource = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const TOKEN_KEY = "astra_access_token";
const THEME_KEY = "astra_theme";
const THEMES = ["dark", "light"];
const WIDTHS = [390, 1100];

/** Kunde + Server (bezahlt), Admin-Token: so haben Dashboard, Bestellungen und Server-Detail echte Inhalte. */
async function prepare() {
  const product = await seed();
  await api("POST", "/auth/register", customer);
  const { access_token: customerToken } = await api("POST", "/auth/login", { login: customer.username, password: customer.password });
  const { access_token: adminToken } = await api("POST", "/auth/login", ADMIN);
  const order = await api("POST", "/client/orders", { product_id: product.id, name: serverName }, customerToken);
  await api("POST", `/admin/orders/${order.uuid}/mark-paid`, {}, adminToken);
  let instance;
  for (let i = 0; i < 20 && !instance; i++) {
    instance = (await api("GET", "/client/instances", undefined, customerToken))[0];
    if (!instance) await new Promise((r) => setTimeout(r, 500));
  }
  if (!instance) throw new Error("Kein Server nach der Bezahlung entstanden");
  return { customerToken, adminToken, instanceUuid: instance.uuid };
}

const browser = await launchBrowser();
const findings = [];
let checked = 0;
try {
  const { customerToken, adminToken, instanceUuid } = await prepare();
  // role: null = ohne Anmeldung
  const routes = [
    { path: "/", role: null, name: "Landing" },
    { path: "/login", role: null, name: "Login" },
    { path: "/register", role: null, name: "Registrierung" },
    { path: "/datenschutz", role: null, name: "Datenschutz" },
    { path: "/", role: "customer", name: "Dashboard", ready: "h1" },
    { path: "/shop", role: "customer", name: "Shop", ready: "h1" },
    { path: "/orders", role: "customer", name: "Bestellungen", ready: "h1" },
    { path: `/instances/${instanceUuid}?tab=console`, role: "customer", name: "Server-Detail (Konsole)", ready: "h1" },
    { path: "/admin", role: "admin", name: "Admin-Übersicht", ready: "h1" },
    { path: "/admin/orders", role: "admin", name: "Admin-Bestellungen", ready: "h1" },
    { path: "/admin/invoices", role: "admin", name: "Admin-Rechnungen", ready: "h1" },
    { path: "/account", role: "customer", name: "Konto", ready: "h1" },
  ];
  const tokens = { customer: customerToken, admin: adminToken };

  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 } });
      for (const route of routes) {
        const page = await ctx.newPage();
        await page.addInitScript(([k, t, kt, token]) => {
          localStorage.setItem(t, k);
          if (token) localStorage.setItem(kt, token);
        }, [theme, THEME_KEY, TOKEN_KEY, route.role ? tokens[route.role] : null]);
        await page.goto(BASE + route.path);
        await page.waitForSelector(route.ready ?? "h1, main", { timeout: 15000 });
        await page.waitForLoadState("networkidle").catch(() => {});
        await page.addScriptTag({ content: axeSource });
        const result = await page.evaluate(() => globalThis.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }));
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
        checked++;
        const where = `${route.name} [${theme}, ${width}px]`;
        for (const v of result.violations) {
          findings.push(`${where}: ${v.id} (${v.impact}) – ${v.help}\n    ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join("\n    ")}\n    ${v.helpUrl}`);
        }
        if (overflow) findings.push(`${where}: Seite scrollt horizontal (Überlauf)`);
        await page.close();
      }
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}

if (findings.length > 0) {
  console.error(`[a11y] ${findings.length} Verstoß/Verstöße bei ${checked} Prüfungen:\n\n${findings.join("\n\n")}`);
  process.exit(1);
}
console.log(`[a11y] OK: ${checked} Prüfungen (WCAG A/AA, ${THEMES.join("/")}, ${WIDTHS.join("/")} px), keine Verstöße`);
