// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminOverview } from "./AdminOverview";
import { api, ApiError, type PaymentEvent } from "../../services/api";
import { makeOrder } from "../../test/fixtures";
import { setLang } from "../../i18n";

beforeEach(() => vi.restoreAllMocks());
afterEach(() => { cleanup(); setLang("de"); });

const mount = (period: 7 | 30 | 90 = 30) => render(<MemoryRouter><AdminOverview period={period} /></MemoryRouter>);

const agent = (over: Record<string, unknown> = {}) => ({
  id: 1, name: "de-fra-01", fqdn: "n", health_status: "healthy", is_active: true, is_stale: false, last_seen_at: "2026-10-04T10:00:00Z",
  maintenance_mode: false, instance_count: 19,
  capacity: { memory_total_mb: 65536, disk_total_mb: 491520, effective_memory_mb: 65536, effective_disk_mb: 491520, cpu_total_percent: 800, effective_cpu_percent: 800 },
  utilization: { used_memory_mb: 47104, used_disk_mb: 419840, used_cpu_percent: 100, memory_utilization: 72, disk_utilization: 85, cpu_utilization: 12, instance_count: 19 },
  ...over,
});

const ev = (id: number, status: "mismatch" | "unapplied", detail: string): PaymentEvent => ({
  id, event_id: `evt_${id}_abcdef`, provider: "stripe", event_type: "x", order_uuid: id === 1 ? "abcdef1234" : null, status, detail,
  received_at: "2026-10-04T10:00:00Z", processed_at: null,
});

function mockAll() {
  const recent = new Date(Date.now() - 2 * 86_400_000).toISOString();
  vi.spyOn(api, "getRevenueStats").mockResolvedValue({
    days: 30, since: "", by_currency: { EUR: 128400 }, paid_count: 24, renewals_count: 6, refunded_cents_by_currency: { EUR: 1490 },
  });
  vi.spyOn(api, "getAdminOrders").mockResolvedValue([
    makeOrder({ id: 1, uuid: "a", status: "active", created_at: recent, paid_at: recent, current_period_end: new Date(Date.now() + 5 * 3_600_000).toISOString() }),
    makeOrder({ id: 2, uuid: "b", status: "pending_payment", created_at: recent }),
    makeOrder({ id: 3, uuid: "c", status: "past_due", created_at: recent, paid_at: recent }),
  ]);
  vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([agent()] as never);
  vi.spyOn(api, "getInstances").mockResolvedValue([
    { status: "ready", container_state: "running", agent_id: 1 }, { status: "ready", container_state: "offline", agent_id: 1 },
  ] as never);
  vi.spyOn(api, "getPaymentEvents").mockImplementation(async (p) =>
    p?.status === "mismatch" ? [ev(1, "mismatch", "Betrag 5.00 statt 9.99")] : [ev(2, "unapplied", "Bestellung bereits beendet")]);
  vi.spyOn(api, "getBillingStatus").mockResolvedValue({
    healthy: true, last_run_at: new Date(Date.now() - 120_000).toISOString(), age_seconds: 120, max_age_minutes: 15,
    orders_needing_tick: 0, orders_by_status: {}, last_summary: null,
  });
}

describe("AdminOverview", () => {
  it("zeigt Kennzahlen: Umsatz, Bestellungen nach Zustand, laufende Instances und Tick", async () => {
    mockAll();
    mount();
    expect((await screen.findByTestId("revenue-EUR")).textContent).toMatch(/1\.284,00/);
    expect(screen.getByText("24 Zahlungen, davon 6 Verlängerungen")).toBeTruthy();
    expect(screen.getByTestId("revenue-refunds").textContent).toMatch(/Erstattet: .*14,90.*\(nicht abgezogen\)/);
    expect(screen.getByTestId("orders-total").textContent).toBe("3");
    const orders = screen.getByRole("group", { name: "Bestellungen 30 Tage" });
    expect(within(orders).getByText("1 bezahlt")).toBeTruthy();
    expect(within(orders).getByText("1 wartend")).toBeTruthy();
    expect(within(orders).getByText("1 überfällig")).toBeTruthy();
    expect((await screen.findByTestId("instances-running")).textContent).toBe("1 / 2");
    expect(await screen.findByText(/letzter Lauf vor 2 Min\./)).toBeTruthy();
  });

  it("zeigt Node-Balken mit Werten und Warnfarbe ab 80 % sowie die auffälligen Zahlungen", async () => {
    mockAll();
    mount();
    const nodes = await screen.findByRole("region", { name: "Node-Auslastung" });
    expect(within(nodes).getByText("de-fra-01")).toBeTruthy();
    expect(within(nodes).getByText("19 Instances")).toBeTruthy();
    expect(within(nodes).getByText("46 GB / 64 GB")).toBeTruthy();
    const disk = within(nodes).getByRole("progressbar", { name: "Festplatte 85 %" });
    expect(disk.className).toContain("bar-warn");
    const pay = screen.getByRole("region", { name: "Auffällige Zahlungen" });
    expect(await within(pay).findByText("Betrag weicht ab")).toBeTruthy();
    expect(within(pay).getByText("Erstattung prüfen")).toBeTruthy();
    expect(within(pay).getByText("Bestellung bereits beendet")).toBeTruthy();
    expect(pay.textContent).toContain("Läuft in 24 h ab: #1");
  });

  it("warnt bei gestoerten Nodes (alert) und bündelt Hinweise in einem Banner (status)", async () => {
    mockAll();
    vi.mocked(api.getAgentsMonitoring).mockResolvedValue([agent({ id: 2, name: "de-fra-02", health_status: "unreachable", instance_count: 5 })] as never);
    vi.mocked(api.getInstances).mockResolvedValue([{ status: "ready", container_state: "running", agent_id: 2 }] as never);
    vi.mocked(api.getBillingStatus).mockResolvedValue({
      healthy: false, last_run_at: null, age_seconds: null, max_age_minutes: 15, orders_needing_tick: 2, orders_by_status: {}, last_summary: null,
    });
    mount();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Node de-fra-02 nicht erreichbar – 5 Instances betroffen/);
    expect(screen.getByRole("link", { name: "Node öffnen" }).getAttribute("href")).toBe("/admin/agents/monitoring");
    const status = await screen.findByText(/Fehlstatus warten auf Prüfung/);
    expect(status.textContent).toContain("Container billing prüfen");
    expect(status.textContent).toContain("1 Bestellung läuft in 24 h ab");
    expect(await screen.findByText(/1 auf gestörten Nodes \(de-fra-02\)/)).toBeTruthy();
  });

  it("zeigt ohne Auffälligkeiten keine Banner", async () => {
    mockAll();
    vi.mocked(api.getPaymentEvents).mockResolvedValue([]);
    vi.mocked(api.getAdminOrders).mockResolvedValue([]);
    mount();
    await screen.findByText("Keine Abweichungen oder nicht zugeordneten Zahlungen.");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/Fehlstatus/)).toBeNull();
  });

  it("fällt bei 404 des Umsatz-Endpunkts auf die Schätzung zurück und nutzt den gewählten Zeitraum", async () => {
    mockAll();
    const rev = vi.mocked(api.getRevenueStats).mockRejectedValue(new ApiError("Request failed: 404", 404));
    mount(90);
    expect(await screen.findByText(/Näherung/)).toBeTruthy();
    expect(screen.getByText("Umsatz 90 Tage")).toBeTruthy();
    expect(rev).toHaveBeenCalledWith(90);
  });

  const withPrev = (prev: Record<string, number> | undefined) => {
    mockAll();
    vi.mocked(api.getRevenueStats).mockResolvedValue({
      days: 30, since: "", by_currency: { EUR: 112000 }, paid_count: 24, renewals_count: 6, refunded_cents_by_currency: {},
      ...(prev ? { prev_since: "", prev_by_currency: prev, prev_paid_count: 20, prev_renewals_count: 4 } : {}),
    });
  };

  it("zeigt den Umsatztrend zum Vorzeitraum (Anstieg, Rueckgang), nur wenn der Vorzeitraum > 0 war", async () => {
    withPrev({ EUR: 100000 });
    mount();
    const up = await screen.findByTestId("revenue-trend-EUR");
    expect(up.textContent).toBe("+12 % zum Vorzeitraum");
    expect(up.className).toContain("trend-up");
    cleanup();
    withPrev({ EUR: 160000 });
    mount();
    const down = await screen.findByTestId("revenue-trend-EUR");
    expect(down.textContent).toMatch(/^[-\u2212]30 % zum Vorzeitraum$/);
    expect(down.className).toContain("trend-down");
  });

  it("zeigt 'kein Vergleich' ohne Umsatz im Vorzeitraum und keine Trendzeile bei aelterem Backend", async () => {
    withPrev({ EUR: 0 });
    mount();
    expect((await screen.findByTestId("revenue-trend-EUR")).textContent).toBe("kein Vergleich");
    cleanup();
    withPrev(undefined);
    mount();
    await screen.findByTestId("revenue-EUR");
    expect(screen.queryByTestId("revenue-trend-EUR")).toBeNull();
  });

  it("beschriftet den Trend auf Englisch", async () => {
    setLang("en");
    withPrev({ EUR: 100000 });
    mount();
    expect((await screen.findByTestId("revenue-trend-EUR")).textContent).toBe("+12% vs. previous period");
  });

  it("lässt eine ausgefallene Datenquelle nur ihre Kachel betreffen", async () => {
    mockAll();
    vi.mocked(api.getAgentsMonitoring).mockRejectedValue(new Error("boom"));
    mount();
    expect(await screen.findByText(/Node-Auslastung: Daten konnten nicht geladen werden/)).toBeTruthy();
    expect(await screen.findByTestId("revenue-EUR")).toBeTruthy();
    expect(screen.getByTestId("orders-total")).toBeTruthy();
  });

  it("zeigt die Übersicht auf Englisch mit Plural, Datum und Währung der Sprache", async () => {
    setLang("en");
    mockAll();
    mount();
    expect((await screen.findByTestId("revenue-EUR")).textContent).toMatch(/1,284\.00/);
    expect(screen.getByText("24 payments, of which 6 renewals")).toBeTruthy();
    expect(screen.getByTestId("revenue-refunds").textContent).toMatch(/Refunded: .*14\.90.*\(not deducted\)/);
    const orders = screen.getByRole("group", { name: "Orders 30 days" });
    expect(within(orders).getByText("1 paid")).toBeTruthy();
    expect(within(orders).getByText("1 waiting")).toBeTruthy();
    expect(within(orders).getByText("1 overdue")).toBeTruthy();
    expect(await screen.findByText(/last run 2 min ago/)).toBeTruthy();
    const nodes = await screen.findByRole("region", { name: "Node utilisation" });
    expect(within(nodes).getByText("19 instances")).toBeTruthy();
    expect(within(nodes).getByRole("progressbar", { name: "Disk 85 %" })).toBeTruthy();
    const pay = screen.getByRole("region", { name: "Flagged payments" });
    expect(pay.textContent).toContain("Expires within 24 h: #1");
    expect(screen.getByText(/1 order expires within 24 h/)).toBeTruthy();
  });
});
