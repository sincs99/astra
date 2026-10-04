// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ActivityLog } from "./ActivityLog";
import { api, type ActivityLogEntry } from "../services/api";
import { setLang } from "../i18n";

const logs = [
  { id: 1, event: "backup:create", actor_id: null, actor_type: "system", description: "Backup erstellt", created_at: "2026-01-02T03:04:05" },
  { id: 2, event: "instance:start", actor_id: 7, actor_type: "user", description: null, created_at: "2026-01-02T03:05:05" },
] as ActivityLogEntry[];

describe("ActivityLog", () => {
  beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
  afterEach(() => { cleanup(); setLang("de"); });

  it("zeigt die Liste", async () => {
    vi.spyOn(api, "getInstanceActivity").mockResolvedValue(logs);
    render(<ActivityLog instanceUuid="u" />);
    expect(await screen.findByText("backup:create")).toBeTruthy();
    expect(screen.getByText("System")).toBeTruthy();
    expect(screen.getByText("Benutzer #7")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Zeit" })).toBeTruthy();
  });

  it("zeigt den Leerzustand", async () => {
    vi.spyOn(api, "getInstanceActivity").mockResolvedValue([]);
    render(<ActivityLog instanceUuid="u" />);
    expect(await screen.findByText("Keine Aktivitäten vorhanden.")).toBeTruthy();
  });

  it("zeigt Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "getInstanceActivity").mockResolvedValue(logs);
    render(<ActivityLog instanceUuid="u" />);
    expect(await screen.findByText("User #7")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Actor" })).toBeTruthy();
  });
});
