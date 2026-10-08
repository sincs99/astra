// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { InstanceDetailPage } from "./InstanceDetailPage";
import { api, type Instance } from "../services/api";
import { resetCurrentUserCache } from "../hooks/useCurrentUser";
import { makeOrder } from "../test/fixtures";

// Schwere Teilkomponenten (WebSocket, Dateien, Backups …) sind separat getestet bzw. brauchen echte Daten
vi.mock("../components/ServerConsole", () => ({ ServerConsole: () => <div>Konsole-Stub</div> }));
vi.mock("../components/FileBrowser", () => ({ FileBrowser: () => <div>Dateien-Stub</div> }));
vi.mock("../components/BackupManager", () => ({ BackupManager: () => <div>Backups-Stub</div> }));
vi.mock("../components/RoutineManager", () => ({ RoutineManager: () => <div>Routinen-Stub</div> }));
vi.mock("../components/CollaboratorManager", () => ({ CollaboratorManager: () => <div>Mitbenutzer-Stub</div> }));
vi.mock("../components/ActivityLog", () => ({ ActivityLog: () => <div>Aktivitaet-Stub</div> }));
vi.mock("../components/SftpAccess", () => ({ SftpAccess: () => <div>SFTP-Stub</div> }));

const base = {
  id: 1, uuid: "8k2f91ab-0000", name: "Freitagsrunde", description: "Crew-Server", status: "ready", container_state: "running",
  role: "owner", owner_id: 2, agent_id: 1, blueprint_id: 1, memory: 8192, swap: 0, disk: 51200, io: 500, cpu: 400,
  image: "img", startup_command: "run", variable_values: {}, suspended_reason: null,
  connection: { host: "mc.example", ip: "198.51.100.24", port: 25565, address: "mc.example:25565" },
} as unknown as Instance;

const stats = {
  container_status: "running", cpu_percent: 38, memory_bytes: 5 * 1024 ** 3, memory_limit_bytes: 8 * 1024 ** 3,
  disk_bytes: 45 * 1024 ** 3, network_rx_bytes: 1024, network_tx_bytes: 2048, uptime_seconds: 90000,
};

function mount(path = "/instances/8k2f91ab-0000") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/instances/:uuid" element={<InstanceDetailPage />} />
        <Route path="/" element={<div>Dashboard-Seite</div>} />
        <Route path="/orders" element={<div>Bestellungen-Seite</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function setup(instance: Instance = base, resources: unknown = stats) {
  vi.spyOn(api, "getClientInstance").mockResolvedValue(instance);
  vi.spyOn(api, "getInstanceResources").mockResolvedValue(resources as never);
  vi.spyOn(api, "getBlueprints").mockResolvedValue([]);
  vi.spyOn(api, "getMyOrders").mockResolvedValue([]);
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetCurrentUserCache();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); vi.useRealTimers(); });

describe("InstanceDetailPage", () => {
  it("zeigt Kopfzeile mit Status, Kurz-ID, Zurück-Link und Verbindung/Ressourcen in der Infospalte", async () => {
    setup();
    mount();
    expect(await screen.findByRole("heading", { level: 1, name: "Freitagsrunde" })).toBeTruthy();
    const backLink = screen.getAllByRole("link", { name: "Meine Server" }).find((a) => a.className.includes("back-link"));
    expect(backLink?.getAttribute("href")).toBe("/");
    expect(screen.getByText("läuft")).toBeTruthy();
    expect(screen.getByText("8k2f91ab")).toBeTruthy();
    const aside = screen.getByRole("complementary", { name: "Server" });
    expect(within(aside).getByText("mc.example:25565")).toBeTruthy();
    // Beschriftet "Serveradresse" und mit Kopierknopf
    expect(within(aside).getByText("Serveradresse")).toBeTruthy();
    expect(within(aside).getByRole("button", { name: /mc\.example:25565 kopieren/ })).toBeTruthy();
    expect(within(aside).getByText("198.51.100.24")).toBeTruthy();
    expect(await within(aside).findByText("38 %")).toBeTruthy();
    expect(within(aside).getByRole("progressbar", { name: "RAM" }).getAttribute("aria-valuenow")).toBe("63");
    expect(within(aside).getByRole("progressbar", { name: "Festplatte" }).getAttribute("aria-valuenow")).toBe("90");
  });

  it("aktiviert die Power-Buttons passend zum Zustand und sendet Stop", async () => {
    setup();
    const power = vi.spyOn(api, "sendPowerAction").mockResolvedValue({ message: "Stopp gesendet" } as never);
    mount();
    await screen.findByRole("heading", { level: 1, name: "Freitagsrunde" });
    await screen.findByText("38 %");
    expect((screen.getByRole("button", { name: "Start" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(power).toHaveBeenCalledWith("8k2f91ab-0000", "stop"));
    expect(await screen.findByText("Stopp gesendet")).toBeTruthy();
  });

  it("erlaubt bei gestopptem Server nur Start und Kill", async () => {
    setup({ ...base, container_state: "offline" } as Instance, { ...stats, container_status: "offline" });
    mount();
    await screen.findByRole("heading", { level: 1, name: "Freitagsrunde" });
    await waitFor(() => expect((screen.getByRole("button", { name: "Stop" }) as HTMLButtonElement).disabled).toBe(true));
    expect((screen.getByRole("button", { name: "Start" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "Neustart" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("fragt vor Kill nach und sendet nur nach Bestätigung", async () => {
    setup();
    const power = vi.spyOn(api, "sendPowerAction").mockResolvedValue({ message: "ok" } as never);
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    mount();
    await screen.findByRole("heading", { level: 1, name: "Freitagsrunde" });
    fireEvent.click(screen.getByRole("button", { name: "Kill" }));
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(power).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Kill" }));
    await waitFor(() => expect(power).toHaveBeenCalledWith("8k2f91ab-0000", "kill"));
  });

  it("wechselt per Tab zwischen Konsole, Dateien, Backups und Einstellungen und merkt sich den Tab in der URL", async () => {
    setup();
    mount();
    await screen.findByText("Konsole-Stub");
    expect(screen.getByRole("tab", { name: "Konsole" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: "Dateien" }));
    expect(await screen.findByText("Dateien-Stub")).toBeTruthy();
    expect(screen.queryByText("Konsole-Stub")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Backups" }));
    expect(await screen.findByText("Backups-Stub")).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Backups" }), { key: "ArrowRight" });
    expect(await screen.findByText("Routinen-Stub")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Einstellungen" }).getAttribute("aria-selected")).toBe("true");
  });

  it("öffnet über ?tab=settings direkt die Einstellungen; Owner sehen 'Server löschen', Mitbenutzer nicht", async () => {
    setup();
    const first = mount("/instances/8k2f91ab-0000?tab=settings");
    expect(await screen.findByRole("heading", { name: "Server löschen" })).toBeTruthy();
    expect(screen.getByText("Mitbenutzer-Stub")).toBeTruthy();
    first.unmount();
    setup({ ...base, role: "collaborator" } as Instance);
    mount("/instances/8k2f91ab-0000?tab=settings");
    await screen.findByText("Mitbenutzer-Stub");
    expect(screen.queryByRole("heading", { name: "Server löschen" })).toBeNull();
    expect(screen.queryByText("Routinen-Stub")).toBeNull();
  });

  it("zeigt Laufzeit aus der Bestellung mit Verlängern (Überweisung -> Bestellungen)", async () => {
    setup();
    vi.mocked(api.getMyOrders).mockResolvedValue([
      makeOrder({ status: "active", instance_uuid: "8k2f91ab-0000", product_name: "Crew", price_cents: 1990, current_period_end: "2026-10-28T00:00:00Z" }),
    ]);
    mount();
    expect(await screen.findByText("Crew")).toBeTruthy();
    expect(screen.getByText((_, el) => el?.tagName === "SPAN" && /19,90.*30 Tage/.test((el.textContent ?? "").replace(/[\u00a0\u202f]/g, " ")))).toBeTruthy();
    const link = screen.getByRole("link", { name: "Verlängern" });
    expect(link.getAttribute("href")).toBe("/orders");
  });

  it("zeigt ohne Bestellung (z.B. Mitbenutzer) kein Laufzeit-Panel", async () => {
    setup();
    mount();
    await screen.findByRole("heading", { level: 1, name: "Freitagsrunde" });
    expect(screen.queryByText("Laufzeit", { selector: "h2" })).toBeNull();
  });

  it("warnt bei gesperrtem Server und sperrt die Steuerung", async () => {
    setup({ ...base, status: "suspended", suspended_reason: "Zahlung überfällig" } as Instance);
    mount();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Dein Server ist gesperrt");
    expect(alert.textContent).toContain("Zahlung überfällig");
    expect((screen.getByRole("button", { name: "Kill" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("bietet bei fehlgeschlagener Einrichtung dem Owner 'Neu installieren' an", async () => {
    setup({ ...base, status: "provision_failed" } as Instance);
    const reinstall = vi.spyOn(api, "reinstallInstance").mockResolvedValue({ message: "Neuinstallation gestartet" } as never);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /Neu installieren/ }));
    await waitFor(() => expect(reinstall).toHaveBeenCalledWith("8k2f91ab-0000"));
  });
});
