// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { RegisterPage } from "./RegisterPage";
import { api } from "../services/api";
import { getLang, setLang } from "../i18n";

const user = { id: 1, username: "anna", email: "a@b.de", is_admin: false, created_at: null, updated_at: null };

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); setLang("de"); });
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("Sprache bei Login und Registrierung (M67)", () => {
  it("übernimmt nach dem Login die am Konto gespeicherte Sprache", async () => {
    vi.spyOn(api, "login").mockResolvedValue({ access_token: "t", token_type: "bearer", user: { ...user, locale: "en" } });
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Benutzername oder E-Mail"), { target: { value: "anna" } });
    fireEvent.change(screen.getByLabelText("Passwort", { exact: true }), { target: { value: "geheim123" } });
    fireEvent.click(screen.getByRole("button", { name: /Anmelden/ }));
    await waitFor(() => expect(getLang()).toBe("en"));
  });

  it("behält die Browser-Sprache, wenn am Konto keine gesetzt ist (Backend ohne Feld oder null)", async () => {
    setLang("en");
    vi.spyOn(api, "login").mockResolvedValue({ access_token: "t", token_type: "bearer", user });
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Username or email"), { target: { value: "anna" } });
    fireEvent.change(screen.getByLabelText("Password", { exact: true }), { target: { value: "geheim123" } });
    fireEvent.click(screen.getByRole("button", { name: /Sign in|Log in/ }));
    await waitFor(() => expect(api.login).toHaveBeenCalled());
    expect(getLang()).toBe("en");
  });

  it("sendet bei der Registrierung die aktuelle UI-Sprache als locale mit", async () => {
    setLang("en");
    const register = vi.spyOn(api, "register").mockResolvedValue({ verification_required: true, message: "ok", user } as never);
    render(<MemoryRouter><RegisterPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "anna" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.de" } });
    fireEvent.change(screen.getByLabelText("Password", { exact: true }), { target: { value: "geheim12345" } });
    fireEvent.change(screen.getByLabelText("Repeat password"), { target: { value: "geheim12345" } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Create account/ }));
    await waitFor(() => expect(register).toHaveBeenCalledWith("anna", "a@b.de", "geheim12345", "en"));
  });
});
