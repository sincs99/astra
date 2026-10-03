// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AdminInstancesPage } from "./AdminInstancesPage";
import { api } from "../services/api";

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
afterEach(() => { cleanup(); localStorage.clear(); });

async function fillBasics() {
  fireEvent.change(await screen.findByLabelText("Name *"), { target: { value: "Srv" } });
  fireEvent.change(screen.getByLabelText("Owner *"), { target: { value: "3" } });
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
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "7" } });
    fireEvent.change(await screen.findByLabelText(/^Endpoint/), { target: { value: "11" } });
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
