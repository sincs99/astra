// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { api } from "../services/api";
import { setLang } from "../i18n";

import { AdminJobsPage } from "./AdminJobsPage";

const job = (over: Record<string, unknown> = {}) => ({
  id: 5, uuid: "u-5", job_type: "backup.run", status: "failed", attempts: 2, max_attempts: 3, payload_summary: null,
  result: null, error: "disk full", created_at: "2026-10-01T10:00:00Z", started_at: null, finished_at: null, scheduled_at: null, ...over,
});
const listOf = (items: unknown[], pages = 1) => ({ items, total: items.length, page: 1, per_page: 50, pages });
const summary = { total: 3, by_status: { failed: 1, completed: 2 }, by_type: { "backup.run": 3 } };

function mount() {
  return render(<MemoryRouter><AdminJobsPage /></MemoryRouter>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("astra_access_token", "t");
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({ id: 1, username: "root", is_admin: true } as never);
});
afterEach(() => { cleanup(); localStorage.clear(); setLang("de"); });

describe("AdminJobsPage", () => {
  it("listet Jobs mit Kacheln und filtert nach Status", async () => {
    const list = vi.spyOn(api, "getJobs").mockResolvedValue(listOf([job()]) as never);
    vi.spyOn(api, "getJobsSummary").mockResolvedValue(summary);
    mount();
    expect(await screen.findByText("backup.run", { selector: "td span" })).toBeTruthy();
    expect(screen.getByText("disk full")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Job-Übersicht" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "failed" } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ status: "failed", page: 1 })));
  });

  it("blättert zwischen Seiten", async () => {
    const list = vi.spyOn(api, "getJobs").mockResolvedValue(listOf([job()], 3) as never);
    vi.spyOn(api, "getJobsSummary").mockResolvedValue(summary);
    mount();
    await screen.findByText("Seite 1 / 3");
    fireEvent.click(screen.getByRole("button", { name: "Weiter" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("zeigt Fehler und lädt erneut", async () => {
    const list = vi.spyOn(api, "getJobs").mockRejectedValueOnce(new Error("boom")).mockResolvedValue(listOf([job()]) as never);
    vi.spyOn(api, "getJobsSummary").mockResolvedValue(summary);
    mount();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("boom");
    fireEvent.click(within(alert).getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByText("disk full");
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("zeigt den Leerzustand", async () => {
    vi.spyOn(api, "getJobs").mockResolvedValue(listOf([]) as never);
    vi.spyOn(api, "getJobsSummary").mockResolvedValue(summary);
    mount();
    expect(await screen.findByText("Keine Jobs gefunden.")).toBeTruthy();
  });

  it("zeigt die Seite auf Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getJobs").mockResolvedValue(listOf([job()]) as never);
    vi.spyOn(api, "getJobsSummary").mockResolvedValue(summary);
    mount();
    expect(await screen.findByRole("columnheader", { name: "Attempts" })).toBeTruthy();
    expect(screen.getByText("Background jobs")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeTruthy();
  });
});
