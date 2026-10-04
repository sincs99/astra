// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { friendlyApiMessage } from "../lib/errors";
import { isManualPayment } from "../lib/checkout";
import { setLang } from "../i18n";

function respond(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}
const sentHeaders = (spy: ReturnType<typeof respond>) => (spy.mock.calls[0][1] as RequestInit).headers as Record<string, string>;

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); setLang("de"); });
afterEach(() => { localStorage.clear(); setLang("de"); });

describe("Accept-Language (M72)", () => {
  it("sendet bei jedem Request die Sprache der Oberfläche", async () => {
    let spy = respond(200, []);
    await api.getMyOrders();
    expect(sentHeaders(spy)["Accept-Language"]).toBe("de");
    spy.mockRestore();
    setLang("en");
    spy = respond(200, []);
    await api.getMyOrders();
    expect(sentHeaders(spy)["Accept-Language"]).toBe("en");
    spy.mockRestore();
    spy = respond(200, { message: "ok" });
    await api.requestPasswordReset("a@b.de");
    expect(sentHeaders(spy)["Accept-Language"]).toBe("en");
  });
});

describe("Fehlertexte (M72)", () => {
  it("zeigt den Server-Text, wenn die Antwort {error, code} hat, und behält den code", async () => {
    setLang("en");
    respond(429, { error: "Too many attempts", code: "rate_limited", retry_after_seconds: 90 });
    const err = await api.login("a", "b").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Too many attempts");
    expect(err.code).toBe("rate_limited");
    expect(err.status).toBe(429);
    expect(err.data?.retry_after_seconds).toBe(90);
  });

  it("fällt ohne Server-Text auf die Frontend-Übersetzung zurück (DE und EN)", async () => {
    respond(500, {});
    expect((await api.getMyOrders().catch((e) => e)).message).toMatch(/Fehler aufgetreten/);
    vi.restoreAllMocks();
    setLang("en");
    respond(404, "kaputt");
    expect((await api.getMyOrders().catch((e) => e)).message).toBe("That could not be found.");
  });

  it("korrigiert ASCII-Umlaute nur in der deutschen Oberfläche", () => {
    expect(friendlyApiMessage(400, "Ungueltige Eingabe")).toBe("Ungültige Eingabe");
    setLang("en");
    expect(friendlyApiMessage(400, "Ungueltige Eingabe")).toBe("Ungueltige Eingabe");
    expect(friendlyApiMessage(400, "Invalid input")).toBe("Invalid input");
  });

  it("erkennt Sonderfälle am code, nicht am Text", () => {
    expect(isManualPayment(new ApiError("Payments are handled by the operator", 409, "manual"))).toBe(true);
    expect(isManualPayment(new ApiError("Something else", 409, "stale"))).toBe(false);
  });
});
