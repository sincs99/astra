// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

async function mountNav(shopEnabled: boolean, isAdmin: boolean) {
  vi.resetModules();
  vi.doMock("../../config", () => ({ SHOP_ENABLED: shopEnabled }));
  const { api } = await import("../../services/api");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "u", is_admin: isAdmin } as never);
  const { PageLayout } = await import("./PageLayout");
  render(<MemoryRouter><PageLayout title="T"><div /></PageLayout></MemoryRouter>);
  // Warten, bis der User geladen ist (Admin-Links erscheinen asynchron)
  if (isAdmin) await screen.findByRole("link", { name: "Agents" });
  else await screen.findByRole("link", { name: "Konto" });
  return (name: string) => screen.queryByRole("link", { name });
}

beforeEach(() => { localStorage.setItem("astra_access_token", `t-${Math.random()}`); });
afterEach(() => { cleanup(); localStorage.clear(); vi.doUnmock("../../config"); });

describe("Phase-4-Navigation (Feature-Flag)", () => {
  it("blendet Shop-Eintraege ohne Flag aus", async () => {
    const link = await mountNav(false, true);
    for (const name of ["Shop", "Meine Bestellungen", "Produkte", "Bestellungen"]) expect(link(name)).toBeNull();
  });

  it("zeigt Kunden mit Flag Shop und Bestellungen, aber keine Verkaufs-Admin-Links", async () => {
    const link = await mountNav(true, false);
    expect(link("Shop")?.getAttribute("href")).toBe("/shop");
    expect(link("Meine Bestellungen")?.getAttribute("href")).toBe("/orders");
    expect(link("Produkte")).toBeNull();
    expect(link("Bestellungen")).toBeNull();
  });

  it("zeigt Admins mit Flag zusaetzlich Produkte und Bestellungen", async () => {
    const link = await mountNav(true, true);
    expect(link("Produkte")?.getAttribute("href")).toBe("/admin/products");
    expect(link("Bestellungen")?.getAttribute("href")).toBe("/admin/orders");
  });
});
