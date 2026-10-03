// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OrdersPage } from "./OrdersPage";
import { api, type Order } from "../services/api";

const base = { user_id: 2, created_at: "2026-10-01T10:00:00Z", cancel_at_period_end: false, instance_id: null, current_period_end: null };
const orders = [
  { ...base, id: 1, product_id: 5, product_name: "Starter", name: "Mein Server", status: "active", instance_id: 42, current_period_end: "2026-11-15T00:00:00Z" },
  { ...base, id: 2, product_id: 5, product_name: "Starter", status: "pending_payment" },
  { ...base, id: 3, product_id: 6, status: "cancelled" },
  { ...base, id: 4, product_id: 5, product_name: "Starter", status: "active", cancel_at_period_end: true },
] as Order[];

function mount() {
  return render(<MemoryRouter><OrdersPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
  vi.spyOn(api, "getClientInstances").mockResolvedValue([{ id: 42, uuid: "abc-123" }] as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("OrdersPage", () => {
  it("zeigt Status-Badges, Laufzeitende und Link zur Instance", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue(orders);
    mount();
    const rows = await screen.findAllByRole("row");
    const first = within(rows[1]);
    expect(first.getByText("Starter")).toBeTruthy();
    expect(first.getByLabelText("aktiv")).toBeTruthy();
    expect(first.getByText("15.11.2026")).toBeTruthy();
    expect(first.getByRole("link", { name: "Zum Server" }).getAttribute("href")).toBe("/instances/abc-123");
    expect(within(rows[2]).getByLabelText("Zahlung ausstehend")).toBeTruthy();
    expect(within(rows[3]).getByText("Produkt #6")).toBeTruthy();
    expect(within(rows[3]).getByLabelText("gekündigt")).toBeTruthy();
  });

  it("kuendigt zum Laufzeitende und storniert unbezahlte Bestellungen", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue(orders);
    const cancel = vi.spyOn(api, "cancelOrder").mockResolvedValue({} as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith(1));
    fireEvent.click(await screen.findByRole("button", { name: "Stornieren" }));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith(2));
  });

  it("bietet bei bereits gekuendigten oder beendeten Bestellungen keine Kuendigung an", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([orders[2], orders[3]]);
    mount();
    await screen.findByText("gekündigt zum Laufzeitende");
    expect(screen.queryByRole("button", { name: /Kündigen|Stornieren/ })).toBeNull();
  });

  it("zeigt den Leerzustand mit Link zum Shop und Fehler der Kuendigung", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([]);
    mount();
    expect(await screen.findByText(/noch keine Bestellungen/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zum Shop" }).getAttribute("href")).toBe("/shop");
  });

  it("zeigt den Fehlertext, wenn das Kuendigen scheitert", async () => {
    vi.spyOn(api, "getMyOrders").mockResolvedValue([orders[0]]);
    vi.spyOn(api, "cancelOrder").mockRejectedValue(new Error("Bestellung bereits beendet"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" }));
    expect(await screen.findByText("Bestellung bereits beendet")).toBeTruthy();
  });
});
