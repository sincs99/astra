// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OverviewTiles } from "./OverviewTiles";
import { api, type PaymentEvent } from "../../services/api";
import { makeOrder } from "../../test/fixtures";

beforeEach(() => vi.restoreAllMocks());
afterEach(cleanup);

const mount = () => render(<MemoryRouter><OverviewTiles /></MemoryRouter>);

const agent = {
  id: 1, name: "node-1", fqdn: "n1", health_status: "healthy", is_active: true, is_stale: false, last_seen_at: null,
  maintenance_mode: false, maintenance_reason: null, maintenance_started_at: null, available_for_deployment: true,
  capacity: { memory_total_mb: 4096, disk_total_mb: 10240, cpu_total_percent: 400, memory_overalloc_percent: 0, disk_overalloc_percent: 0, cpu_overalloc_percent: 0, effective_memory_mb: 4096, effective_disk_mb: 10240, effective_cpu_percent: 400 },
  utilization: { instance_count: 2, used_memory_mb: 2048, used_disk_mb: 1024, used_cpu_percent: 100, memory_utilization: 50, disk_utilization: 10, cpu_utilization: 25 },
  instance_count: 2, endpoint_summary: { total: 0, assigned: 0, free: 0, locked: 0 },
};

const ev = (id: number, status: "mismatch" | "unapplied", detail: string): PaymentEvent => ({
  id, event_id: `e${id}`, provider: "stripe", event_type: "checkout.session.completed", order_uuid: "abcdef12-0000", status,
  detail, received_at: `2026-10-0${id}T10:00:00Z`, processed_at: null,
});

function mockAll() {
  const recent = new Date(Date.now() - 2 * 86_400_000).toISOString();
  vi.spyOn(api, "getAdminOrders").mockResolvedValue([
    makeOrder({ status: "active", price_cents: 999, paid_at: recent }),
    makeOrder({ uuid: "b", status: "pending_payment" }),
    makeOrder({ uuid: "c", status: "awaiting_provisioning", price_cents: 500, paid_at: recent }),
  ]);
  vi.spyOn(api, "getAgentsMonitoring").mockResolvedValue([agent] as never);
  vi.spyOn(api, "getPaymentEvents").mockImplementation(async (p) =>
    p?.status === "mismatch" ? [ev(1, "mismatch", "Betrag 5.00 statt 9.99")] : [ev(2, "unapplied", "Bestellung bereits beendet")]);
}

describe("OverviewTiles", () => {
  it("zeigt Umsatz, Bestellungen je Status, Auslastung und Zahlungsereignisse", async () => {
    mockAll();
    mount();
    expect((await screen.findByTestId("revenue-EUR")).textContent).toMatch(/14,99/);
    expect(screen.getByTestId("orders-active").textContent).toBe("1");
    expect(screen.getByTestId("orders-pending_payment").textContent).toBe("1");
    expect(screen.getByTestId("orders-past_due").textContent).toBe("0");
    expect(screen.getByRole("link", { name: "Zahlung ausstehend" }).getAttribute("href")).toBe("/admin/orders?status=pending_payment");
    expect(await screen.findByText(/am höchsten ausgelastet/)).toBeTruthy();
    expect(screen.getByText("node-1")).toBeTruthy();
    const events = screen.getByRole("region", { name: "Zahlungsereignisse mit Handlungsbedarf" });
    expect(within(events).getByText("Betrag weicht ab")).toBeTruthy();
    expect(within(events).getByText("Erstattung prüfen")).toBeTruthy();
    expect(within(events).getByText("Bestellung bereits beendet")).toBeTruthy();
  });

  it("meldet leere Zahlungsereignisse ruhig", async () => {
    mockAll();
    vi.spyOn(api, "getPaymentEvents").mockResolvedValue([]);
    mount();
    expect(await screen.findByText("Keine Abweichungen oder nicht zugeordneten Zahlungen.")).toBeTruthy();
  });

  it("faellt pro Kachel aus, ohne die anderen zu stoeren", async () => {
    mockAll();
    vi.spyOn(api, "getAgentsMonitoring").mockRejectedValue(new Error("boom"));
    mount();
    expect(await screen.findByText("Daten konnten nicht geladen werden.")).toBeTruthy();
    expect(await screen.findByTestId("revenue-EUR")).toBeTruthy();
    expect(screen.getByTestId("orders-active")).toBeTruthy();
  });
});
