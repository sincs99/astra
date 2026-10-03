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

  it("sendet beim Passwort-Reset das Feld 'password'", async () => {
    const fetchMock = mockFetch(200, { message: "ok" });
    await api.confirmPasswordReset("t", "geheim123");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ token: "t", password: "geheim123" });
  });
});
