// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TransferInstanceForm } from "./TransferInstanceForm";
import { api, type Agent } from "../services/api";

const agents = [{ id: 2, name: "Node-2" }, { id: 3, name: "Node-3" }] as Agent[];
// Antwort von GET /admin/instances/{uuid}/backups
const info = (successful: number, last: string | null = "2026-10-01T10:00:00") =>
  ({ backups: [], successful_count: successful, last_successful_backup_at: successful ? last : null });

beforeEach(() => vi.restoreAllMocks());
afterEach(cleanup);

function mount(onTransfer = vi.fn().mockResolvedValue(undefined)) {
  render(<TransferInstanceForm instanceUuid="u-1" instanceName="Mein Server" agents={agents} onTransfer={onTransfer} onCancel={() => {}} />);
  return onTransfer;
}
const start = () => screen.getByRole("button", { name: "Transfer starten" }) as HTMLButtonElement;
async function fillAll() {
  fireEvent.change(screen.getByLabelText("Ziel-Agent"), { target: { value: "3" } });
  fireEvent.click(screen.getByLabelText("Ich habe ein aktuelles Backup"));
  fireEvent.change(screen.getByLabelText(/Zur Bestätigung den Namen/), { target: { value: "Mein Server" } });
}

describe("TransferInstanceForm", () => {
  it("zeigt die rote Warnung, dass Serverdaten nicht uebertragen werden", async () => {
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(2));
    mount();
    expect(screen.getByRole("alert").textContent).toBe(
      "Achtung: Beim Transfer werden die Serverdaten NICHT übertragen. Vorher ein Backup erstellen und danach wiederherstellen.");
    await screen.findByText(/Letztes erfolgreiches Backup: 1\.10\.2026/);
  });

  it("aktiviert 'Transfer starten' erst mit Ziel, Backup-Haken und exaktem Namen", async () => {
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(2));
    const onTransfer = mount();
    await screen.findByText(/Letztes erfolgreiches Backup/);
    expect(start().disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Ziel-Agent"), { target: { value: "3" } });
    expect(start().disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Ich habe ein aktuelles Backup"));
    expect(start().disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Zur Bestätigung den Namen/), { target: { value: "mein server" } });
    expect(start().disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Zur Bestätigung den Namen/), { target: { value: "Mein Server" } });
    expect(start().disabled).toBe(false);
    fireEvent.click(start());
    await waitFor(() => expect(onTransfer).toHaveBeenCalledWith(3));
  });

  it("fragt den Admin-Endpunkt der Instance ab", async () => {
    const check = vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(1));
    mount();
    await screen.findByText(/Letztes erfolgreiches Backup/);
    expect(check).toHaveBeenCalledWith("u-1");
  });

  it("sperrt den Transfer, wenn es kein erfolgreiches Backup gibt", async () => {
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(0));
    const onTransfer = mount();
    expect(await screen.findByText(/kein erfolgreiches Backup/)).toBeTruthy();
    await fillAll();
    expect(start().disabled).toBe(true);
    expect(onTransfer).not.toHaveBeenCalled();
  });

  it("wartet waehrend der Pruefung und erlaubt den Transfer, wenn die Backups nicht lesbar sind (Admin)", async () => {
    let reject!: (e: Error) => void;
    vi.spyOn(api, "getAdminInstanceBackups").mockReturnValue(new Promise((_, r) => { reject = r; }));
    mount();
    await fillAll();
    expect(screen.getByText("Backups werden geprüft…")).toBeTruthy();
    expect(start().disabled).toBe(true);
    reject(new Error("Instance nicht gefunden"));
    expect(await screen.findByText(/konnten nicht geprüft werden/)).toBeTruthy();
    await waitFor(() => expect(start().disabled).toBe(false));
  });

  it("zeigt den Fehler des Backends und erlaubt einen neuen Versuch", async () => {
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(2));
    const onTransfer = vi.fn().mockRejectedValue(new Error("Ziel-Agent hat nicht genug Kapazität"));
    mount(onTransfer);
    await screen.findByText(/Letztes erfolgreiches Backup/);
    await fillAll();
    fireEvent.click(start());
    expect(await screen.findByText("Ziel-Agent hat nicht genug Kapazität")).toBeTruthy();
    expect(start().disabled).toBe(false);
  });

  it("bietet nur die uebergebenen Ziel-Agents an", async () => {
    vi.spyOn(api, "getAdminInstanceBackups").mockResolvedValue(info(1));
    mount();
    const options = Array.from((screen.getByLabelText("Ziel-Agent") as HTMLSelectElement).options).map((o) => o.textContent);
    expect(options).toEqual(["– Ziel-Agent wählen –", "Node-2", "Node-3"]);
  });
});
