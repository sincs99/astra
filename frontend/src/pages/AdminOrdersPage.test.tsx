// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminOrdersPage } from "./AdminOrdersPage";
import { api, type Order } from "../services/api";

const pending = { id: 7, user_id: 2, username: "bob", product_id: 5, product_name: "Starter", name: "Srv", status: "pending_payment",
  instance_id: null, current_period_end: null, created_at: null } as Order;
const active = { ...pending, id: 8, status: "active", instance_id: 3, instance_uuid: "0f3a9c1e-ffff" } as Order;

function mount() {
  return render(<MemoryRouter><AdminOrdersPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("AdminOrdersPage", () => {
  it("listet Bestellungen und filtert nach Status", async () => {
    const list = vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending, active]);
    mount();
    expect(await screen.findAllByText("bob")).toHaveLength(2);
    expect(list).toHaveBeenLastCalledWith("");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "pending_payment" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith("pending_payment"));
  });

  it("bietet 'Als bezahlt markieren' nur fuer offene Bestellungen an", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending, active]);
    mount();
    await screen.findAllByText("bob");
    expect(screen.getAllByRole("button", { name: "Als bezahlt markieren" })).toHaveLength(1);
    expect(screen.getByText("0f3a9c1e")).toBeTruthy();
  });

  it("markiert als bezahlt und laedt neu", async () => {
    const list = vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending]);
    const paid = vi.spyOn(api, "markOrderPaid").mockResolvedValue({} as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Als bezahlt markieren" }));
    await waitFor(() => expect(paid).toHaveBeenCalledWith(7));
    expect(await screen.findByText(/Bestellung #7 als bezahlt markiert/)).toBeTruthy();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("zeigt den 409-Text bei fehlender Kapazitaet", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending]);
    vi.spyOn(api, "markOrderPaid").mockRejectedValue(new Error("Kein Agent mit genug Kapazität: memory (frei: 256 MB)"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Als bezahlt markieren" }));
    expect(await screen.findByText(/Kein Agent mit genug Kapazität/)).toBeTruthy();
  });
});
