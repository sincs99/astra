// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminInvoicesPage, monthRange } from "./AdminInvoicesPage";
import { api, ApiError, type InvoiceRow } from "../services/api";
import { setLang } from "../i18n";

const rows: InvoiceRow[] = [
  { number: "R-2026-0001", kind: "invoice", issued_at: "2026-10-03T10:00:00Z", customer_name: "Anna GmbH", net_cents: 1000, vat_cents: 190, gross_cents: 1190, currency: "EUR" },
  { number: "G-2026-0001", kind: "credit_note", issued_at: "2026-10-20T10:00:00Z", username: "bob", net_cents: -1000, vat_cents: -190, gross_cents: -1190, currency: "EUR" },
];

const mount = () => render(<MemoryRouter><AdminInvoicesPage /></MemoryRouter>);

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  setLang("de");
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("monthRange", () => {
  it("liefert ersten und letzten Tag, auch im Schaltjahr", () => {
    expect(monthRange("2026-10")).toEqual({ from: "2026-10-01", to: "2026-10-31" });
    expect(monthRange("2028-02")).toEqual({ from: "2028-02-01", to: "2028-02-29" });
    expect(monthRange("2026-02")).toEqual({ from: "2026-02-01", to: "2026-02-28" });
    expect(monthRange("")).toBeNull();
    expect(monthRange("2026-13")).toBeNull();
  });
});

describe("AdminInvoicesPage", () => {
  it("lädt den gewählten Monat und zeigt Nummer, Art, Datum, Kunde, Netto, USt., Brutto, Währung", async () => {
    const list = vi.spyOn(api, "getInvoices").mockResolvedValue(rows);
    mount();
    fireEvent.change(screen.getByLabelText("Monat"), { target: { value: "2026-10" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith("2026-10-01", "2026-10-31"));
    const table = await screen.findByRole("table");
    for (const h of ["Nummer", "Art", "Datum", "Kunde", "Netto", "USt.", "Brutto", "Währung"]) {
      expect(within(table).getByRole("columnheader", { name: h })).toBeTruthy();
    }
    expect(within(table).getByText("R-2026-0001")).toBeTruthy();
    expect(within(table).getByText("Rechnung")).toBeTruthy();
    expect(within(table).getByText("Gutschrift")).toBeTruthy();
    expect(within(table).getByText("Anna GmbH")).toBeTruthy();
    expect(within(table).getByText("bob")).toBeTruthy();
    expect(within(table).getAllByText(/11,90/)).toHaveLength(2);
  });

  it("zeigt Leerzustand und Fehler mit Wiederholen", async () => {
    const list = vi.spyOn(api, "getInvoices").mockResolvedValueOnce([]).mockRejectedValueOnce(new ApiError("kaputt", 500)).mockResolvedValue(rows);
    mount();
    expect(await screen.findByText("Keine Rechnungen in diesem Monat.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Monat"), { target: { value: "2026-09" } });
    expect((await screen.findByRole("alert")).textContent).toContain("kaputt");
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByRole("table");
    expect(list).toHaveBeenCalledTimes(3);
  });

  it("lädt die CSV herunter (Blob, Dateiname mit Monat)", async () => {
    vi.spyOn(api, "getInvoices").mockResolvedValue(rows);
    const csv = vi.spyOn(api, "getInvoicesCsv").mockResolvedValue("number;kind\nR-1;invoice\n");
    const create = vi.fn(() => "blob:x");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    let name = "";
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { name = this.download; });
    mount();
    fireEvent.change(screen.getByLabelText("Monat"), { target: { value: "2026-10" } });
    await screen.findByRole("table");
    fireEvent.click(screen.getByRole("button", { name: "CSV herunterladen" }));
    await waitFor(() => expect(csv).toHaveBeenCalledWith("2026-10-01", "2026-10-31"));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(name).toBe("rechnungen-2026-10.csv");
    expect(revoke).toHaveBeenCalled();
  });

  it("ist auf Englisch beschriftet", async () => {
    setLang("en");
    vi.spyOn(api, "getInvoices").mockResolvedValue(rows);
    mount();
    expect(await screen.findByRole("button", { name: "Download CSV" })).toBeTruthy();
    expect(await screen.findByRole("columnheader", { name: "Gross" })).toBeTruthy();
    expect(screen.getByText("Credit note")).toBeTruthy();
  });
});
