// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OrdersPage } from "./OrdersPage";
import { api } from "../services/api";
import { makeOrder } from "../test/fixtures";

const active = makeOrder({
  id: 1, uuid: "o-1", status: "active", current_period_end: "2026-11-15T00:00:00Z",
  instance_uuid: "inst-abc", instance_status: "ready",
  connection: { host: "n1.example.com", ip: "0.0.0.0", port: 25565, address: "n1.example.com:25565" },
});
const pending = makeOrder({ id: 2, uuid: "o-2", status: "pending_payment", instance_name: "Offen" });
const awaiting = makeOrder({ id: 3, uuid: "o-3", status: "awaiting_provisioning", instance_name: "Wartet" });
const cancelled = makeOrder({ id: 4, uuid: "o-4", status: "cancelled", product_name: null });
const endingActive = makeOrder({
  id: 5, uuid: "o-5", status: "active", cancel_at_period_end: true,
  current_period_end: "2026-11-30T00:00:00", scheduled_deletion_at: "2026-11-30T00:00:00",
});
const overdue = makeOrder({
  id: 6, uuid: "o-6", status: "past_due", past_due_at: "2026-10-01T08:30:00",
  scheduled_deletion_at: "2026-10-08T08:30:00", current_period_end: "2026-09-30T00:00:00",
});

function mount() {
  return render(<MemoryRouter><OrdersPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("OrdersPage", () => {
  it("zeigt Status, Laufzeitende, Server-Link und Verbindungsadresse", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending, awaiting, cancelled]);
    mount();
    const rows = await screen.findAllByRole("row");
    const first = within(rows[1]);
    expect(first.getByLabelText("aktiv")).toBeTruthy();
    expect(first.getByText("15.11.2026")).toBeTruthy();
    expect(first.getByRole("link", { name: "Zum Server" }).getAttribute("href")).toBe("/instances/inst-abc");
    expect(first.getByText("n1.example.com:25565")).toBeTruthy();
    expect(within(rows[2]).getByLabelText("Zahlung ausstehend")).toBeTruthy();
    expect(within(rows[3]).getByLabelText("wird bereitgestellt")).toBeTruthy();
    expect(within(rows[3]).getByText("Bezahlt, wird bereitgestellt")).toBeTruthy();
    expect(within(rows[4]).getByText("Produkt #5")).toBeTruthy();
    expect(within(rows[4]).getByLabelText("gekündigt")).toBeTruthy();
  });

  it("unterscheidet Stornieren (sofort) und Kuendigen zum Laufzeitende, beides ueber die uuid", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending]);
    const cancel = vi.spyOn(api, "cancelOrder").mockResolvedValue(active);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith("o-1"));
    expect(await screen.findByText(/Dein Server läuft noch bis 15\.11\.2026/)).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: "Stornieren" }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith("o-2"));
    expect(await screen.findByText("Bestellung storniert.")).toBeTruthy();
  });

  it("bietet bei bereits gekuendigten, beendeten oder in Bereitstellung befindlichen Bestellungen keine Kuendigung an", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([cancelled, endingActive, awaiting]);
    mount();
    await screen.findByText(/Läuft bis .*, wird dann gelöscht/);
    expect(screen.queryByRole("button", { name: /Kündigen|Stornieren/ })).toBeNull();
  });

  it("warnt bei ueberfaelligen Bestellungen deutlich vor Sperre und Loeschung", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([overdue]);
    mount();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Gesperrt seit 1\.10\.2026/);
    expect(alert.textContent).toMatch(/Server wird am 8\.10\.2026 gelöscht/);
  });

  it("zeigt den Leerzustand mit Link zum Shop", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([]);
    mount();
    expect(await screen.findByText(/noch keine Bestellungen/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zum Shop" }).getAttribute("href")).toBe("/shop");
  });

  it("zeigt den Fehlertext, wenn das Kuendigen scheitert", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([active]);
    vi.spyOn(api, "cancelOrder").mockRejectedValue(new Error("Bestellung im Status 'expired' kann nicht storniert werden"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" }));
    expect(await screen.findByText(/kann nicht storniert werden/)).toBeTruthy();
  });
});
