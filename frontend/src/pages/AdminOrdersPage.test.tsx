// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminOrdersPage } from "./AdminOrdersPage";
import { api } from "../services/api";
import { makeOrder } from "../test/fixtures";

const pending = makeOrder({ id: 7, uuid: "o-7", status: "pending_payment", user_id: 2, username: "bob" });
const active = makeOrder({ id: 8, uuid: "o-8", status: "active", user_id: 2, username: "bob", instance_uuid: "0f3a9c1e-ffff", payment_reference: "ÜW-123" });
const awaiting = makeOrder({ id: 9, uuid: "o-9", status: "awaiting_provisioning", user_id: 3, username: "eve" });

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
    expect(screen.getByText("Ref: ÜW-123")).toBeTruthy();
    expect(list).toHaveBeenLastCalledWith("");
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "awaiting_provisioning" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith("awaiting_provisioning"));
  });

  it("bietet je Status die passende Aktion", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending, active, awaiting]);
    mount();
    await screen.findByText("eve");
    expect(screen.getAllByRole("button", { name: "Als bezahlt markieren" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Erneut bereitstellen" })).toHaveLength(1);
    expect(screen.getByText("0f3a9c1e")).toBeTruthy();
  });

  it("markiert mit optionaler Zahlungsreferenz als bezahlt (uuid im Pfad) und laedt neu", async () => {
    const list = vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending]);
    const paid = vi.spyOn(api, "markOrderPaid").mockResolvedValue(makeOrder({ status: "active" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Als bezahlt markieren" }));
    fireEvent.change(screen.getByLabelText("Zahlungsreferenz (optional)"), { target: { value: " ÜW-42 " } });
    fireEvent.click(screen.getByRole("button", { name: "Bezahlt bestätigen" }));
    await waitFor(() => expect(paid).toHaveBeenCalledWith("o-7", "ÜW-42"));
    expect(await screen.findByText(/Bestellung #7 als bezahlt markiert/)).toBeTruthy();
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("markiert ohne Referenz, wenn das Feld leer bleibt", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending]);
    const paid = vi.spyOn(api, "markOrderPaid").mockResolvedValue(makeOrder({ status: "active" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Als bezahlt markieren" }));
    fireEvent.click(screen.getByRole("button", { name: "Bezahlt bestätigen" }));
    await waitFor(() => expect(paid).toHaveBeenCalledWith("o-7", undefined));
  });

  it("stellt eine wartende Bestellung erneut bereit", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([awaiting]);
    const paid = vi.spyOn(api, "markOrderPaid").mockResolvedValue(makeOrder({ status: "active" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Erneut bereitstellen" }));
    await waitFor(() => expect(paid).toHaveBeenCalledWith("o-9", undefined));
    expect(await screen.findByText(/Bestellung #9 wurde bereitgestellt/)).toBeTruthy();
  });

  it("warnt, wenn nach der Zahlung weiter kein Platz frei ist", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([pending]);
    vi.spyOn(api, "markOrderPaid").mockResolvedValue(makeOrder({ status: "awaiting_provisioning" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Als bezahlt markieren" }));
    fireEvent.click(screen.getByRole("button", { name: "Bezahlt bestätigen" }));
    expect(await screen.findByText(/noch kein Platz frei/)).toBeTruthy();
  });

  it("zeigt den Fehlertext des Backends bei fehlender Kapazitaet", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([awaiting]);
    vi.spyOn(api, "markOrderPaid").mockRejectedValue(new Error("Kein Agent mit genug Kapazität: memory (frei: 256 MB)"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Erneut bereitstellen" }));
    expect(await screen.findByText(/Kein Agent mit genug Kapazität/)).toBeTruthy();
  });
});
