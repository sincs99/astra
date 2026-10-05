// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShopPage } from "./ShopPage";
import { api } from "../services/api";
import { resetCurrentUserCache } from "../hooks/useCurrentUser";
import { OPERATOR } from "../legal/operator";
import { makeOrder, makeProduct } from "../test/fixtures";

// Oeffentliche Produktdaten: ohne interne Felder (kein Blueprint, kein is_active)
const starter = makeProduct({ blueprint_id: undefined, is_active: undefined, max_instances_per_user: undefined });
const crew = makeProduct({ id: 6, name: "Crew", price_cents: 1999, description: null, blueprint_id: undefined, is_active: undefined, resources: { memory: 8192, swap: 0, disk: 51200, io: 500, cpu: 400 } });
const plain = (s: string | null) => (s ?? "").replace(/[\u00a0\u202f]/g, " ");

function mount(path = "/shop") {
  return render(<MemoryRouter initialEntries={[path]}><ShopPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetCurrentUserCache();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
});
afterEach(() => { cleanup(); localStorage.clear(); OPERATOR.jurisdiction = "DE"; });

describe("ShopPage", () => {
  it("zeigt nur bei Betreiber in der Schweiz den Hinweis 'Leistung beginnt sofort, kein Widerrufsrecht'", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    mount();
    await screen.findByRole("radiogroup", { name: "Paket" });
    expect(screen.queryByText(/kein allgemeines Widerrufsrecht/)).toBeNull();
    cleanup();
    OPERATOR.jurisdiction = "CH";
    mount();
    const note = await screen.findByRole("note");
    expect(note.textContent).toMatch(/Die Leistung beginnt sofort nach Bezahlung/);
    expect(note.textContent).toMatch(/kein allgemeines Widerrufsrecht/);
    expect(within(note).getByRole("link", { name: "AGB" }).getAttribute("href")).toBe("/agb");
  });

  it("zeigt Pakete als Auswahlkarten mit Preis und Ressourcen; das erste ist vorgewaehlt", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter, crew]);
    mount();
    const group = await screen.findByRole("radiogroup", { name: "Paket" });
    const radios = within(group).getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([true, false]);
    const card = radios[0].closest("label") as HTMLElement;
    expect(plain(within(card).getByText(/€/).textContent)).toBe("9,99 €");
    expect(within(card).getByText("2 GB RAM · 150 % CPU · 10 GB")).toBeTruthy();
    expect(within(card).getByText("30 Tage")).toBeTruthy();
    expect(within(card).getByText("Für kleine Server")).toBeTruthy();
  });

  it("zeigt den Blueprint-Namen (Spiel), sobald das Backend ihn liefert", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([{ ...starter, blueprint_name: "Minecraft Vanilla" }]);
    mount();
    expect((await screen.findAllByText("Minecraft Vanilla")).length).toBeGreaterThan(0);
    expect(within(screen.getByRole("complementary", { name: "Zusammenfassung" })).getByText("Minecraft Vanilla")).toBeTruthy();
  });

  it("wählt über ?plan= das verlinkte Paket vor (Link von der Landingpage)", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter, crew]);
    mount("/shop?plan=6");
    const group = await screen.findByRole("radiogroup", { name: "Paket" });
    const radios = within(group).getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([false, true]);
  });

  it("ignoriert ein unbekanntes ?plan= und wählt das erste Paket", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter, crew]);
    mount("/shop?plan=999");
    const radios = within(await screen.findByRole("radiogroup", { name: "Paket" })).getAllByRole("radio") as HTMLInputElement[];
    expect(radios.map((r) => r.checked)).toEqual([true, false]);
  });

  it("aktualisiert die Zusammenfassung bei Paket- und Namenswahl", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter, crew]);
    mount();
    await screen.findByRole("radiogroup", { name: "Paket" });
    const summary = screen.getByRole("complementary", { name: "Zusammenfassung" });
    expect(within(summary).getByText("Starter")).toBeTruthy();
    expect(within(summary).getByText("wird vergeben")).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: /Crew/ }));
    fireEvent.change(screen.getByLabelText("Servername (optional)"), { target: { value: "Freitagsrunde" } });
    expect(within(summary).getByText("Crew")).toBeTruthy();
    expect(within(summary).getByText("Freitagsrunde")).toBeTruthy();
    expect(plain(within(summary).getByText(/19,99/).textContent)).toBe("19,99 €");
    expect(within(summary).getByText("30 Tage, verlängerbar")).toBeTruthy();
  });

  it("zeigt ausgeloggt den Shop mit Link zum Login und Rückkehr zum Shop", async () => {
    localStorage.clear();
    const me = vi.mocked(api.getCurrentUser);
    me.mockClear();
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    mount();
    await screen.findByRole("radiogroup", { name: "Paket" });
    expect(screen.getByRole("link", { name: "Anmelden und bestellen" }).getAttribute("href")).toBe("/login?redirect=%2Fshop");
    expect(screen.queryByRole("button", { name: "Verbindlich bestellen" })).toBeNull();
    expect(screen.getByRole("link", { name: "Registrieren" })).toBeTruthy();
    expect(me).not.toHaveBeenCalled();
  });

  it("bestellt per Ueberweisung mit Servername und weist auf die Freischaltung nach Zahlung hin", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter, crew]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ status: "pending_payment" }));
    mount();
    fireEvent.click(await screen.findByRole("radio", { name: /Crew/ }));
    fireEvent.change(screen.getByLabelText("Servername (optional)"), { target: { value: "  Mein Server " } });
    expect(screen.getByText("Überweisung")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Verbindlich bestellen" }));
    await waitFor(() => expect(order).toHaveBeenCalledWith(6, "Mein Server"));
    expect(await screen.findByText(/Bestellung eingegangen/)).toBeTruthy();
    expect(screen.getByText(/nach Zahlungseingang freigeschaltet/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zu meinen Bestellungen" }).getAttribute("href")).toBe("/orders");
  });

  it("erlaubt eine Bestellung ohne Servername (optional)", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder());
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Verbindlich bestellen" }));
    await waitFor(() => expect(order).toHaveBeenCalledWith(5, undefined));
  });

  it("leitet bei Online-Zahlung nach der Bestellung direkt zum Checkout weiter", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
    vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ uuid: "ord-1" }));
    const checkout = vi.spyOn(api, "createCheckout").mockResolvedValue({ checkout_url: "https://checkout.stripe.com/pay/x" } as never);
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    mount();
    expect(await screen.findByText("Karte, Apple Pay, Google Pay")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Weiter zur Zahlung" }));
    await waitFor(() => expect(checkout).toHaveBeenCalledWith("ord-1"));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/pay/x"));
    vi.unstubAllGlobals();
  });

  it("faellt bei fehlgeschlagenem Checkout auf die Bestaetigung mit Link zu den Bestellungen zurueck", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
    vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ uuid: "ord-1" }));
    vi.spyOn(api, "createCheckout").mockRejectedValue(new Error("Zahlungsanbieter nicht erreichbar"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Weiter zur Zahlung" }));
    expect((await screen.findAllByText("Zahlungsanbieter nicht erreichbar")).length).toBeGreaterThan(0);
    expect(await screen.findByText(/Bestellung eingegangen/)).toBeTruthy();
  });

  it("bietet kostenlose Pakete ohne Zahlungsschritt an und meldet die Bereitstellung", async () => {
    const free = makeProduct({ id: 7, name: "Gratis", price_cents: 0, blueprint_id: undefined, is_active: undefined });
    vi.spyOn(api, "getShopProducts").mockResolvedValue([free]);
    vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
    const order = vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ status: "active" }));
    const checkout = vi.spyOn(api, "createCheckout");
    mount();
    expect(await screen.findByText("Dieses Paket ist kostenlos, es ist keine Zahlung nötig.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Kostenlos bestellen" }));
    expect(await screen.findByText(/Dein Server wurde bereitgestellt/)).toBeTruthy();
    expect(order).toHaveBeenCalledWith(7, undefined);
    expect(checkout).not.toHaveBeenCalled();
  });

  it("meldet fehlenden Platz bei bezahlter Bereitstellung", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    vi.spyOn(api, "createOrder").mockResolvedValue(makeOrder({ status: "awaiting_provisioning" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText(/sobald Platz frei ist/)).toBeTruthy();
  });

  it("zeigt Fehler der Bestellung (z.B. zu viele offene Bestellungen) und laesst das Formular offen", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([starter]);
    vi.spyOn(api, "createOrder").mockRejectedValue(new Error("Zu viele offene Bestellungen (5) – bitte erst bezahlen oder stornieren"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Verbindlich bestellen" }));
    expect(await screen.findByText(/Zu viele offene Bestellungen/)).toBeTruthy();
    expect(screen.getByLabelText("Servername (optional)")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Verbindlich bestellen" }) as HTMLButtonElement).disabled).toBe(false);
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
