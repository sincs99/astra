// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RoutineManager } from "./RoutineManager";
import { api, type RoutineEntry } from "../services/api";
import { setLang } from "../i18n";

const routine = {
  id: 1, instance_id: 1, name: "Nightly", cron_minute: "0", cron_hour: "3", cron_day_month: "*", cron_month: "*", cron_day_week: "*",
  is_active: true, is_processing: false, only_when_online: false, last_run_at: null, next_run_at: null,
  actions: [{ id: 5, routine_id: 1, sequence: 1, action_type: "create_backup", payload: {}, delay_seconds: 0 }],
} as unknown as RoutineEntry;

describe("RoutineManager", () => {
  beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
  afterEach(() => { cleanup(); setLang("de"); });

  it("zeigt die Liste", async () => {
    vi.spyOn(api, "getRoutines").mockResolvedValue([routine]);
    render(<RoutineManager instanceUuid="u" />);
    expect(await screen.findByText("Nightly")).toBeTruthy();
    expect(screen.getByText("aktiv")).toBeTruthy();
  });

  it("legt eine Routine an", async () => {
    vi.spyOn(api, "getRoutines").mockResolvedValue([]);
    const create = vi.spyOn(api, "createRoutine").mockResolvedValue(routine as never);
    render(<RoutineManager instanceUuid="u" />);
    fireEvent.change(await screen.findByLabelText("Routine-Name"), { target: { value: " Neu " } });
    fireEvent.click(screen.getByRole("button", { name: /Routine anlegen/ }));
    await waitFor(() => expect(create).toHaveBeenCalledWith("u", { name: "Neu" }));
    expect((await screen.findByRole("status")).textContent).toBe("Routine erstellt");
  });

  it("löscht nach Bestätigung", async () => {
    vi.spyOn(api, "getRoutines").mockResolvedValue([routine]);
    const del = vi.spyOn(api, "deleteRoutine").mockResolvedValue(undefined as never);
    const conf = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<RoutineManager instanceUuid="u" />);
    fireEvent.click(await screen.findByRole("button", { name: "Routine löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("u", 1));
    expect(conf).toHaveBeenCalledWith('Routine "Nightly" löschen?');
  });

  it("zeigt Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getRoutines").mockResolvedValue([routine]);
    render(<RoutineManager instanceUuid="u" />);
    expect(await screen.findByText("active")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show actions" }));
    expect(screen.getAllByText("Create backup").length).toBe(2);
    expect(screen.getByRole("columnheader", { name: "Type" })).toBeTruthy();
  });
});
