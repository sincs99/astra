// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RegisterPage } from "./RegisterPage";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { LoginPage } from "./LoginPage";
import { api, ApiError } from "../services/api";
import { setLang } from "../i18n";
import { resetCaptchaScriptsForTests } from "../lib/captcha";

const TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/api.js";
const HCAPTCHA = "https://js.hcaptcha.com/1/api.js";
const scripts = () => Array.from(document.querySelectorAll("script")).map((s) => s.getAttribute("src"));

type Opts = { sitekey: string; theme: string; callback: (t: string) => void; "expired-callback": () => void };
let widget: { render: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn>; remove: ReturnType<typeof vi.fn>; opts?: Opts };

function installWidget(name: "turnstile" | "hcaptcha") {
  widget = {
    render: vi.fn((_el: HTMLElement, opts: Opts) => { widget.opts = opts; return "w1"; }),
    reset: vi.fn(), remove: vi.fn(),
  };
  (window as unknown as Record<string, unknown>)[name] = widget;
}
/** Das Script "laden": Tag finden und das load-Ereignis auslösen. */
async function finishLoading(src: string) {
  const el = await waitFor(() => {
    const found = document.querySelector(`script[src="${src}"]`);
    if (!found) throw new Error("kein Script");
    return found;
  });
  el.dispatchEvent(new Event("load"));
  await waitFor(() => expect(widget.render).toHaveBeenCalled());
}

function fillRegister() {
  fireEvent.change(screen.getByLabelText("Benutzername"), { target: { value: "anna" } });
  fireEvent.change(screen.getByLabelText("E-Mail"), { target: { value: "a@b.de" } });
  fireEvent.change(screen.getByLabelText("Passwort", { exact: true }), { target: { value: "geheim12345" } });
  fireEvent.change(screen.getByLabelText("Passwort wiederholen"), { target: { value: "geheim12345" } });
  fireEvent.click(screen.getByRole("checkbox"));
}
const mountRegister = () => render(<MemoryRouter><RegisterPage /></MemoryRouter>);
const verify = { verification_required: true, message: "ok", user: { id: 1, username: "anna", email: "a@b.de", is_admin: false, created_at: null, updated_at: null } } as never;

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  setLang("de");
  resetCaptchaScriptsForTests();
  document.head.querySelectorAll("script").forEach((s) => s.remove());
  delete (window as unknown as Record<string, unknown>).turnstile;
  delete (window as unknown as Record<string, unknown>).hcaptcha;
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("Registrierungsschutz (M71)", () => {
  it("lädt ohne Anbieter kein Script und sendet kein captcha_token", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "none", site_key: null });
    const register = vi.spyOn(api, "register").mockResolvedValue(verify);
    mountRegister();
    fillRegister();
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    await waitFor(() => expect(register).toHaveBeenCalledWith("anna", "a@b.de", "geheim12345", "de"));
    expect(scripts().filter((s) => s === TURNSTILE || s === HCAPTCHA)).toHaveLength(0);
    expect(screen.queryByTestId("captcha-host")).toBeNull();
  });

  it("lädt bei Turnstile genau das Cloudflare-Script, rendert mit Theme/Sprache und sendet das Token", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "turnstile", site_key: "site-123" });
    const register = vi.spyOn(api, "register").mockResolvedValue(verify);
    installWidget("turnstile");
    document.documentElement.setAttribute("data-theme", "light");
    mountRegister();
    await finishLoading(TURNSTILE);
    expect(scripts().filter((s) => s === HCAPTCHA)).toHaveLength(0);
    expect(widget.opts).toMatchObject({ sitekey: "site-123", theme: "light", language: "de" });
    expect(screen.getByText(/Cloudflare Turnstile/)).toBeTruthy();
    fillRegister();
    act(() => widget.opts!.callback("tok-1"));
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    await waitFor(() => expect(register).toHaveBeenCalledWith("anna", "a@b.de", "geheim12345", "de", { captcha_token: "tok-1" }));
    document.documentElement.removeAttribute("data-theme");
  });

  it("lädt bei hCaptcha das hCaptcha-Script", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "hcaptcha", site_key: "hk" });
    installWidget("hcaptcha");
    mountRegister();
    await finishLoading(HCAPTCHA);
    expect(widget.opts).toMatchObject({ sitekey: "hk" });
    expect(scripts().filter((s) => s === TURNSTILE)).toHaveLength(0);
  });

  it("verlangt das Token, bevor etwas gesendet wird", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "turnstile", site_key: "k" });
    const register = vi.spyOn(api, "register").mockResolvedValue(verify);
    installWidget("turnstile");
    mountRegister();
    await finishLoading(TURNSTILE);
    fillRegister();
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Bitte schließe die Sicherheitsprüfung ab.");
    expect(register).not.toHaveBeenCalled();
  });

  it("setzt das Widget nach captcha_failed zurück und zeigt den Hinweis", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "turnstile", site_key: "k" });
    vi.spyOn(api, "register").mockRejectedValue(new ApiError("x", 400, "captcha_failed", { code: "captcha_failed" }));
    installWidget("turnstile");
    mountRegister();
    await finishLoading(TURNSTILE);
    fillRegister();
    act(() => widget.opts!.callback("tok"));
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Die Sicherheitsprüfung ist fehlgeschlagen. Bitte versuche es erneut.");
    await waitFor(() => expect(widget.reset).toHaveBeenCalledWith("w1"));
  });

  it("zeigt bei captcha_unavailable (503) den Dienst-Hinweis", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "none", site_key: null });
    vi.spyOn(api, "register").mockRejectedValue(new ApiError("x", 503, "captcha_unavailable"));
    mountRegister();
    fillRegister();
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Der Prüfdienst ist gerade nicht erreichbar. Bitte versuche es später erneut.");
  });

  it("sendet bei gefülltem Köder-Feld nichts", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "none", site_key: null });
    const register = vi.spyOn(api, "register").mockResolvedValue(verify);
    const { container } = mountRegister();
    fillRegister();
    const honeypot = container.querySelector('input[name="website"]') as HTMLInputElement;
    expect(honeypot.tabIndex).toBe(-1);
    expect(honeypot.autocomplete).toBe("off");
    expect(honeypot.closest("[aria-hidden='true']")).toBeTruthy();
    fireEvent.change(honeypot, { target: { value: "http://spam.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    await new Promise((r) => setTimeout(r, 30));
    expect(register).not.toHaveBeenCalled();
  });

  it("zeigt bei 429 den Wartehinweis in Minuten (aufgerundet) und sperrt den Button", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "none", site_key: null });
    vi.spyOn(api, "register").mockRejectedValue(new ApiError("x", 429, "rate_limited", { retry_after_seconds: 150 }));
    mountRegister();
    fillRegister();
    fireEvent.click(screen.getByRole("button", { name: "Konto erstellen" }));
    expect((await screen.findByText("Zu viele Versuche, bitte in 3 Minuten erneut.")).textContent).toBeTruthy();
    expect((screen.getByRole("button", { name: "Konto erstellen" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("behandelt eine fehlende Captcha-Konfiguration (Fehler/404) wie 'kein Captcha'", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    await expect(api.getCaptchaConfig()).resolves.toEqual({ provider: "none", site_key: null });
    fetchSpy.mockResolvedValue(new Response(JSON.stringify({ provider: "turnstile" }), { status: 200 }));
    await expect(api.getCaptchaConfig()).resolves.toEqual({ provider: "none", site_key: null });
  });
});

describe("Passwort vergessen und Login: Captcha und Ratenlimit", () => {
  it("sendet bei der Passwort-Anfrage das Token mit", async () => {
    vi.spyOn(api, "getCaptchaConfig").mockResolvedValue({ provider: "turnstile", site_key: "k" });
    const reset = vi.spyOn(api, "requestPasswordReset").mockResolvedValue({ message: "ok" });
    installWidget("turnstile");
    render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>);
    await finishLoading(TURNSTILE);
    fireEvent.change(screen.getByLabelText("E-Mail"), { target: { value: "a@b.de" } });
    act(() => widget.opts!.callback("tok-9"));
    fireEvent.click(screen.getByRole("button", { name: /Link anfordern|Zurücksetzen|senden/i }));
    await waitFor(() => expect(reset).toHaveBeenCalledWith("a@b.de", "tok-9"));
  });

  it("zeigt beim Login ein 429 als Wartehinweis (1 Minute) und sperrt den Button", async () => {
    vi.spyOn(api, "login").mockRejectedValue(new ApiError("x", 429, "rate_limited", { retry_after_seconds: 30 }));
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("Benutzername oder E-Mail"), { target: { value: "anna" } });
    fireEvent.change(screen.getByLabelText("Passwort", { exact: true }), { target: { value: "geheim123" } });
    fireEvent.click(screen.getByRole("button", { name: /Anmelden/ }));
    expect(await screen.findByText("Zu viele Versuche, bitte in 1 Minute erneut.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Anmelden/ }) as HTMLButtonElement).disabled).toBe(true);
  });
});
