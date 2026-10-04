// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BackupManager } from "./BackupManager";
import { api, type BackupEntry } from "../services/api";
import { setLang } from "../i18n";

const mk = (o: Partial<BackupEntry>): BackupEntry => ({
  id: 1, uuid: "abcdef12-0000-0000-0000-000000000000", instance_id: 1, name: "Nightly", ignored_files: null, disk: "wings",
  checksum: null, bytes: 2048, is_successful: true, is_locked: false, completed_at: null,
  created_at: "2026-10-03T14:05:00Z", updated_at: null, ...o,
});

describe("BackupManager", () => {
  beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
  afterEach(() => { cleanup(); setLang("de"); });

  it("zeigt die Liste mit Spaltenköpfen (scope=col)", async () => {
    vi.spyOn(api, "getBackups").mockResolvedValue([mk({}), mk({ uuid: "ffff0000-1", name: "Locked", is_locked: true, is_successful: false })]);
    render(<BackupManager instanceUuid="u1" />);
    expect(await screen.findByText("Nightly")).toBeTruthy();
    expect(screen.getAllByText("2.0 KB").length).toBe(2);
    expect(screen.getByText("Ausstehend")).toBeTruthy();
    const ths = screen.getAllByRole("columnheader");
    expect(ths.length).toBe(5);
    ths.forEach((th) => expect(th.getAttribute("scope")).toBe("col"));
    expect(screen.queryByRole("button", { name: "Backup Locked löschen" })).toBeNull();
  });

  it("zeigt Leerzustand und Ladefehler als alert", async () => {
    vi.spyOn(api, "getBackups").mockRejectedValueOnce(new Error("kaputt"));
    render(<BackupManager instanceUuid="u1" />);
    expect((await screen.findByRole("alert")).textContent).toContain("kaputt");
  });

  it("erstellt ein Backup und meldet Erfolg per status", async () => {
    const get = vi.spyOn(api, "getBackups").mockResolvedValue([]);
    const create = vi.spyOn(api, "createBackup").mockResolvedValue(mk({}));
    render(<BackupManager instanceUuid="u1" />);
    expect(await screen.findByText("Noch keine Backups vorhanden.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Name des neuen Backups"), { target: { value: " Test " } });
    fireEvent.click(screen.getByRole("button", { name: /Backup erstellen/ }));
    await waitFor(() => expect(create).toHaveBeenCalledWith("u1", "Test"));
    expect((await screen.findByText("Backup erstellt")).closest("[role=status]")).toBeTruthy();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("löscht und stellt wieder her nur nach Bestätigung", async () => {
    vi.spyOn(api, "getBackups").mockResolvedValue([mk({})]);
    const del = vi.spyOn(api, "deleteBackup").mockResolvedValue({ message: "Gelöscht" });
    const restore = vi.spyOn(api, "restoreBackup").mockResolvedValue({ message: "Wiederhergestellt", instance_status: null });
    const conf = vi.fn().mockReturnValueOnce(false).mockReturnValue(true);
    vi.stubGlobal("confirm", conf);
    render(<BackupManager instanceUuid="u1" />);
    const delBtn = await screen.findByRole("button", { name: "Backup Nightly löschen" });
    fireEvent.click(delBtn);
    expect(conf).toHaveBeenCalledWith('Backup "Nightly" wirklich löschen?');
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(delBtn);
    await waitFor(() => expect(del).toHaveBeenCalledWith("u1", "abcdef12-0000-0000-0000-000000000000"));
    expect(await screen.findByText("Gelöscht")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Backup Nightly wiederherstellen" }));
    await waitFor(() => expect(restore).toHaveBeenCalled());
    vi.unstubAllGlobals();
  });

  it("zeigt auf Englisch übersetzte Texte", async () => {
    setLang("en");
    vi.spyOn(api, "getBackups").mockResolvedValue([mk({})]);
    const del = vi.spyOn(api, "deleteBackup").mockResolvedValue({ message: "Deleted" });
    const conf = vi.fn().mockReturnValue(true);
    vi.stubGlobal("confirm", conf);
    render(<BackupManager instanceUuid="u1" />);
    expect(await screen.findByRole("columnheader", { name: "Created" })).toBeTruthy();
    expect(screen.getByText("Successful")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create backup" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete backup Nightly" }));
    expect(conf).toHaveBeenCalledWith('Really delete backup "Nightly"?');
    await waitFor(() => expect(del).toHaveBeenCalled());
    vi.unstubAllGlobals();
  });
});
