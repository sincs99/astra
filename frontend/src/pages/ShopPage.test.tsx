// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShopPage } from "./ShopPage";
import { api } from "../services/api";
import { makeOrder, makeProduct } from "../test/fixtures";

// Oeffentliche Produktdaten: ohne interne Felder (kein Blueprint, kein is_active)
const product = makeProduct({ blueprint_id: undefined, is_active: undefined, max_instances_per_user: undefined });
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
  it("zeigt Produkte als Karten mit Preis und Ressourcen", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    mount();
    const card = await screen.findByRole("article", { name: "Starter" });
    expect(plain(within(card).getByText(/€/).textContent)).toBe("9,99 € / 30 Tage");
    expect(within(card).getByText("2048 MB RAM")).toBeTruthy();
    expect(within(card).getByText("10240 MB Disk")).toBeTruthy();
    expect(within(card).getByText("150% CPU")).toBeTruthy();
    expect(within(card).getByText("Für kleine Server")).toBeTruthy();
  });

  it("zeigt den Blueprint-Namen, sobald das Backend ihn liefert", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([{ ...product, blueprint_name: "Minecraft Vanilla" }]);
    mount();
    expect(await screen.findByText("Minecraft Vanilla")).toBeTruthy();
  });

  it("zeigt den Shop auch ausgeloggt und fuehrt zum Login mit Rückkehr zum Shop", async () => {
    localStorage.clear();
    const me = vi.mocked(api.getCurrentUser);
    me.mockClear();
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    mount();
    const card = await screen.findByRole("article", { name: "Starter" });
    const login = within(card).getByRole("link", { name: /bestellen/ });
    expect(login.getAttribute("href")).toBe("/login?redirect=%2Fshop");
    expect(within(card).queryByRole("button", { name: /bestellen/ })).toBeNull();
    expect(screen.getByRole("link", { name: "Anmelden" }).getAttribute("href")).toBe("/login?redirect=%2F");
    expect(screen.getByRole("link", { name: "Registrieren" })).toBeTruthy();
    expect(me).not.toHaveBeenCalled();
  });

  it("bestellt mit Servername und weist auf die Freischaltung nach Zahlung hin", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ status: "pending_payment" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.change(screen.getByLabelText("Servername (optional)"), { target: { value: "  Mein Server " } });
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    await waitFor(() => expect(order).toHaveBeenCalledWith(5, "Mein Server"));
    expect(await screen.findByText(/Bestellung eingegangen/)).toBeTruthy();
    expect(screen.getByText(/nach Zahlungseingang freigeschaltet/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zu meinen Bestellungen" }).getAttribute("href")).toBe("/orders");
  });

  it("erlaubt eine Bestellung ohne Servername (optional)", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder());
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    await waitFor(() => expect(order).toHaveBeenCalledWith(5, undefined));
  });

  it("meldet bei kostenlosen Produkten die sofortige Bereitstellung bzw. fehlenden Platz", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ status: "active" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText(/Dein Server wurde bereitgestellt/)).toBeTruthy();

    order.mockResolvedValue(makeOrder({ status: "awaiting_provisioning" }));
    fireEvent.click(screen.getByRole("button", { name: "Starter bestellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText(/sobald Platz frei ist/)).toBeTruthy();
  });

  it("zeigt Fehler der Bestellung (z.B. zu viele offene Bestellungen) und laesst das Formular offen", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([product]);
    vi.spyOn(api, "createOrder").mockRejectedValue(new Error("Zu viele offene Bestellungen (5) – bitte erst bezahlen oder stornieren"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Starter bestellen" }));
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText(/Zu viele offene Bestellungen/)).toBeTruthy();
    expect(screen.getByLabelText("Servername (optional)")).toBeTruthy();
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
