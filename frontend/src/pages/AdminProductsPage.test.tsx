// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminProductsPage } from "./AdminProductsPage";
import { api } from "../services/api";
import { makeProduct } from "../test/fixtures";

const product = makeProduct({ description: "Klein" });

function mount() {
  return render(<MemoryRouter><AdminProductsPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(api, "getAdminProducts").mockResolvedValue([product]);
  vi.spyOn(api, "getBlueprints").mockResolvedValue([{ id: 1, name: "Minecraft" }] as never);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  window.scrollTo = vi.fn() as never;
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("AdminProductsPage", () => {
  it("zeigt Produkte mit Preis, Ressourcen und Aktiv-Badge", async () => {
    mount();
    expect(await screen.findByText("Starter")).toBeTruthy();
    expect(screen.getByText("Minecraft", { selector: "td" })).toBeTruthy();
    expect(screen.getByText(/2048 MB RAM · 10240 MB Disk · 150% CPU/)).toBeTruthy();
    expect(screen.getByLabelText("aktiv")).toBeTruthy();
    expect((screen.getByText(/€ \/ 30 Tage/).textContent ?? "").replace(/ | /g, " ")).toBe("9,99 € / 30 Tage");
  });

  it("legt ein Produkt an und rechnet Euro in Cent um", async () => {
    const create = vi.spyOn(api, "createProduct").mockResolvedValue(product);
    mount();
    await screen.findByText("Starter");
    fireEvent.click(screen.getByRole("button", { name: "Produkt erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Namen/);
    expect(create).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Name *"), { target: { value: "Pro" } });
    fireEvent.change(screen.getByLabelText("Blueprint *"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Preis (€) *"), { target: { value: "19,90" } });
    fireEvent.click(screen.getByRole("button", { name: "Produkt erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({
      name: "Pro", blueprint_id: 1, price_cents: 1990, currency: "EUR", billing_period_days: 30,
      is_active: true, max_instances_per_user: null, memory: 1024, swap: 0, io: 500,
    });
  });

  it("bearbeitet ein Produkt mit vorbelegtem Formular", async () => {
    const update = vi.spyOn(api, "updateProduct").mockResolvedValue(product);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /Bearbeiten/ }));
    expect((screen.getByLabelText("Preis (€) *") as HTMLInputElement).value).toBe("9,99");
    expect((screen.getByLabelText("Name *") as HTMLInputElement).value).toBe("Starter");
    fireEvent.change(screen.getByLabelText("Preis (€) *"), { target: { value: "12,50" } });
    fireEvent.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(update.mock.calls[0][0]).toBe(5);
    expect(update.mock.calls[0][1]).toMatchObject({ price_cents: 1250, name: "Starter" });
  });

  it("verlangt bei kostenlosen Produkten ein Limit pro Nutzer", async () => {
    const create = vi.spyOn(api, "createProduct").mockResolvedValue(product);
    mount();
    await screen.findByText("Starter");
    fireEvent.change(screen.getByLabelText("Name *"), { target: { value: "Gratis" } });
    fireEvent.change(screen.getByLabelText("Blueprint *"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Preis (€) *"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Produkt erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Kostenlose Produkte/);
    expect(create).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Max\. Instances pro Nutzer/), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Produkt erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({ price_cents: 0, max_instances_per_user: 1 });
  });

  it("deaktiviert ein aktives Produkt", async () => {
    const update = vi.spyOn(api, "updateProduct").mockResolvedValue(product);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Deaktivieren" }));
    await waitFor(() => expect(update).toHaveBeenCalledWith(5, { is_active: false }));
  });

  it("zeigt den Backend-Fehler, wenn das Loeschen abgelehnt wird", async () => {
    vi.spyOn(api, "deleteProduct").mockRejectedValue(new Error("Produkt hat noch Bestellungen"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Löschen" }));
    expect(await screen.findByText("Produkt hat noch Bestellungen")).toBeTruthy();
  });
});
