// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { AppRouter } from "./router";
import { api } from "../services/api";
import { resetCurrentUserCache } from "../hooks/useCurrentUser";

beforeEach(() => {
  vi.restoreAllMocks();
  resetCurrentUserCache();
  window.history.pushState({}, "", "/");
  vi.spyOn(api, "getShopProducts").mockResolvedValue([]);
  vi.spyOn(api, "getBillingInfo").mockResolvedValue({ payment_provider: "manual", online_payment: false });
  vi.spyOn(api, "getClientInstances").mockResolvedValue([]);
  vi.spyOn(api, "getMyOrders").mockResolvedValue([]);
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "bob", is_admin: false } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("Startseite /", () => {
  it("zeigt ausgeloggt die Landingpage", async () => {
    render(<AppRouter />);
    expect(await screen.findByRole("heading", { level: 1, name: /Dein Game-Server/ })).toBeTruthy();
  });

  it("zeigt angemeldet das Dashboard 'Meine Server'", async () => {
    localStorage.setItem("astra_access_token", "t");
    render(<AppRouter />);
    expect(await screen.findByRole("heading", { level: 1, name: "Meine Server" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: /Dein Game-Server/ })).toBeNull();
  });

  it("schützt weiterhin die übrigen Seiten (Shop -> Login mit Rückkehr)", async () => {
    window.history.pushState({}, "", "/orders");
    render(<AppRouter />);
    expect(await screen.findByRole("heading", { name: "Astra Login" })).toBeTruthy();
    expect(window.location.pathname + window.location.search).toBe("/login?redirect=%2Forders");
  });
});
