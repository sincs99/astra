// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminBlueprintsPage } from "./AdminBlueprintsPage";
import { api, type Blueprint } from "../services/api";
import { setLang } from "../i18n";

const bp = {
  id: 4, name: "Minecraft", description: "Vanilla", docker_image: "itzg/minecraft-server", startup_command: "java -jar server.jar",
  install_script: null, install_container: null, install_entrypoint: null, config_schema: null, config_files: null,
  config_startup: { done: [")! For help"] }, config_stop: "stop", file_denylist: [], created_at: "2026-10-01T10:00:00Z", updated_at: null,
  variables: [{ name: "Port", description: "", env_var: "SERVER_PORT", default_value: "25565", user_viewable: true, user_editable: false }],
} as unknown as Blueprint;

function mount() {
  return render(<MemoryRouter><AdminBlueprintsPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(api, "getBlueprints").mockResolvedValue([bp]);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("AdminBlueprintsPage", () => {
  it("listet Blueprints mit Details und Variablentabelle", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: /Minecraft/ })).toBeTruthy();
    expect(screen.getByText("itzg/minecraft-server")).toBeTruthy();
    expect(screen.getByText(")! For help")).toBeTruthy();
    const table = screen.getByRole("region", { name: "Variablen von Minecraft" });
    expect(within(table).getByText("SERVER_PORT")).toBeTruthy();
    expect(within(table).getByText("Ja")).toBeTruthy();
    expect(within(table).getByText("Nein")).toBeTruthy();
  });

  it("legt einen Blueprint mit Variable an", async () => {
    const create = vi.spyOn(api, "createBlueprint").mockResolvedValue(bp);
    mount();
    await screen.findByRole("heading", { name: /Minecraft/ });
    const form = screen.getByRole("heading", { name: "Neuer Blueprint" }).closest("section") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Name *"), { target: { value: "Rust" } });
    fireEvent.change(within(form).getByLabelText("Startup-Erkennung – Zeile(n), ab denen der Server läuft (eine pro Zeile)"), { target: { value: "Server started" } });
    fireEvent.click(within(form).getByRole("button", { name: "Variable hinzufügen" }));
    fireEvent.change(within(form).getByLabelText("ENV-Variable"), { target: { value: "PORT" } });
    fireEvent.click(within(form).getByRole("button", { name: "Blueprint erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({ name: "Rust", config_startup: { done: ["Server started"] } });
    expect(create.mock.calls[0][0].variables!).toHaveLength(1);
    expect(create.mock.calls[0][0].variables![0]).toMatchObject({ env_var: "PORT" });
    expect(await screen.findByText("Blueprint erstellt.")).toBeTruthy();
  });

  it("bearbeitet einen Blueprint", async () => {
    const update = vi.spyOn(api, "updateBlueprint").mockResolvedValue(bp);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Bearbeiten" }));
    const edit = screen.getByRole("heading", { name: "Blueprint bearbeiten #4" }).closest("section") as HTMLElement;
    fireEvent.change(within(edit).getByLabelText("Name *"), { target: { value: "MC 2" } });
    fireEvent.click(within(edit).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(update.mock.calls[0][0]).toBe(4);
    expect(update.mock.calls[0][1]).toMatchObject({ name: "MC 2" });
    expect(await screen.findByText("Blueprint aktualisiert.")).toBeTruthy();
  });

  it("loescht nach Bestaetigung und zeigt Backend-Fehler als Alert", async () => {
    const del = vi.spyOn(api, "deleteBlueprint").mockRejectedValue(new Error("Blueprint wird von Produkten genutzt"));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(4));
    expect(window.confirm).toHaveBeenCalledWith('Blueprint "Minecraft" wirklich löschen?');
    expect((await screen.findByRole("alert")).textContent).toMatch(/von Produkten genutzt/);
  });

  it("zeigt einen Ladefehler mit Erneut-versuchen", async () => {
    vi.spyOn(api, "getBlueprints").mockRejectedValue(new Error("Backend down"));
    mount();
    expect((await screen.findByRole("alert")).textContent).toMatch(/Backend down/);
    expect(screen.getByRole("button", { name: "Erneut versuchen" })).toBeTruthy();
  });

  it("importiert ein Egg und zeigt Pruefmeldungen", async () => {
    const imp = vi.spyOn(api, "importBlueprint").mockResolvedValue(bp);
    mount();
    const area = await screen.findByLabelText("oder JSON einfügen");
    fireEvent.change(area, { target: { value: "kein json" } });
    expect((await screen.findByRole("alert")).textContent).toMatch(/Kein gültiges JSON/);
    fireEvent.change(area, { target: { value: JSON.stringify({ name: "Egg", author: "me@x.de", variables: [{}] }) } });
    expect(await screen.findByText(/von me@x\.de/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Importieren" }));
    await waitFor(() => expect(imp).toHaveBeenCalled());
    expect(await screen.findByText("Blueprint 'Minecraft' importiert.")).toBeTruthy();
  });

  it("zeigt die Oberflaeche auf Englisch", async () => {
    setLang("en");
    mount();
    expect(await screen.findByRole("heading", { name: "New blueprint" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Import blueprint" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Edit" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "ENV variable" })).toBeTruthy();
    expect(screen.getByText("Startup detection")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("or paste JSON"), { target: { value: "x" } });
    expect((await screen.findByRole("alert")).textContent).toBe("Not valid JSON.");
  });
});
