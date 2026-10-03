// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OpenOrdersCard } from "./OpenOrdersCard";
import { api } from "../services/api";
import { makeOrder } from "../test/fixtures";

beforeEach(() => vi.restoreAllMocks());
afterEach(cleanup);

const mount = () => render(<MemoryRouter><OpenOrdersCard /></MemoryRouter>);

describe("OpenOrdersCard", () => {
  it("zaehlt beide offenen Status und verlinkt auf die gefilterte Bestellliste", async () => {
    const list = vi.spyOn(api, "getAdminOrders").mockImplementation(async (status) =>
      status === "pending_payment" ? [makeOrder(), makeOrder({ id: 2, uuid: "b" })] : [makeOrder({ id: 3, uuid: "c", status: "awaiting_provisioning" })]);
    mount();
    expect((await screen.findByTestId("open-orders-total")).textContent).toBe("3");
    expect(screen.getByRole("link", { name: "2 warten auf Zahlung" }).getAttribute("href")).toBe("/admin/orders?status=pending_payment");
    expect(screen.getByRole("link", { name: "1 bezahlt, warten auf Bereitstellung" }).getAttribute("href"))
      .toBe("/admin/orders?status=awaiting_provisioning");
    expect(list).toHaveBeenCalledWith("pending_payment");
    expect(list).toHaveBeenCalledWith("awaiting_provisioning");
  });

  it("zeigt bei 0 offenen Bestellungen eine ruhige Karte ohne Links", async () => {
    vi.spyOn(api, "getAdminOrders").mockResolvedValue([]);
    mount();
    expect(await screen.findByText("Keine offenen Bestellungen.")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("blendet sich bei einem Fehler still aus", async () => {
    vi.spyOn(api, "getAdminOrders").mockRejectedValue(new Error("boom"));
    const { container } = mount();
    await Promise.resolve();
    await new Promise((r) => setTimeout(r, 0));
    expect(container.textContent).toBe("");
  });
});
