// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BillingAddressSection } from "./BillingAddressSection";
import { api, ApiError } from "../../services/api";
import { setLang } from "../../i18n";

beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
afterEach(() => { cleanup(); setLang("de"); });

describe("BillingAddressSection", () => {
  it("füllt vorhandene Werte vor, zeigt den Hinweis und speichert getrimmt", async () => {
    const update = vi.spyOn(api, "updateBillingAddress").mockResolvedValue({} as never);
    const saved = vi.fn();
    render(<BillingAddressSection user={{ billing_name: "Anna GmbH", billing_address: null }} onSaved={saved} />);
    expect((screen.getByLabelText("Name oder Firma") as HTMLInputElement).value).toBe("Anna GmbH");
    expect(screen.getByText("Optional. Erscheint auf deinen Rechnungen.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Anschrift"), { target: { value: "Hauptstr. 1\n12345 Berlin" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith("Anna GmbH", "Hauptstr. 1\n12345 Berlin"));
    await waitFor(() => expect(saved).toHaveBeenCalledWith("Rechnungsadresse gespeichert"));
  });

  it("zeigt Fehler des Servers (auch bei Backend ohne das Feld) als Alert", async () => {
    vi.spyOn(api, "updateBillingAddress").mockRejectedValue(new ApiError("Feld unbekannt", 400));
    render(<BillingAddressSection user={{ billing_name: null, billing_address: null }} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Feld unbekannt");
  });

  it("ist auf Englisch beschriftet", () => {
    setLang("en");
    render(<BillingAddressSection user={{}} onSaved={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Billing address" })).toBeTruthy();
    expect(screen.getByText("Optional. Appears on your invoices.")).toBeTruthy();
  });
});
