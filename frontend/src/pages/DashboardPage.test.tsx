// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";
import { api, type Instance } from "../services/api";

const customer = { id: 2, username: "bob", email: "b@x.de", is_admin: false };
const admin = { ...customer, id: 1, username: "root", is_admin: true };

const instance = {
  id: 1, uuid: "0f3a9c1e-aaaa", name: "Mein Server", status: "ready", role: "owner",
  memory: 512, disk: 1000, cpu: 100,
  connection: { host: "n1.example.com", port: 25565, address: "n1.example.com:25565" },
} as Instance;

function mount() {
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", `tok-${Math.random()}`);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("DashboardPage", () => {
  it("zeigt Kunden ohne Server den Platzhalter fuer die Bestellung", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    mount();
    expect(await screen.findByText("Noch kein Server. Bestellung folgt in Phase 4.")).toBeTruthy();
    expect(screen.queryByText(/Admin-Bereich/)).toBeNull();
  });

  it("verweist Admins ohne Instances auf den Admin-Bereich", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(admin as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
    mount();
    expect(await screen.findByText(/ueber den Admin-Bereich/)).toBeTruthy();
  });

  it("zeigt Server mit Status und Verbindungsadresse", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    vi.spyOn(api, "getClientInstances").mockResolvedValue([instance]);
    mount();
    expect(await screen.findByText("Mein Server")).toBeTruthy();
    expect(screen.getByText("n1.example.com:25565")).toBeTruthy();
    expect(screen.getByText("Eingeloggt als bob", { exact: false })).toBeTruthy();
  });

  it("zeigt bei einem Ladefehler eine Meldung und kann es erneut versuchen", async () => {
    vi.spyOn(api, "getCurrentUser").mockResolvedValue(customer as never);
    const load = vi.spyOn(api, "getClientInstances")
      .mockRejectedValueOnce(new Error("Der Server ist nicht erreichbar."))
      .mockResolvedValue([instance]);
    mount();
    expect(await screen.findByText("Der Server ist nicht erreichbar.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("Mein Server")).toBeTruthy();
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  });
});
