// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AccountPage } from "./AccountPage";
import { api } from "../services/api";

const user = { id: 1, username: "alice", email: "alice@example.com", is_admin: false, mfa_enabled: false };

function mount() {
  return render(<MemoryRouter><AccountPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue(user as never);
  vi.spyOn(api, "getApiKeys").mockResolvedValue([]);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("AccountPage", () => {
  it("zeigt Profil und Link auf die SSH-Keys", async () => {
    mount();
    expect(await screen.findByText("alice@example.com")).toBeTruthy();
    expect(screen.getByText("Kunde")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /SSH-Keys verwalten/ })[0].getAttribute("href")).toBe("/account/ssh-keys");
  });

  it("aendert das Passwort mit Validierung und zeigt den Sitzungs-Hinweis", async () => {
    const change = vi.spyOn(api, "changePassword").mockResolvedValue({ message: "ok" });
    mount();
    await screen.findByText("alice@example.com");
    expect(screen.getByText(/Sitzungen auf anderen Geraeten/)).toBeTruthy();

    const fill = (cur: string, next: string, conf: string) => {
      fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), { target: { value: cur } });
      fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: next } });
      fireEvent.change(screen.getByLabelText("Neues Passwort wiederholen"), { target: { value: conf } });
      fireEvent.click(screen.getByRole("button", { name: "Passwort aendern" }));
    };
    fill("altespasswort", "kurz", "kurz");
    expect((await screen.findByRole("alert")).textContent).toMatch(/mindestens 8/);
    fill("altespasswort", "altespasswort", "altespasswort");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/unterscheiden/));
    fill("altespasswort", "neuespasswort1", "anders12345");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/stimmen nicht ueberein/));
    expect(change).not.toHaveBeenCalled();

    fill("altespasswort", "neuespasswort1", "neuespasswort1");
    await waitFor(() => expect(change).toHaveBeenCalledWith("altespasswort", "neuespasswort1"));
  });

  it("meldet ein falsches aktuelles Passwort", async () => {
    vi.spyOn(api, "changePassword").mockRejectedValue(new Error("Aktuelles Passwort ist falsch"));
    mount();
    await screen.findByText("alice@example.com");
    fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), { target: { value: "falsch123" } });
    fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: "neuespasswort1" } });
    fireEvent.change(screen.getByLabelText("Neues Passwort wiederholen"), { target: { value: "neuespasswort1" } });
    fireEvent.click(screen.getByRole("button", { name: "Passwort aendern" }));
    expect(await screen.findByText("Aktuelles Passwort ist falsch")).toBeTruthy();
  });

  it("richtet MFA ein: QR/Secret, Verifikation, Recovery-Codes", async () => {
    vi.spyOn(api, "setupMfa").mockResolvedValue({
      secret: "JBSWY3DPEHPK3PXP", provisioning_uri: "otpauth://totp/Astra:alice?secret=JBSWY3DPEHPK3PXP", message: "",
    });
    const verify = vi.spyOn(api, "verifyMfa").mockResolvedValue({
      mfa_enabled: true, recovery_codes: ["aaaa1111", "bbbb2222"], message: "",
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "MFA einrichten" }));
    expect(await screen.findByText("JBSWY3DPEHPK3PXP")).toBeTruthy();
    expect(await screen.findByAltText(/QR-Code/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Code aus der App/), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Aktivieren" }));
    await waitFor(() => expect(verify).toHaveBeenCalledWith("123456"));
    expect(await screen.findByText(/aaaa1111/)).toBeTruthy();
    expect(screen.getByText(/MFA ist/).textContent).toMatch(/aktiv/);
  });

  it("deaktiviert MFA nach Bestaetigung", async () => {
    (api.getCurrentUser as ReturnType<typeof vi.fn>).mockResolvedValue({ ...user, mfa_enabled: true });
    const disable = vi.spyOn(api, "disableMfa").mockResolvedValue({ message: "ok" });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "MFA deaktivieren" }));
    await waitFor(() => expect(disable).toHaveBeenCalled());
    expect(await screen.findByRole("button", { name: "MFA einrichten" })).toBeTruthy();
  });

  it("zeigt den neuen API-Key nur direkt nach dem Anlegen", async () => {
    const created = {
      id: 5, user_id: 1, key_type: "account", identifier: "astra_abc", memo: "Skript",
      allowed_ips: null, permissions: null, last_used_at: null, expires_at: null, created_at: null,
      raw_token: "astra_abc.GEHEIMER-TOKEN",
    };
    const create = vi.spyOn(api, "createApiKey").mockResolvedValue(created as never);
    (api.getApiKeys as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([])
      .mockResolvedValue([{ ...created, raw_token: undefined }]);
    mount();
    fireEvent.change(await screen.findByLabelText("Beschreibung"), { target: { value: " Skript " } });
    fireEvent.click(screen.getByRole("button", { name: "Key erstellen" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith({ key_type: "account", memo: "Skript" }));
    expect(await screen.findByText("astra_abc.GEHEIMER-TOKEN")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Schliessen" }));
    expect(screen.queryByText("astra_abc.GEHEIMER-TOKEN")).toBeNull();
    // Die Liste kennt nur die Kennung, nie den Klartext
    const row = screen.getByRole("row", { name: /Skript/ });
    expect(within(row).getByText("astra_abc")).toBeTruthy();
  });

  it("loescht einen API-Key", async () => {
    const key = { id: 9, user_id: 1, key_type: "application", identifier: "astra_zzz", memo: null,
      allowed_ips: null, permissions: null, last_used_at: null, expires_at: null, created_at: null };
    (api.getApiKeys as ReturnType<typeof vi.fn>).mockResolvedValueOnce([key]).mockResolvedValue([]);
    const del = vi.spyOn(api, "deleteApiKey").mockResolvedValue({ message: "ok" });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Loeschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(9));
  });
});
