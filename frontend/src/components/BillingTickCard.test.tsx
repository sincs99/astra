// @vitest-environment jsdom
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
    render(<BillingTickCard />);
    expect(await screen.findByText("gesund")).toBeTruthy();
    expect(screen.getByText("Letzter Lauf: vor 3 Min.")).toBeTruthy();
    expect(screen.getByText("aktiv: 4")).toBeTruthy();
    expect(screen.queryByText(/cancelled|storniert: 0/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warnt deutlich, wenn der Tick nicht laeuft", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue({ ...base, healthy: false, last_run_at: null, age_seconds: null, orders_needing_tick: 2 });
    render(<BillingTickCard />);
    expect((await screen.findByRole("alert")).textContent).toContain("Container billing prüfen");
    expect(screen.getByText("Letzter Lauf: noch nie")).toBeTruthy();
  });

  it("blendet sich bei Fehler (z.B. 404) still aus", async () => {
    vi.spyOn(api, "getBillingStatus").mockRejectedValue(new Error("404"));
    const { container } = render(<BillingTickCard />);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });

  it("blendet sich im Dashboard-Modus aus, solange alles gesund ist", async () => {
    vi.spyOn(api, "getBillingStatus").mockResolvedValue(base);
    const { container } = render(<BillingTickCard onlyWhenUnhealthy />);
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });
});
