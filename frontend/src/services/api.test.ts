// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, getAccessToken, setAccessToken } from "./api";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("api.request", () => {
  const assign = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    assign.mockReset();
    vi.stubGlobal("location", { pathname: "/admin/jobs", assign });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("sendet den Bearer-Token mit", async () => {
    setAccessToken("tok");
    const fetchMock = mockFetch(200, []);
    await api.getAgents();
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer tok");
  });

  it("verwirft den Token und leitet bei 401 zum Login um", async () => {
    setAccessToken("tok");
    mockFetch(401, { error: "expired" });
    await expect(api.getAgents()).rejects.toThrow("expired");
    expect(getAccessToken()).toBeNull();
    expect(assign).toHaveBeenCalledWith("/login?expired=1");
  });

  it("behandelt ein falsches Passwort beim Login nicht als abgelaufene Sitzung", async () => {
    setAccessToken("alt");
    mockFetch(401, { error: "Ungueltige Zugangsdaten" });
    await expect(api.login("a", "b")).rejects.toThrow("Ungueltige Zugangsdaten");
    expect(assign).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("alt");
  });

  it("behandelt ein falsches aktuelles Passwort beim Passwort-Aendern nicht als abgelaufene Sitzung", async () => {
    setAccessToken("tok");
    mockFetch(401, { error: "Aktuelles Passwort ist falsch" });
    await expect(api.changePassword("falsch", "neuespasswort1")).rejects.toThrow("Aktuelles Passwort ist falsch");
    expect(assign).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("tok");
  });

  it("zeigt bei fehlender Admin-Berechtigung eine verstaendliche Meldung", async () => {
    setAccessToken("tok");
    mockFetch(403, { error: "Admin-Berechtigung erforderlich" });
    await expect(api.getAgents()).rejects.toThrow("Nur Administratoren");
  });

  it("meldet einen nicht erreichbaren Server verstaendlich", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.getAgents()).rejects.toThrow("nicht erreichbar");
  });

  it("sendet beim Loeschen den Namen als Bestaetigung bzw. force als Admin", async () => {
    const fetchMock = mockFetch(200, { uuid: "u", message: "ok" });
    await api.deleteInstance("u1", "Mein Server");
    expect(fetchMock.mock.calls[0][0]).toContain("/client/instances/u1");
    expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ confirm: "Mein Server" });
    await api.adminDeleteInstance("u1", true);
    expect(fetchMock.mock.calls[1][0]).toContain("/admin/instances/u1");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ force: true });
    await api.adminDeleteInstance("u1");
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({});
  });

  it("sendet beim Passwort-Reset das Feld 'password'", async () => {
    const fetchMock = mockFetch(200, { message: "ok" });
    await api.confirmPasswordReset("t", "geheim123");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ token: "t", password: "geheim123" });
  });
});
