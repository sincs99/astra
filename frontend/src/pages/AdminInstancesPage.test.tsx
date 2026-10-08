// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminInstancesPage } from "./AdminInstancesPage";
import { api } from "../services/api";
import { setLang } from "../i18n";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getInstances").mockResolvedValue([]);
  vi.spyOn(api, "getUsers").mockResolvedValue([{ id: 3, username: "kunde" }] as never);
  vi.spyOn(api, "getAgents").mockResolvedValue([{ id: 7, name: "N1", fqdn: "n1.x.de" }] as never);
  vi.spyOn(api, "getBlueprints").mockResolvedValue([{ id: 2, name: "Minecraft" }] as never);
  vi.spyOn(api, "getEndpoints").mockResolvedValue([
    { id: 11, agent_id: 7, instance_id: null, is_locked: false, ip: "0.0.0.0", port: 25565 },
  ] as never);
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

async function fillBasics() {
  fireEvent.change(await screen.findByLabelText("Name *"), { target: { value: "Srv" } });
  // Die Auswahllisten werden asynchron befüllt: erst wenn die Option da ist, lässt sich ein Wert wählen
  const hasOption = (label: string, value: string) => () =>
    expect((screen.getByLabelText(label) as HTMLSelectElement).querySelector(`option[value="${value}"]`)).toBeTruthy();
  await waitFor(hasOption("Owner *", "3"));
  fireEvent.change(screen.getByLabelText("Owner *"), { target: { value: "3" } });
  await waitFor(hasOption("Blueprint *", "2"));
  fireEvent.change(screen.getByLabelText("Blueprint *"), { target: { value: "2" } });
}

describe("AdminInstancesPage Erstellformular", () => {
  it("platziert standardmaessig automatisch und blendet das Endpoint-Feld aus", async () => {
    const create = vi.spyOn(api, "createInstance").mockResolvedValue({} as never);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    await fillBasics();
    const agent = screen.getByLabelText("Agent") as HTMLSelectElement;
    expect(agent.value).toBe("");
    expect(agent.options[0].textContent).toBe("Automatisch (nach Kapazität)");
    expect(screen.queryByLabelText(/^Endpoint/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Instance erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({ name: "Srv", owner_id: 3, blueprint_id: 2, agent_id: null });
  });

  it("zeigt bei gewaehltem Agent das Endpoint-Feld und sendet agent_id", async () => {
    const create = vi.spyOn(api, "createInstance").mockResolvedValue({} as never);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    await fillBasics();
    await waitFor(() => expect((screen.getByLabelText("Agent") as HTMLSelectElement).querySelector('option[value="7"]')).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "7" } });
    const endpoint = await screen.findByLabelText(/^Endpoint/);
    await waitFor(() => expect((endpoint as HTMLSelectElement).querySelector('option[value="11"]')).toBeTruthy());
    fireEvent.change(endpoint, { target: { value: "11" } });
    fireEvent.click(screen.getByRole("button", { name: "Instance erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({ agent_id: 7, endpoint_id: 11 });
  });

  it("zeigt den 409-Text der Platzierung an", async () => {
    vi.spyOn(api, "createInstance").mockRejectedValue(new Error("Kein Agent mit genug Kapazität: memory (frei: 256 MB)"));
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    await fillBasics();
    fireEvent.click(screen.getByRole("button", { name: "Instance erstellen" }));
    expect(await screen.findByText(/Kein Agent mit genug Kapazität/)).toBeTruthy();
  });
});

describe("AdminInstancesPage Loeschen", () => {
  const inst = { id: 1, uuid: "u-1", name: "Alt", status: "ready", owner_id: 3, agent_id: 7, blueprint_id: 2,
    primary_endpoint_id: null, memory: 512, disk: 1024, cpu: 100 };

  async function openDelete() {
    (api.getInstances as ReturnType<typeof vi.fn>).mockResolvedValue([inst]);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Löschen/ }));
    fireEvent.change(await screen.findByLabelText(/Zur Bestätigung den Namen/), { target: { value: "Alt" } });
  }

  it("warnt Admins, wenn das Aufraeumen auf dem Node fehlgeschlagen ist", async () => {
    const del = vi.spyOn(api, "adminDeleteInstance").mockResolvedValue({ uuid: "u-1", message: "ok", runner_cleanup: "failed" });
    await openDelete();
    fireEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("u-1", false));
    expect(await screen.findByText(/aufräumen auf dem node fehlgeschlagen, bitte wings prüfen/i)).toBeTruthy();
  });

  it("bestaetigt normales Loeschen mit Erfolgsmeldung", async () => {
    vi.spyOn(api, "adminDeleteInstance").mockResolvedValue({ uuid: "u-1", message: "ok", runner_cleanup: "ok" });
    await openDelete();
    fireEvent.click(screen.getByRole("button", { name: "Endgültig löschen" }));
    expect(await screen.findByText('"Alt" gelöscht.')).toBeTruthy();
  });
});

describe("AdminInstancesPage Transfer", () => {
  const inst = { id: 1, uuid: "u-1", name: "Alt", status: "ready", owner_id: 3, agent_id: 7, blueprint_id: 2,
    primary_endpoint_id: null, memory: 512, disk: 1024, cpu: 100 };

  it("oeffnet statt des alten Schnell-Transfers den Sicherheitsdialog und startet erst nach allen Bestaetigungen", async () => {
    (api.getInstances as ReturnType<typeof vi.fn>).mockResolvedValue([inst]);
    (api.getAgents as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id: 7, name: "N1", fqdn: "a", is_active: true }, { id: 8, name: "N2", fqdn: "b", is_active: true }, { id: 9, name: "N3", fqdn: "c", is_active: false },
    ]);
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue({ backups: [], successful_count: 1, last_successful_backup_at: "2026-10-01T10:00:00" });
    const transfer = vi.spyOn(api, "transferInstance").mockResolvedValue({} as never);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Transfer/ }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Serverdaten NICHT übertragen/);
    const options = Array.from((screen.getByLabelText("Ziel-Agent") as HTMLSelectElement).options).map((o) => o.textContent);
    expect(options).toEqual(["– Ziel-Agent wählen –", "N2"]); // weder aktueller noch inaktiver Agent
    fireEvent.change(screen.getByLabelText("Ziel-Agent"), { target: { value: "8" } });
    fireEvent.click(screen.getByLabelText("Ich habe ein aktuelles Backup"));
    fireEvent.change(screen.getByLabelText(/Zur Bestätigung den Namen/), { target: { value: "Alt" } });
    await screen.findByText(/Letztes erfolgreiches Backup/);
    fireEvent.click(screen.getByRole("button", { name: "Transfer starten" }));
    await waitFor(() => expect(transfer).toHaveBeenCalledWith("u-1", 8));
    expect(await screen.findByText(/Transfer für "Alt" gestartet/)).toBeTruthy();
  });
});

describe("AdminInstancesPage Liste", () => {
  const inst = { id: 1, uuid: "abcdef12-0000", name: "Alt", description: "Testserver", status: "ready", owner_id: 3, agent_id: 7, blueprint_id: 2,
    primary_endpoint_id: 11, memory: 512, disk: 1024, cpu: 100 };

  it("listet Instances mit Owner, Agent, Endpoint und Ressourcen", async () => {
    (api.getInstances as ReturnType<typeof vi.fn>).mockResolvedValue([inst]);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    expect(await screen.findByText("Alt")).toBeTruthy();
    expect(screen.getByText("kunde", { selector: "td" })).toBeTruthy();
    expect(screen.getByText("N1", { selector: "td" })).toBeTruthy();
    expect(screen.getByText("0.0.0.0:25565")).toBeTruthy();
    expect(screen.getByText("512 MB / 1024 MB / 100%")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Instances-Tabelle" })).toBeTruthy();
  });

  it("sperrt eine Instance nach Bestaetigung", async () => {
    (api.getInstances as ReturnType<typeof vi.fn>).mockResolvedValue([inst]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const suspend = vi.spyOn(api, "suspendInstance").mockResolvedValue({} as never);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Sperren" }));
    await waitFor(() => expect(suspend).toHaveBeenCalledWith("abcdef12-0000"));
    expect(confirm).toHaveBeenCalledWith('Instance "Alt" suspendieren?');
    expect(await screen.findByText('"Alt" suspendiert')).toBeTruthy();
  });

  it("zeigt einen Ladefehler als Alert mit Erneut-versuchen", async () => {
    (api.getInstances as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("Backend down"));
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    expect((await screen.findByRole("alert")).textContent).toMatch(/Backend down/);
    expect(screen.getByRole("button", { name: "Erneut versuchen" })).toBeTruthy();
  });

  it("zeigt die Oberflaeche auf Englisch", async () => {
    setLang("en");
    (api.getInstances as ReturnType<typeof vi.fn>).mockResolvedValue([inst]);
    render(<MemoryRouter><AdminInstancesPage /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "New instance" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create instance" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Suspend" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Resources" })).toBeTruthy();
    expect(screen.getByLabelText("Agent")).toBeTruthy();
    expect(screen.queryByText("Instance erstellen")).toBeNull();
  });
});
