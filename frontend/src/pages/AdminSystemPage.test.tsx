// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "../services/api";
import { setLang } from "../i18n";

import { AdminSystemPage } from "./AdminSystemPage";

const version = { version: "1.2.3", release_phase: "pilot", build_sha: null, build_date: null, build_ref: null, environment: "production", service: "astra" };
const upgrade = {
  version: "1.2.3", build: { version: "1.2.3", build_sha: null, build_date: null, build_ref: null }, environment: "production",
  migration: { current_head: "abc", applied_revision: "abc", is_up_to_date: true, pending_migrations: 2, error: null }, upgrade_required: false,
};
const preflight = { checks: { database: "ok" }, issues: ["Disk low"], overall_status: "warning", compatible: false, timestamp: "x" };

function mount() {
  return render(<MemoryRouter><AdminSystemPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
  vi.spyOn(api, "getBillingStatus").mockRejectedValue(new Error("404"));
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("AdminSystemPage", () => {
  it("zeigt Version, Migration und Preflight", async () => {
    vi.spyOn(api, "getSystemVersion").mockResolvedValue(version);
    vi.spyOn(api, "getUpgradeStatus").mockResolvedValue(upgrade as never);
    vi.spyOn(api, "getPreflight").mockResolvedValue(preflight);
    mount();
    expect(await screen.findByText("1.2.3", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("2 Migration(en)")).toBeTruthy();
    expect(screen.getByText("Disk low")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Preflight-Prüfung" })).toBeTruthy();
  });

  it("aktualisiert per Button", async () => {
    const v = vi.spyOn(api, "getSystemVersion").mockResolvedValue(version);
    vi.spyOn(api, "getUpgradeStatus").mockResolvedValue(upgrade as never);
    vi.spyOn(api, "getPreflight").mockRejectedValue(new Error("x"));
    mount();
    await screen.findByText("astra");
    fireEvent.click(screen.getByRole("button", { name: "Aktualisieren" }));
    await waitFor(() => expect(v).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("heading", { name: "Preflight-Prüfung" })).toBeNull();
  });

  it("zeigt einen Ladefehler als Alert", async () => {
    vi.spyOn(api, "getSystemVersion").mockRejectedValue(new Error("down"));
    vi.spyOn(api, "getUpgradeStatus").mockResolvedValue(upgrade as never);
    mount();
    expect((await screen.findByRole("alert")).textContent).toContain("down");
  });

  it("zeigt die Seite auf Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getSystemVersion").mockResolvedValue(version);
    vi.spyOn(api, "getUpgradeStatus").mockResolvedValue(upgrade as never);
    vi.spyOn(api, "getPreflight").mockResolvedValue(preflight);
    mount();
    expect(await screen.findByRole("heading", { name: "Migration & upgrade" })).toBeTruthy();
    expect(screen.getByText("2 migration(s)")).toBeTruthy();
    expect(screen.getAllByText("n/a").length).toBeGreaterThan(0);
  });
});
