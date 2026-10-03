// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "../../services/api";
import { PageLayout } from "./PageLayout";

async function mountNav(isAdmin: boolean) {
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "u", is_admin: isAdmin } as never);
  render(<MemoryRouter><PageLayout title="T"><div /></PageLayout></MemoryRouter>);
  // Warten, bis der User geladen ist (Admin-Links erscheinen asynchron)
  if (isAdmin) await screen.findByRole("link", { name: "Agents" });
  else await screen.findByRole("link", { name: "Konto" });
  return (name: string) => screen.queryByRole("link", { name });
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", `t-${Math.random()}`);
});
afterEach(() => { cleanup(); localStorage.clear(); });

describe("Navigation (Shop und Verkauf)", () => {
  it("zeigt Kunden Shop und Bestellungen, aber keine Verkaufs-Admin-Links", async () => {
    const link = await mountNav(false);
    expect(link("Shop")?.getAttribute("href")).toBe("/shop");
    expect(link("Meine Bestellungen")?.getAttribute("href")).toBe("/orders");
    expect(link("Produkte")).toBeNull();
    expect(link("Bestellungen")).toBeNull();
    expect(link("Agents")).toBeNull();
  });

  it("zeigt Admins zusätzlich Produkte und Bestellungen", async () => {
    const link = await mountNav(true);
    expect(link("Shop")).toBeTruthy();
    expect(link("Produkte")?.getAttribute("href")).toBe("/admin/products");
    expect(link("Bestellungen")?.getAttribute("href")).toBe("/admin/orders");
  });
});
