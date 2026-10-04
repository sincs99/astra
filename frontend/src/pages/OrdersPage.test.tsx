// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OrdersPage } from "./OrdersPage";
import { api, ApiError } from "../services/api";
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

function mount(path = "/orders") {
  return render(<MemoryRouter initialEntries={[path]}><OrdersPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "stripe", online_payment: true });
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
    expect(within(rows[3]).getByText("Bezahlt. Dein Server wird automatisch bereitgestellt, sobald Platz frei ist.")).toBeTruthy();
    expect(within(rows[4]).getByText("Produkt #5")).toBeTruthy();
    expect(within(rows[4]).getByLabelText("gekündigt")).toBeTruthy();
  });

  it("unterscheidet Stornieren (sofort) und Kuendigen zum Laufzeitende, beides über die uuid", async () => {
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

  it("zeigt bei erstatteten Bestellungen den Hinweis mit Loeschtermin und bei Streit das Badge, ohne Bezahl-Buttons", async () => {
    const refunded = makeOrder({ id: 7, uuid: "o-7", status: "refunded", refunded_at: "2026-10-02T09:00:00Z", scheduled_deletion_at: "2026-10-09T09:00:00Z", instance_name: "Server-R" });
    const disputed = makeOrder({ id: 8, uuid: "o-8", status: "active", disputed: true, current_period_end: "2026-11-15T00:00:00Z", instance_name: "Streit" });
    vi.spyOn(api, "getMyOrders").mockResolvedValue([refunded, disputed]);
    mount();
    await screen.findAllByText("Server-R");
    expect(screen.getAllByText(/Zahlung erstattet am 2\.10\.2026, der Server wird am 9\.10\.2026 gelöscht/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("status", { name: "Zahlung angefochten" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Jetzt bezahlen" })).toBeNull();
  });

  describe("Belege", () => {
    const r1 = { number: "R-2026-0001", issued_at: "2026-10-01T10:00:00Z", amount_cents: 999, currency: "EUR" };
    const r2 = { number: "R-2026-0007", issued_at: "2026-10-31T10:00:00Z", amount_cents: 999, currency: "EUR" };

    it("zeigt je Bestellung keinen, einen oder mehrere Belege und den Hinweis nur bei vorhandenen Belegen", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([
        makeOrder({ id: 1, uuid: "a", status: "active", instance_name: "Ohne", receipts: [] }),
        makeOrder({ id: 2, uuid: "b", status: "active", instance_name: "Eins", receipts: [r1] }),
        makeOrder({ id: 3, uuid: "c", status: "active", instance_name: "Zwei", receipts: [r1, r2] }),
      ]);
      mount();
      await screen.findByText("Zwei");
      expect(screen.getAllByText("Belege")).toHaveLength(2);
      expect(screen.getAllByText(/R-2026-0001 · 1\.10\.2026 · /)).toHaveLength(2);
      expect(screen.getByText(/R-2026-0007 · 31\.10\.2026/)).toBeTruthy();
      expect(screen.getByText("Vereinfachter Zahlungsbeleg, keine Rechnung mit Umsatzsteuer.")).toBeTruthy();
    });

    it("zeigt ohne Belege keinen Hinweis", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([makeOrder({ status: "active", receipts: [] })]);
      mount();
      await screen.findByText("Mein Server");
      expect(screen.queryByText(/Vereinfachter Zahlungsbeleg/)).toBeNull();
    });

    it("laedt den Beleg mit Nummer und zeigt ihn in einem Dialog; Escape schliesst", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([makeOrder({ uuid: "ord-9", status: "active", receipts: [r1, r2] })]);
      const get = vi.spyOn(api, "getReceiptHtml").mockResolvedValue("<h1>Beleg R-2026-0007</h1>");
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Beleg R-2026-0007 anzeigen" }));
      const dialog = await screen.findByRole("dialog", { name: "Beleg R-2026-0007" });
      expect(get).toHaveBeenCalledWith("ord-9", "R-2026-0007");
      const frame = within(dialog).getByTitle("Zahlungsbeleg R-2026-0007") as HTMLIFrameElement;
      expect(frame.getAttribute("sandbox")).toBe("");
      expect(frame.getAttribute("srcdoc")).toBe("<h1>Beleg R-2026-0007</h1>");
      expect(within(dialog).getByRole("button", { name: "Als Datei speichern" })).toBeTruthy();
      // Der Dialog nimmt den Fokus (Effekt läuft nach dem ersten Render): erst dann ist Escape verdrahtet
      await waitFor(() => expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Schliessen" })));
      fireEvent.keyDown(document, { key: "Escape" });
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    });

    it("zeigt bei 404 eine Fehlermeldung statt eines Dialogs", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([makeOrder({ status: "active", receipts: [r1] })]);
      vi.spyOn(api, "getReceiptHtml").mockRejectedValue(new ApiError("Beleg nicht gefunden", 404));
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Beleg R-2026-0001 anzeigen" }));
      expect(await screen.findByText("Beleg nicht gefunden")).toBeTruthy();
      expect(screen.queryByRole("dialog")).toBeNull();
    });
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

  describe("Zahlungsweg (billing-info)", () => {
    it("rendert bei manuellem Anbieter keine Bezahl-Buttons und nennt den Zahlungsweg sofort", async () => {
      vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
      const checkout = vi.spyOn(api, "createCheckout");
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending]);
      mount();
      expect((await screen.findAllByText("Zahlung per Überweisung, Freischaltung durch den Betreiber."))).toHaveLength(2);
      expect(screen.queryByRole("button", { name: /bezahlen/ })).toBeNull();
      expect(checkout).not.toHaveBeenCalled();
    });

    it("zeigt bei Stripe die Bezahl-Buttons", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      mount();
      expect(await screen.findByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
      expect(screen.queryByText(/Zahlung per Überweisung/)).toBeNull();
    });

    it("faellt auf die Buttons zurueck, wenn billing-info nicht geladen werden kann", async () => {
      vi.spyOn(api, "getBillingInfo").mockRejectedValue(new Error("nicht verfuegbar"));
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      mount();
      expect(await screen.findByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
    });

    it("zeigt Fehler wie nothing_to_pay und provider_unavailable mit dem Text des Backends", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      const checkout = vi.spyOn(api, "createCheckout").mockRejectedValueOnce(new ApiError("Für diese Bestellung ist nichts zu zahlen", 409, "nothing_to_pay"));
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Jetzt bezahlen" }));
      expect(await screen.findByText("Für diese Bestellung ist nichts zu zahlen")).toBeTruthy();
      checkout.mockRejectedValueOnce(new ApiError("Der Zahlungsanbieter ist gerade nicht erreichbar", 502, "provider_unavailable"));
      fireEvent.click(screen.getByRole("button", { name: "Jetzt bezahlen" }));
      expect(await screen.findByText("Der Zahlungsanbieter ist gerade nicht erreichbar")).toBeTruthy();
    });
  });

  it("bietet bei kostenlosen Bestellungen keine Zahlung an (nichts zu bezahlen)", async () => {
    const free = makeOrder({ id: 12, uuid: "o-12", status: "active", price_cents: 0, current_period_end: "2026-11-15T00:00:00" });
    vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
    vi.spyOn(api, "getMyOrders").mockResolvedValue([free]);
    mount();
    await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" });
    expect(screen.queryByText(/Überweisung/)).toBeNull();
    expect(screen.queryByRole("button", { name: /bezahlen/ })).toBeNull();
  });

  describe("Zahlung (Stripe-Checkout)", () => {
    const assign = vi.fn();
    beforeEach(() => {
      assign.mockReset();
      vi.stubGlobal("location", { ...window.location, assign });
    });
    afterEach(() => { vi.unstubAllGlobals(); });

    it("startet den Checkout für unbezahlte Bestellungen und leitet zur Zahlungsseite weiter", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending]);
      const checkout = vi.spyOn(api, "createCheckout").mockResolvedValue({ checkout_url: "https://checkout.stripe.com/c/pay/cs_1" });
      mount();
      // Nur die unbezahlte Bestellung bekommt den Button
      const buttons = await screen.findAllByRole("button", { name: "Jetzt bezahlen" });
      expect(buttons).toHaveLength(1);
      fireEvent.click(buttons[0]);
      await waitFor(() => expect(checkout).toHaveBeenCalledWith("o-2"));
      await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_1"));
    });

    it("blendet 'Jetzt bezahlen' bei 409 manual aus und erklaert den Zahlungsweg", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending, makeOrder({ id: 9, uuid: "o-9", status: "pending_payment" })]);
      vi.spyOn(api, "createCheckout").mockRejectedValue(new ApiError("Zahlung erfolgt manuell", 409, "manual"));
      mount();
      fireEvent.click((await screen.findAllByRole("button", { name: "Jetzt bezahlen" }))[0]);
      await waitFor(() => expect(screen.queryByRole("button", { name: "Jetzt bezahlen" })).toBeNull());
      expect(screen.getAllByText(/Zahlung per Überweisung/)).toHaveLength(2);
      expect(assign).not.toHaveBeenCalled();
      // Stornieren bleibt möglich
      expect(screen.getAllByRole("button", { name: "Stornieren" })).toHaveLength(2);
    });

    it("zeigt andere Fehler als Meldung und behaelt den Button", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      vi.spyOn(api, "createCheckout").mockRejectedValue(new ApiError("Stripe ist nicht erreichbar", 502));
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Jetzt bezahlen" }));
      expect(await screen.findByText("Stripe ist nicht erreichbar")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
    });

    it("bietet bei aktiven und ueberfaelligen Bestellungen 'Verlängern und bezahlen' an", async () => {
      const overdue2 = makeOrder({ id: 8, uuid: "o-8", status: "past_due", past_due_at: "2026-10-01T08:30:00", scheduled_deletion_at: "2026-10-08T08:30:00" });
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, overdue2]);
      const checkout = vi.spyOn(api, "createCheckout").mockResolvedValue({ checkout_url: "https://checkout.stripe.com/c/pay/cs_2" });
      mount();
      const buttons = await screen.findAllByRole("button", { name: "Verlängern und bezahlen" });
      expect(buttons).toHaveLength(2);
      expect(screen.queryByRole("button", { name: "Jetzt bezahlen" })).toBeNull();
      fireEvent.click(buttons[1]);
      await waitFor(() => expect(checkout).toHaveBeenCalledWith("o-8"));
      await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_2"));
    });

    it("hebt 'Verlängern und bezahlen' bei ueberfaelligen Bestellungen rot hervor", async () => {
      const overdue2 = makeOrder({ id: 8, uuid: "o-8", status: "past_due", past_due_at: "2026-10-01T08:30:00", scheduled_deletion_at: "2026-10-08T08:30:00" });
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, overdue2]);
      mount();
      const [normal, urgent] = await screen.findAllByRole("button", { name: "Verlängern und bezahlen" });
      expect((normal as HTMLElement).style.backgroundColor).toBe("rgb(25, 118, 210)");
      expect((urgent as HTMLElement).style.backgroundColor).toBe("rgb(211, 47, 47)");
    });

    it("lädt die Liste neu, wenn der Checkout invalid_status meldet", async () => {
      const list = vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      vi.spyOn(api, "createCheckout").mockRejectedValue(new ApiError("Bestellung ist nicht zahlbar", 409, "invalid_status"));
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Jetzt bezahlen" }));
      expect(await screen.findByText("Bestellung ist nicht zahlbar")).toBeTruthy();
      await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
      // invalid_status ist kein manueller Zahlungsweg: Button bleibt
      expect(screen.getByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
    });

    it("zeigt bei manuellem Zahlungsweg den zentralen Hinweistext statt aller Bezahl-Buttons", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending]);
      vi.spyOn(api, "createCheckout").mockRejectedValue(new ApiError("manual", 409, "manual"));
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Jetzt bezahlen" }));
      await waitFor(() => expect(screen.queryByRole("button", { name: /bezahlen/ })).toBeNull());
      expect(screen.getAllByText("Zahlung per Überweisung, Freischaltung durch den Betreiber.")).toHaveLength(2);
    });

    it("ruft keine unsichere Checkout-Adresse auf", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      vi.spyOn(api, "createCheckout").mockResolvedValue({ checkout_url: "javascript:alert(1)" });
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Jetzt bezahlen" }));
      expect(await screen.findByText(/ungültige Adresse/)).toBeTruthy();
      expect(assign).not.toHaveBeenCalled();
    });
  });

  describe("Rückkehr von Stripe", () => {
    it("meldet bei ?paid= den Zahlungseingang und lädt nach 5 s den Status nach", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      try {
        const list = vi.spyOn(api, "getMyOrders")
          .mockResolvedValueOnce([pending])
          .mockResolvedValue([{ ...pending, status: "active", current_period_end: "2026-11-15T00:00:00" }]);
        mount("/orders?paid=o-2");
        expect(await screen.findByText("Zahlung eingegangen, Server wird bereitgestellt. Eine Bestätigung folgt per E-Mail.")).toBeTruthy();
        await vi.advanceTimersByTimeAsync(5100);
        await waitFor(() => expect(screen.getByLabelText("aktiv")).toBeTruthy());
        // nach dem Statuswechsel wird nicht weiter nachgeladen
        const calls = list.mock.calls.length;
        await vi.advanceTimersByTimeAsync(10000);
        expect(list.mock.calls.length).toBe(calls);
      } finally {
        vi.useRealTimers();
      }
    });

    it("weist bei ?cancelled= auf die offene Bestellung hin", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([pending]);
      mount("/orders?cancelled=o-2");
      expect(await screen.findByText("Zahlung abgebrochen.")).toBeTruthy();
      expect(await screen.findByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
    });
  });

  describe("Schmale Bildschirme", () => {
    beforeEach(() => {
      vi.stubGlobal("matchMedia", (query: string) => ({
        matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {},
      }));
    });
    afterEach(() => { vi.unstubAllGlobals(); });

    it("zeigt Bestellungen als Karten mit allen Angaben und Aktionen statt als Tabelle", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active, pending]);
      mount();
      const list = await screen.findByRole("list", { name: "Meine Bestellungen" });
      expect(screen.queryByRole("table")).toBeNull();
      const cards = within(list).getAllByRole("listitem");
      expect(cards).toHaveLength(2);
      expect(within(cards[0]).getByLabelText("aktiv")).toBeTruthy();
      expect(within(cards[0]).getByText("15.11.2026")).toBeTruthy();
      expect(within(cards[0]).getByRole("link", { name: "Zum Server" }).getAttribute("href")).toBe("/instances/inst-abc");
      expect(within(cards[0]).getByRole("button", { name: "Kündigen zum Laufzeitende" })).toBeTruthy();
      expect(within(cards[1]).getByRole("button", { name: "Jetzt bezahlen" })).toBeTruthy();
      expect(within(cards[1]).getByRole("button", { name: "Stornieren" })).toBeTruthy();
    });

    it("kuendigt auch in der Kartenansicht", async () => {
      vi.spyOn(api, "getMyOrders").mockResolvedValue([active]);
      const cancel = vi.spyOn(api, "cancelOrder").mockResolvedValue(active);
      mount();
      fireEvent.click(await screen.findByRole("button", { name: "Kündigen zum Laufzeitende" }));
      await waitFor(() => expect(cancel).toHaveBeenCalledWith("o-1"));
    });
  });

  describe("Automatische Aktualisierung", () => {
    beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
    afterEach(() => { vi.useRealTimers(); });

    it("laedt alle 30 s still nach und zeigt den Wechsel auf aktiv ohne Neuladen", async () => {
      const waiting = makeOrder({ id: 3, uuid: "o-3", status: "awaiting_provisioning", instance_name: "Wartet" });
      const list = vi.spyOn(api, "getMyOrders")
        .mockResolvedValueOnce([waiting])
        .mockResolvedValue([{ ...waiting, status: "active", current_period_end: "2026-12-01T00:00:00", instance_uuid: "inst-9" }]);
      mount();
      await screen.findByText(/Dein Server wird automatisch bereitgestellt/);
      await vi.advanceTimersByTimeAsync(30500);
      await waitFor(() => expect(screen.getByLabelText("aktiv")).toBeTruthy());
      expect(screen.getByRole("link", { name: "Zum Server" }).getAttribute("href")).toBe("/instances/inst-9");
      expect(list.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    it("laesst die Liste bei einem Fehler des stillen Nachladens stehen", async () => {
      const list = vi.spyOn(api, "getMyOrders").mockResolvedValueOnce([active]).mockRejectedValue(new Error("Server nicht erreichbar"));
      mount();
      await screen.findByText("15.11.2026");
      await vi.advanceTimersByTimeAsync(30500);
      await waitFor(() => expect(list.mock.calls.length).toBeGreaterThanOrEqual(2));
      expect(screen.getByText("15.11.2026")).toBeTruthy();
      expect(screen.queryByText("Server nicht erreichbar")).toBeNull();
    });

    it("laesst sich abschalten und merkt sich die Einstellung", async () => {
      const list = vi.spyOn(api, "getMyOrders").mockResolvedValue([active]);
      mount();
      const toggle = await screen.findByLabelText("Auto-Refresh (30s)");
      fireEvent.click(toggle);
      expect(localStorage.getItem("astra.autorefresh.orders")).toBe("0");
      const calls = list.mock.calls.length;
      await vi.advanceTimersByTimeAsync(65000);
      expect(list.mock.calls.length).toBe(calls);
    });
  });
});
