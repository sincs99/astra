// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LandingPage } from "./LandingPage";
import { api } from "../services/api";
import { makeProduct } from "../test/fixtures";

const start = makeProduct({ id: 1, name: "Start", description: "Für kleine Runden", price_cents: 990, blueprint_name: "Minecraft" });
const crew = makeProduct({ id: 2, name: "Crew", description: null, price_cents: 1990, blueprint_name: "Valheim", resources: { memory: 8192, swap: 0, disk: 51200, io: 500, cpu: 400 } });
const plain = (s: string | null) => (s ?? "").replace(/[  ]/g, " ");

const mount = () => render(<MemoryRouter><LandingPage /></MemoryRouter>);

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
});
afterEach(cleanup);

describe("LandingPage", () => {
  it("zeigt Überschrift, Pakete aus der API mit Preis/Ressourcen und führt zur Bestellung mit Vorauswahl", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([start, crew]);
    mount();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/Dein Game-Server/);
    const card = await screen.findByRole("article", { name: "Start" });
    expect(plain(within(card).getByText(/9,99|9,90/).textContent)).toMatch(/€/);
    expect(within(card).getByText("2 GB RAM · 150 % CPU")).toBeTruthy();
    expect(within(card).getByText("10 GB Speicher")).toBeTruthy();
    expect(within(card).getByText("Für kleine Runden")).toBeTruthy();
    expect(within(card).getByRole("link", { name: "Jetzt bestellen: Start" }).getAttribute("href")).toBe("/shop?plan=1");
    expect(within(screen.getByRole("article", { name: "Crew" })).getByRole("link", { name: /Crew/ }).getAttribute("href")).toBe("/shop?plan=2");
  });

  it("leitet Anmelden auf /login und zeigt Rechtslinks", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([start]);
    mount();
    await screen.findByRole("article", { name: "Start" });
    expect(screen.getAllByRole("link", { name: "Anmelden" })[0].getAttribute("href")).toBe("/login");
    expect(screen.getByRole("link", { name: "Impressum" }).getAttribute("href")).toBe("/impressum");
    expect(screen.getByRole("link", { name: "Datenschutz" }).getAttribute("href")).toBe("/datenschutz");
    expect(screen.getByRole("link", { name: "AGB" }).getAttribute("href")).toBe("/agb");
  });

  it("leitet die Spieleliste aus den Blueprint-Namen der Pakete ab und blendet sie sonst aus", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([start, crew]);
    const first = mount();
    const games = await screen.findByRole("heading", { name: "Unterstützte Spiele" });
    const list = games.closest("section")!.querySelector("ul")!;
    expect(within(list as HTMLElement).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["MIMinecraft", "VAValheim"]);
    expect(screen.getAllByRole("link", { name: "Spiele" }).length).toBeGreaterThan(0);
    first.unmount();
    vi.spyOn(api, "getShopProducts").mockResolvedValue([{ ...start, blueprint_name: null }]);
    mount();
    await screen.findByRole("article", { name: "Start" });
    expect(screen.queryByRole("heading", { name: "Unterstützte Spiele" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Spiele" })).toBeNull();
  });

  it("nennt den Zahlungsweg passend zur Konfiguration", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([start]);
    const first = mount();
    expect(await screen.findByText("Bezahlung per Überweisung")).toBeTruthy();
    first.unmount();
    vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
    mount();
    expect(await screen.findByText("Bezahlung per Karte")).toBeTruthy();
    expect(screen.getByText(/Per Karte in Sekunden/)).toBeTruthy();
  });

  it("zeigt bei Ladefehler eine Meldung mit erneutem Versuch und bei leerem Angebot einen Hinweis", async () => {
    const load = vi.spyOn(api, "getShopProducts").mockRejectedValueOnce(new Error("x")).mockResolvedValue([]);
    mount();
    expect((await screen.findByRole("alert")).textContent).toContain("Die Pakete konnten nicht geladen werden.");
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("Aktuell sind keine Pakete verfügbar.")).toBeTruthy();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("öffnet auf dem Handy das Menü mit den Anker-Links", async () => {
    vi.spyOn(api, "getShopProducts").mockResolvedValue([start]);
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Menü" }));
    const menu = document.getElementById("lp-menu")!;
    expect(within(menu).getByRole("link", { name: "Pakete" }).getAttribute("href")).toBe("#pakete");
    expect(within(menu).getByRole("link", { name: "So funktioniert’s" })).toBeTruthy();
  });
});
