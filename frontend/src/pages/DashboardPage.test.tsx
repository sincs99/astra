// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";
import { resetCurrentUserCache } from "../hooks/useCurrentUser";
import { api, type Instance } from "../services/api";
import { makeOrder } from "../test/fixtures";

const customer = { id: 2, username: "bob", email: "b@x.de", is_admin: false };
const admin = { ...customer, id: 1, username: "root", is_admin: true };

const instance = {
  id: 1, uuid: "0f3a9c1e-aaaa", name: "Mein Server", status: "ready", role: "owner",
  memory: 512, disk: 1000, cpu: 100,
  connection: { host: "n1.example.com", port: 25565, address: "n1.example.com:25565" },
} as Instance;

function mount(state?: unknown) {
  return render(<MemoryRouter initialEntries={[{ pathname: "/", state }]}><DashboardPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", `tok-${Math.random()}`);
  resetCurrentUserCache();
  vi.spyOn(api, "getMyOrders").mockResolvedValue([]);
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("DashboardPage", () => {
  it("verweist Kunden ohne Server auf den Shop", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    mount();
    expect(await screen.findByText("Noch kein Server.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zum Shop" }).getAttribute("href")).toBe("/shop");
    expect(screen.getByText("Noch kein Server")).toBeTruthy();
    expect(screen.queryByText(/Admin-Bereich/)).toBeNull();
  });

  it("verweist Admins ohne Instances auf den Admin-Bereich", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(admin as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    mount();
    expect(await screen.findByText(/über den Admin-Bereich/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Zum Shop" })).toBeNull();
  });

  it("zeigt Admins die Karte mit offenen Bestellungen, Kunden nicht", async () => {
    const orders = vi.spyOn(api, "getAdminOrders").mockResolvedValue([]);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(admin as never);
    mount();
    expect(await screen.findByText(/Offene Bestellungen:/)).toBeTruthy();
    cleanup();
    orders.mockClear();
    localStorage.setItem("astra_access_token", "tok-kunde");
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    mount();
    await screen.findByRole("heading", { name: "Meine Server" });
    expect(screen.queryByText(/Offene Bestellungen:/)).toBeNull();
    expect(orders).not.toHaveBeenCalled();
  });

  it("zeigt Server mit Status und Verbindungsadresse", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([instance]);
    mount();
    expect(await screen.findByRole("link", { name: "Mein Server" })).toBeTruthy();
    expect(screen.getByText("n1.example.com:25565")).toBeTruthy();
    expect(screen.getByText("bereit")).toBeTruthy();
    expect(screen.getByText("1 Server · 0 läuft")).toBeTruthy();
  });

  it("zeigt die Meldung der vorherigen Seite (z.B. nach dem Löschen) als Toast", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    mount({ toast: 'Instance "Alt" wurde gelöscht.' });
    expect(await screen.findByText('Instance "Alt" wurde gelöscht.')).toBeTruthy();
  });

  it("zeigt bei einem Ladefehler eine Meldung und kann es erneut versuchen", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    const load = vi.spyOn(api, "getClientInstances")
      .mockRejectedValueOnce(new Error("Der Server ist nicht erreichbar."))
      .mockResolvedValue([instance]);
    mount();
    expect(await screen.findByText("Der Server ist nicht erreichbar.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByRole("link", { name: "Mein Server" })).toBeTruthy();
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  });

  describe("Karten und Hinweise", () => {
    const running = { ...instance, uuid: "u-run", name: "Freitagsrunde", container_state: "running", memory: 8192, disk: 20480 } as Instance;
    const stopped = { ...instance, uuid: "u-stop", name: "Factory 02", container_state: "offline" } as Instance;
    const soon = new Date(Date.now() + 3 * 86_400_000).toISOString();
    const later = new Date(Date.now() + 40 * 86_400_000).toISOString();

    beforeEach(() => {
      vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    });

    it("zaehlt laufende Server im Untertitel und zeigt Stop/Neustart nur bei laufenden, Start bei gestoppten", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([running, stopped]);
      mount();
      await screen.findByRole("link", { name: "Freitagsrunde" });
      expect(screen.getByText("2 Server · 1 laufen")).toBeTruthy();
      const runCard = screen.getByRole("article", { name: "Freitagsrunde" });
      expect(within(runCard).getByRole("button", { name: "Stop" })).toBeTruthy();
      expect(within(runCard).getByRole("button", { name: "Neustart" })).toBeTruthy();
      expect(within(runCard).getByText("8 GB")).toBeTruthy();
      const stopCard = screen.getByRole("article", { name: "Factory 02" });
      expect(within(stopCard).getByRole("button", { name: "Start" })).toBeTruthy();
      expect(within(stopCard).queryByRole("button", { name: "Stop" })).toBeNull();
    });

    it("sendet Stop an den Server und meldet das Ergebnis", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([running]);
      const power = vi.spyOn(api, "sendPowerAction").mockResolvedValue({ message: "Stopp gesendet" } as never);
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
      await waitFor(() => expect(power).toHaveBeenCalledWith("u-run", "stop"));
      expect(await screen.findByText("Stopp gesendet")).toBeTruthy();
    });

    it("zeigt Laufzeitende aus der Bestellung; bald faellig in Warnfarbe mit Verlaengern, spaeter ohne", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([running, stopped]);
      vi.spyOn(api, "getMyOrders").mockResolvedValue([
        makeOrder({ id: 1, uuid: "o1", status: "active", instance_uuid: "u-run", product_name: "Crew", current_period_end: later }),
        makeOrder({ id: 2, uuid: "o2", status: "active", instance_uuid: "u-stop", product_name: "Start", current_period_end: soon }),
      ]);
      mount();
      const runCard = await screen.findByRole("article", { name: "Freitagsrunde" });
      expect(within(runCard).getByText("Crew")).toBeTruthy();
      expect(within(runCard).queryByRole("link", { name: "Verlängern" })).toBeNull();
      const soonCard = screen.getByRole("article", { name: "Factory 02" });
      const ends = within(soonCard).getByText(/in 3 Tagen · /);
      expect(ends.className).toContain("text-warn");
      expect(within(soonCard).getByRole("link", { name: "Verlängern" }).getAttribute("href")).toBe("/orders");
    });

    it("erfindet keine Zeilen ohne Daten (keine Bestellung, keine Adresse)", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([{ ...instance, connection: null, memory: 0, disk: 0 } as Instance]);
      mount();
      const card = await screen.findByRole("article", { name: "Mein Server" });
      expect(within(card).queryByText("Läuft bis")).toBeNull();
      expect(within(card).queryByText("RAM")).toBeNull();
      expect(within(card).getByText("Adresse nach der Einrichtung")).toBeTruthy();
    });

    it("zeigt bei Ueberweisung ein Hinweisbanner und eine Karte fuer die Bestellung ohne Server", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([running]);
      vi.spyOn(api, "getMyOrders").mockResolvedValue([
        makeOrder({ id: 418, uuid: "o-pending", status: "pending_payment", instance_name: "Valheim Clan", product_name: "Start", price_cents: 1490 }),
      ]);
      mount();
      expect(await screen.findByText(/Die Überweisung für Valheim Clan ist noch nicht eingegangen/)).toBeTruthy();
      expect(screen.getAllByRole("link", { name: "Zahlungsdaten anzeigen" })[0].getAttribute("href")).toBe("/orders");
      const card = screen.getByRole("article", { name: "Valheim Clan" });
      expect(within(card).getByText("#418")).toBeTruthy();
      expect(within(card).getByText(/14,90/)).toBeTruthy();
      expect(within(card).getByText("Adresse nach Zahlungseingang")).toBeTruthy();
    });

    it("bietet bei Online-Zahlung 'Jetzt mit Karte bezahlen' und storniert nach Bestaetigung", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
      vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
      vi.spyOn(api, "getMyOrders").mockResolvedValue([makeOrder({ uuid: "o-pending", status: "pending_payment", instance_name: "Valheim Clan" })]);
      const cancel = vi.spyOn(api, "cancelOrder").mockResolvedValue({ message: "ok" } as never);
      vi.spyOn(window, "confirm").mockReturnValue(true);
      mount();
      expect((await screen.findAllByRole("button", { name: "Jetzt mit Karte bezahlen" })).length).toBe(2);
      fireEvent.click(screen.getByRole("button", { name: "Stornieren" }));
      await waitFor(() => expect(cancel).toHaveBeenCalledWith("o-pending"));
    });

    it("zeigt bezahlte Bestellungen ohne Server als wartend, ohne Bezahl-Aktion", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
      vi.spyOn(api, "getMyOrders").mockResolvedValue([makeOrder({ status: "awaiting_provisioning", instance_name: "Wartet" })]);
      mount();
      const card = await screen.findByRole("article", { name: "Wartet" });
      expect(within(card).getByText(/sobald Platz frei ist/)).toBeTruthy();
      expect(within(card).queryByRole("link", { name: "Zahlungsdaten anzeigen" })).toBeNull();
      expect(screen.queryByText(/Überweisung für/)).toBeNull();
    });

    it("blendet die Fussnote bei leerem Dashboard aus", async () => {
      vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
      mount();
      await screen.findByText("Noch kein Server.");
      expect(screen.queryByText(/Karenzzeit/)).toBeNull();
    });
  });
});
