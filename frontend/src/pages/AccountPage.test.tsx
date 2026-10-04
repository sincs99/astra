// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AccountPage } from "./AccountPage";
import { api, ApiError } from "../services/api";

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
    expect(within(screen.getByRole("region", { name: "Profil" })).getByText("Kunde")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /SSH-Keys verwalten/ })[0].getAttribute("href")).toBe("/account/ssh-keys");
  });

  it("aendert das Passwort mit Validierung und zeigt den Sitzungs-Hinweis", async () => {
    const change = vi.spyOn(api, "changePassword").mockResolvedValue({ message: "ok" });
    mount();
    await screen.findByText("alice@example.com");
    expect(screen.getByText(/anderen angemeldeten Geräte abgemeldet/)).toBeTruthy();

    const fill = (cur: string, next: string, conf: string) => {
      fireEvent.change(screen.getByLabelText("Aktuelles Passwort"), { target: { value: cur } });
      fireEvent.change(screen.getByLabelText("Neues Passwort"), { target: { value: next } });
      fireEvent.change(screen.getByLabelText("Neues Passwort wiederholen"), { target: { value: conf } });
      fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));
    };
    fill("altespasswort", "kurz", "kurz");
    expect((await screen.findByRole("alert")).textContent).toMatch(/mindestens 8/);
    fill("altespasswort", "altespasswort", "altespasswort");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/unterscheiden/));
    fill("altespasswort", "neuespasswort1", "anders12345");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/stimmen nicht überein/));
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
    fireEvent.click(screen.getByRole("button", { name: "Passwort ändern" }));
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

  it("zeigt die Recovery-Codes gross und schliesst erst nach Bestaetigung", async () => {
    vi.spyOn(api, "setupMfa").mockResolvedValue({ secret: "S", provisioning_uri: "otpauth://x", message: "" });
    vi.spyOn(api, "verifyMfa").mockResolvedValue({
      mfa_enabled: true, recovery_codes: ["abcde-fghij", "klmno-pqrst"], recovery_codes_remaining: 10, message: "",
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "MFA einrichten" }));
    await screen.findByText("S");
    fireEvent.change(screen.getByLabelText(/Code aus der App/), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Aktivieren" }));
    const list = await screen.findByRole("list", { name: "Recovery-Codes" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["abcde-fghij", "klmno-pqrst"]);
    expect(screen.getByRole("button", { name: /Als Textdatei speichern/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Kopieren/ })).toBeTruthy();
    const done = screen.getByRole("button", { name: "Fertig" }) as HTMLButtonElement;
    expect(done.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("Ich habe die Codes gesichert"));
    expect(done.disabled).toBe(false);
    fireEvent.click(done);
    expect(screen.queryByRole("list", { name: "Recovery-Codes" })).toBeNull();
    expect(await screen.findByText("Recovery-Codes: noch 10 von 10 übrig.")).toBeTruthy();
  });

  it("zeigt den Restbestand an und warnt bei wenigen oder keinen Codes", async () => {
    const me = vi.mocked(api.getCurrentUser);
    me.mockResolvedValue({ ...user, mfa_enabled: true, mfa_recovery_codes_remaining: 2 } as never);
    const first = mount();
    expect(await screen.findByText("Nur noch 2 Recovery-Code(s) übrig. Erzeuge bald neue Codes.")).toBeTruthy();
    first.unmount();
    me.mockResolvedValue({ ...user, mfa_enabled: true, mfa_recovery_codes_remaining: 0 } as never);
    mount();
    expect((await screen.findByText(/keine Recovery-Codes mehr/)).getAttribute("role")).toBe("alert");
  });

  it("erzeugt neue Codes nach Passwortabfrage; bei falschem Passwort bleibt alles wie es ist", async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValue({ ...user, mfa_enabled: true, mfa_recovery_codes_remaining: 3 } as never);
    const regen = vi.spyOn(api, "regenerateRecoveryCodes")
      .mockRejectedValueOnce(new ApiError("Passwort falsch", 403, "invalid_password"))
      .mockResolvedValueOnce({ recovery_codes: ["aaaaa-bbbbb"], recovery_codes_remaining: 10, message: "" });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Neue Codes erzeugen" }));
    fireEvent.click(screen.getByRole("button", { name: "Codes erzeugen" }));
    expect(await screen.findByText("Bitte dein Passwort eingeben")).toBeTruthy();
    expect(regen).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "falsch" } });
    fireEvent.click(screen.getByRole("button", { name: "Codes erzeugen" }));
    expect(await screen.findByText("Das Passwort ist falsch.")).toBeTruthy();
    expect(localStorage.getItem("astra_access_token")).toBe("t");
    expect(screen.queryByRole("list", { name: "Recovery-Codes" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Passwort"), { target: { value: "richtig12" } });
    fireEvent.click(screen.getByRole("button", { name: "Codes erzeugen" }));
    expect(await screen.findByText("aaaaa-bbbbb")).toBeTruthy();
    expect(regen).toHaveBeenLastCalledWith("richtig12");
  });

  it("deaktiviert MFA nach Bestätigung", async () => {
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
    fireEvent.click(await screen.findByRole("button", { name: "Löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith(9));
  });
});
