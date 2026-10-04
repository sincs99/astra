// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { PageLayout } from "./PageLayout";
import { api } from "../../services/api";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "tok-123");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 2, username: "bob", is_admin: false } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });

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

describe("Abmelden", () => {
  it("sperrt das Token am Server und leert es lokal", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ token_revoked: true }) });
    vi.stubGlobal("fetch", fetchMock);
    mount();
    fireEvent.click(screen.getAllByRole("button", { name: "Abmelden" })[0]);
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
    fireEvent.click(screen.getAllByRole("button", { name: "Abmelden" })[0]);
    await waitFor(() => expect(localStorage.getItem("astra_access_token")).toBeNull());
    await screen.findByText("Login-Seite");
  });

  it("meldet bei HTTP 500 trotzdem lokal ab", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    mount();
    fireEvent.click(screen.getAllByRole("button", { name: "Abmelden" })[0]);
    await screen.findByText("Login-Seite");
    expect(localStorage.getItem("astra_access_token")).toBeNull();
  });
});
