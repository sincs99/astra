// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CollaboratorManager } from "./CollaboratorManager";
import { api, type CollaboratorEntry, type User } from "../services/api";
import { setLang } from "../i18n";

const users = [{ id: 2, username: "bob", email: "bob@x.de" }, { id: 3, username: "eve", email: "eve@x.de" }] as User[];
const collab = { id: 9, user_id: 2, instance_id: 1, permissions: ["control.start", "weird.perm"] } as CollaboratorEntry;

function mockLoad(list: CollaboratorEntry[]) {
  vi.spyOn(api, "getCollaborators").mockResolvedValue(list);
  vi.spyOn(api, "getUsers").mockResolvedValue(users);
}

describe("CollaboratorManager", () => {
  beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
  afterEach(() => { cleanup(); setLang("de"); });

  it("zeigt Liste mit übersetzten und rohen Rechten", async () => {
    mockLoad([collab]);
    render(<CollaboratorManager instanceUuid="u" isOwner />);
    expect(await screen.findByText("bob")).toBeTruthy();
    expect(screen.getAllByText("Starten").length).toBeGreaterThan(0);
    expect(screen.getByText("weird.perm")).toBeTruthy();
  });

  it("fügt einen Mitbenutzer hinzu", async () => {
    mockLoad([]);
    const add = vi.spyOn(api, "addCollaborator").mockResolvedValue(collab as never);
    render(<CollaboratorManager instanceUuid="u" isOwner />);
    await screen.findByText("Keine Mitbenutzer vorhanden.");
    fireEvent.change(screen.getByLabelText("Benutzer auswählen"), { target: { value: "3" } });
    fireEvent.click(screen.getByLabelText("Konsole"));
    fireEvent.click(screen.getByRole("button", { name: /Hinzufügen/ }));
    await waitFor(() => expect(add).toHaveBeenCalledWith("u", 3, ["control.console"]));
  });

  it("entfernt nach Bestätigung", async () => {
    mockLoad([collab]);
    const del = vi.spyOn(api, "deleteCollaborator").mockResolvedValue(undefined as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<CollaboratorManager instanceUuid="u" isOwner />);
    fireEvent.click(await screen.findByRole("button", { name: "Mitbenutzer entfernen: bob" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("u", 9));
  });

  it("zeigt Englisch", async () => {
    setLang("en");
    mockLoad([collab]);
    render(<CollaboratorManager instanceUuid="u" isOwner />);
    expect(await screen.findByRole("button", { name: "Remove collaborator: bob" })).toBeTruthy();
    expect(screen.getAllByText("Start").length).toBeGreaterThan(0);
  });
});
