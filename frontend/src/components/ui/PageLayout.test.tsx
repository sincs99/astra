// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { PageLayout } from "./PageLayout";
import { api } from "../../services/api";
import { resetCurrentUserCache } from "../../hooks/useCurrentUser";
import { LangRoot } from "../../i18n/LangRoot";
import { setLang } from "../../i18n";

beforeEach(() => {
  resetCurrentUserCache();
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "tok-123");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); setLang("de"); });

function mount() {
  return render(
    <MemoryRouter initialEntries={["/orders"]}>
      <Routes>
        <Route path="/orders" element={<PageLayout title="Test">inhalt</PageLayout>} />
        <Route path="/login" element={<div>Login-Seite</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function logoutViaMenu() {
  fireEvent.click(await screen.findByRole("button", { name: "Nutzermenü" }));
  fireEvent.click(screen.getByRole("button", { name: "Abmelden" }));
}

describe("Abmelden", () => {
  it("sperrt das Token am Server und leert es lokal", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ token_revoked: true }) });
    vi.stubGlobal("fetch", fetchMock);
    mount();
    await logoutViaMenu();
    await screen.findByText("Login-Seite");
    const call = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/auth/logout"));
    expect(call).toBeTruthy();
    expect(call![1].method).toBe("POST");
    expect(call![1].headers.Authorization).toBe("Bearer tok-123");
    expect(localStorage.getItem("astra_access_token")).toBeNull();
  });

  it("meldet auch bei Serverfehler oder Netzwerkproblem lokal ab", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    mount();
    await logoutViaMenu();
    await waitFor(() => expect(localStorage.getItem("astra_access_token")).toBeNull());
    await screen.findByText("Login-Seite");
  });

  it("meldet bei HTTP 500 trotzdem lokal ab", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    mount();
    await logoutViaMenu();
    await screen.findByText("Login-Seite");
    expect(localStorage.getItem("astra_access_token")).toBeNull();
  });
});

describe("Seitenleiste", () => {
  beforeEach(() => { document.documentElement.lang = "de"; });

  it("markiert den aktuellen Eintrag und nutzt bei verschachtelten Pfaden den längsten Treffer", async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
    render(
      <MemoryRouter initialEntries={["/admin/agents/monitoring"]}>
        <PageLayout title="Test">x</PageLayout>
      </MemoryRouter>,
    );
    const monitoring = await screen.findByRole("link", { name: "Fleet Monitoring" });
    expect(monitoring.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Agents" }).getAttribute("aria-current")).toBeNull();
  });

  it("klappt auf Icons ein (Links behalten ihren Namen) und merkt sich den Zustand", async () => {
    mount();
    const toggle = await screen.findByRole("button", { name: "Seitenleiste einklappen" });
    fireEvent.click(toggle);
    expect(localStorage.getItem("astra_sidebar_collapsed")).toBe("1");
    expect(screen.getByRole("button", { name: "Seitenleiste ausklappen" }).getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("link", { name: "Shop" }).getAttribute("title")).toBe("Shop");
    cleanup();
    mount();
    expect(await screen.findByRole("button", { name: "Seitenleiste ausklappen" })).toBeTruthy();
  });

  it("zeigt Titel, Untertitel und Aktionen in der Seitenkopfzeile", async () => {
    render(
      <MemoryRouter><PageLayout title="Meine Server" subtitle="3 Server" actions={<button type="button">Neuer Server</button>}>x</PageLayout></MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Meine Server" })).toBeTruthy();
    expect(screen.getByText("3 Server")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Neuer Server" })).toBeTruthy();
  });

  it("wechselt im Nutzermenü die Sprache", async () => {
    render(
      <MemoryRouter initialEntries={["/orders"]}>
        <LangRoot><PageLayout title="Test">inhalt</PageLayout></LangRoot>
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Nutzermenü" }));
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(await screen.findByRole("link", { name: "My orders" })).toBeTruthy();
  });
});

describe("Mobile Kopfzeile", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {},
    }));
  });

  it("öffnet ein Vollbild-Menü mit 44-px-Hamburger, Navigation und Abmelden; Escape schliesst", async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValue({ id: 1, username: "pascal.kone", is_admin: false } as never);
    mount();
    const burger = await screen.findByRole("button", { name: "Menü öffnen" });
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(burger);
    const dialog = await screen.findByRole("dialog", { name: "Menü" });
    expect(within(dialog).getByRole("link", { name: "Shop" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Abmelden" })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(await screen.findByText("PK")).toBeTruthy();
  });
});
