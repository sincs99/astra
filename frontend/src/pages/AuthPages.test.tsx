// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { api, ApiError, getAccessToken } from "../services/api";

function mount(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<div>Dashboard</div>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/password-reset/confirm" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const type = (label: RegExp | string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
const submit = (name: RegExp | string) => fireEvent.click(screen.getByRole("button", { name }));

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });
afterEach(() => { cleanup(); });

describe("LoginPage", () => {
  it("meldet an, speichert das Token und leitet zum Dashboard", async () => {
    vi.spyOn(api, "login").mockResolvedValue({ access_token: "tok", token_type: "Bearer", user: {} } as never);
    mount("/login");
    type("Username oder Email", " alice ");
    type("Passwort", "geheim123");
    submit("Anmelden");
    expect(await screen.findByText("Dashboard")).toBeTruthy();
    expect(getAccessToken()).toBe("tok");
    expect(api.login).toHaveBeenCalledWith("alice", "geheim123", undefined);
  });

  it("fragt bei aktivem MFA den Code ab und sendet ihn im zweiten Schritt mit", async () => {
    const login = vi.spyOn(api, "login")
      .mockResolvedValueOnce({ requires_mfa: true, message: "MFA-Code erforderlich" })
      .mockResolvedValueOnce({ access_token: "mfa-tok", token_type: "Bearer", user: {} } as never);
    mount("/login");
    type("Username oder Email", "alice");
    type("Passwort", "geheim123");
    submit("Anmelden");
    const codeField = await screen.findByLabelText("Authenticator-Code");
    expect(getAccessToken()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Bestaetigen" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/Code/);
    fireEvent.change(codeField, { target: { value: " 123456 " } });
    submit("Bestaetigen");
    expect(await screen.findByText("Dashboard")).toBeTruthy();
    expect(login).toHaveBeenLastCalledWith("alice", "geheim123", "123456");
    expect(getAccessToken()).toBe("mfa-tok");
  });

  it("verlangt beide Felder", async () => {
    const login = vi.spyOn(api, "login");
    mount("/login");
    submit("Anmelden");
    expect((await screen.findByRole("alert")).textContent).toMatch(/eingeben/);
    expect(login).not.toHaveBeenCalled();
  });

  it("bietet bei unbestaetigter E-Mail das erneute Senden an", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new ApiError("E-Mail nicht bestaetigt", 403, "email_not_verified"));
    const resend = vi.spyOn(api, "resendVerification").mockResolvedValue({ message: "ok" } as never);
    mount("/login");
    type("Username oder Email", "alice");
    type("Passwort", "geheim123");
    submit("Anmelden");
    fireEvent.click(await screen.findByRole("button", { name: /Bestaetigungs-Mail erneut senden/ }));
    await waitFor(() => expect(resend).toHaveBeenCalledWith("alice"));
    expect(await screen.findByText(/neue Bestaetigungs-Mail/)).toBeTruthy();
  });

  it("zeigt Hinweise nach Passwort-Reset und abgelaufener Sitzung", () => {
    mount("/login?reset=1");
    expect(screen.getByRole("status").textContent).toMatch(/Passwort wurde geaendert/);
    cleanup();
    mount("/login?expired=1");
    expect(screen.getByRole("status").textContent).toMatch(/abgelaufen/);
  });
});

describe("RegisterPage", () => {
  function fill(password = "langgenug1", confirm = password) {
    type("Benutzername", "bob");
    type("E-Mail", "bob@example.com");
    type("Passwort", password);
    type("Passwort wiederholen", confirm);
  }

  it("validiert vor dem Request", async () => {
    const register = vi.spyOn(api, "register");
    mount("/register");
    fill("kurz");
    submit("Konto erstellen");
    expect((await screen.findByRole("alert")).textContent).toMatch(/mindestens 8 Zeichen/);
    fill("langgenug1", "anders1234");
    submit("Konto erstellen");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/stimmen nicht ueberein/));
    expect(register).not.toHaveBeenCalled();
  });

  it("loggt nach erfolgreicher Registrierung direkt ein", async () => {
    vi.spyOn(api, "register").mockResolvedValue({ access_token: "neu", token_type: "Bearer", user: {} } as never);
    mount("/register");
    fill();
    submit("Konto erstellen");
    expect(await screen.findByText("Dashboard")).toBeTruthy();
    expect(getAccessToken()).toBe("neu");
  });

  it("zeigt bei aktiver E-Mail-Verifizierung den Hinweis statt einzuloggen", async () => {
    vi.spyOn(api, "register").mockResolvedValue({ verification_required: true, message: "x", user: {} } as never);
    const resend = vi.spyOn(api, "resendVerification").mockResolvedValue({ message: "ok" } as never);
    mount("/register");
    fill();
    submit("Konto erstellen");
    expect(await screen.findByText(/bob@example.com/)).toBeTruthy();
    expect(getAccessToken()).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Erneut senden" }));
    await waitFor(() => expect(resend).toHaveBeenCalledWith("bob@example.com"));
  });

  it("meldet eine deaktivierte Registrierung klar", async () => {
    vi.spyOn(api, "register").mockRejectedValue(new ApiError("Registrierung ist deaktiviert", 403));
    mount("/register");
    fill();
    submit("Konto erstellen");
    expect(await screen.findByText(/Registrierung ist deaktiviert\. Bitte wende dich/)).toBeTruthy();
  });
});

describe("ResetPasswordPage", () => {
  it("meldet fehlenden Token", () => {
    mount("/password-reset/confirm");
    expect(screen.getByRole("alert").textContent).toMatch(/es fehlt der Token/);
  });

  it("setzt das Passwort und leitet mit Hinweis zum Login", async () => {
    const confirm = vi.spyOn(api, "confirmPasswordReset").mockResolvedValue({ message: "ok" });
    mount("/password-reset/confirm?token=abc");
    type("Neues Passwort", "neuespasswort1");
    type("Passwort wiederholen", "neuespasswort1");
    submit("Passwort speichern");
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("abc", "neuespasswort1"));
    expect((await screen.findByRole("status")).textContent).toMatch(/Passwort wurde geaendert/);
  });
});
