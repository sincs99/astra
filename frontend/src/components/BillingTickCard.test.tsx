// @vitest-environment jsdom
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { BillingTickCard } from "./BillingTickCard";
import { api, type BillingStatus } from "../services/api";

beforeEach(() => vi.restoreAllMocks());
afterEach(cleanup);

const base: BillingStatus = {
  healthy: true,
  last_run_at: new Date(Date.now() - 3 * 60_000).toISOString(),
  age_seconds: 180,
  max_age_minutes: 15,
  orders_needing_tick: 0,
  orders_by_status: { active: 4, past_due: 1, cancelled: 0 },
  last_summary: null,
};

describe("BillingTickCard", () => {
  it("zeigt gesund, relativen letzten Lauf und Bestellungen je Status", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue(base);
    render(<MemoryRouter><BillingTickCard /></MemoryRouter>);
    expect(await screen.findByText("gesund")).toBeTruthy();
    expect(screen.getByText("Letzter Lauf: vor 3 Min.")).toBeTruthy();
    expect(screen.getByText("aktiv: 4")).toBeTruthy();
    expect(screen.queryByText(/cancelled|storniert: 0/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warnt deutlich, wenn der Tick nicht laeuft", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue({ ...base, healthy: false, last_run_at: null, age_seconds: null, orders_needing_tick: 2 });
    render(<MemoryRouter><BillingTickCard /></MemoryRouter>);
    expect((await screen.findByRole("alert")).textContent).toContain("Container billing prüfen");
    expect(screen.getByText("Letzter Lauf: noch nie")).toBeTruthy();
  });

  it("blendet sich bei Fehler (z.B. 404) still aus", async () => {
    vi.spyOn(api, "getBillingStatus").mockRejectedValue(new Error("404"));
    const { container } = render(<MemoryRouter><BillingTickCard /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });

  it("blendet sich im Dashboard-Modus aus, solange alles gesund ist", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue(base);
    const { container } = render(<MemoryRouter><BillingTickCard onlyWhenUnhealthy /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });

  const waitingBase = { count: 2, oldest_paid_at: "2026-10-03T08:00:00Z", oldest_wait_hours: 5.4, warn_after_hours: 24, waiting_too_long: false };

  it("zeigt wartende bezahlte Bestellungen ohne Warnung, solange sie nicht zu lange warten", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue({ ...base, awaiting_provisioning: waitingBase });
    render(<MemoryRouter><BillingTickCard /></MemoryRouter>);
    expect((await screen.findByTestId("awaiting-capacity")).textContent)
      .toBe("2 bezahlte Bestellung(en) warten auf einen freien Node, die älteste seit 5 Stunden.");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warnt mit Link zu den Agents, wenn die Wartezeit zu lang ist, und zeigt die Karte auch im Dashboard-Modus", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue({
      ...base, awaiting_provisioning: { ...waitingBase, oldest_wait_hours: 30, waiting_too_long: true },
    });
    render(<MemoryRouter><BillingTickCard onlyWhenUnhealthy /></MemoryRouter>);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Kapazität prüfen");
    expect(screen.getByRole("link", { name: "Zu den Agents" }).getAttribute("href")).toBe("/admin/agents");
    expect(screen.getByTestId("awaiting-capacity").textContent).toContain("seit 30 Stunden");
  });

  it("funktioniert weiter mit aelteren Backends ohne das Feld", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue(base);
    render(<MemoryRouter><BillingTickCard /></MemoryRouter>);
    await screen.findByText("gesund");
    expect(screen.queryByTestId("awaiting-capacity")).toBeNull();
  });
});
