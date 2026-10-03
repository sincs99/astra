// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShopPage } from "./ShopPage";
import { api, type Product } from "../services/api";

const product = {
  id: 5, name: "Starter", description: "Für kleine Server", blueprint_id: 1, blueprint_name: "Minecraft Vanilla",
  memory: 2048, disk: 10240, cpu: 150, swap: 0, io: 500, price_cents: 999, currency: "EUR",
  billing_period_days: 30, active: true, max_instances_per_user: null,
} as Product;

const plain = (s: string | null) => (s ?? "").replace(/ | /g, " ");

function mount() {
  return render(<MemoryRouter><ShopPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("ShopPage", () => {
  it("zeigt Produkte als Karten mit Preis, Ressourcen und Blueprint", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    mount();
    const card = (await screen.findByRole("article", { name: "Starter" }));
    expect(plain(within(card).getByText(/€/).textContent)).toBe("9,99 € / 30 Tage");
    expect(within(card).getByText("2048 MB RAM")).toBeTruthy();
    expect(within(card).getByText("10240 MB Disk")).toBeTruthy();
    expect(within(card).getByText("150% CPU")).toBeTruthy();
    expect(within(card).getByText("Minecraft Vanilla")).toBeTruthy();
  });

  it("bestellt mit Servername und zeigt den Hinweis zur Freischaltung", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue({ id: 1, status: "pending_payment" } as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Namen/);
    expect(order).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Servername"), { target: { value: "  Mein Server " } });
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    await waitFor(() => expect(order).toHaveBeenCalledWith(5, "Mein Server"));
    expect(await screen.findByText(/Bestellung eingegangen/)).toBeTruthy();
    expect(screen.getByText(/nach Zahlungseingang freigeschaltet/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zu meinen Bestellungen" }).getAttribute("href")).toBe("/orders");
  });

  it("zeigt Fehler der Bestellung (z.B. Limit erreicht) und laesst das Formular offen", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    vi.spyOn(api, "createOrder").mockRejectedValue(new Error("Maximale Anzahl Instances erreicht"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.change(screen.getByLabelText("Servername"), { target: { value: "S" } });
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText("Maximale Anzahl Instances erreicht")).toBeTruthy();
    expect(screen.getByLabelText("Servername")).toBeTruthy();
  });

  it("zeigt Leer- und Fehlerzustand", async () => {
    const load = vi.spyOn(api, "getShopProducts").mockRejectedValueOnce(new Error("Server nicht erreichbar")).mockResolvedValue([]);
    mount();
    expect(await screen.findByText("Server nicht erreichbar")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText(/keine Produkte verfügbar/)).toBeTruthy();
    expect(load).toHaveBeenCalledTimes(2);
  });
});
