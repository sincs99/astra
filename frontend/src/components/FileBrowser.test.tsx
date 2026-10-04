// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FileBrowser } from "./FileBrowser";
import { api, type FileEntry } from "../services/api";
import { setLang } from "../i18n";

const entry = (name: string, dir: boolean, size = 10): FileEntry =>
  ({ name, path: `/${name}`, is_directory: dir, is_file: !dir, size } as FileEntry);

const root = { directory: "/", entries: [entry("logs", true, 0), entry("a.txt", false, 5)] };

describe("FileBrowser", () => {
  beforeEach(() => { vi.restoreAllMocks(); setLang("de"); });
  afterEach(() => { cleanup(); setLang("de"); });

  it("laedt und zeigt die Dateiliste", async () => {
    vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    render(<FileBrowser instanceUuid="u1" />);
    expect(await screen.findByRole("button", { name: "Datei a.txt öffnen" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeTruthy();
    expect(screen.getByText("5 B")).toBeTruthy();
  });

  it("oeffnet einen Ordner", async () => {
    const list = vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    render(<FileBrowser instanceUuid="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Ordner logs öffnen" }));
    await waitFor(() => expect(list).toHaveBeenCalledWith("u1", "/logs"));
  });

  it("oeffnet eine Datei und speichert", async () => {
    vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    vi.spyOn(api, "readFile").mockResolvedValue({ path: "/a.txt", content: "alt" } as never);
    const write = vi.spyOn(api, "writeFile").mockResolvedValue(undefined as never);
    render(<FileBrowser instanceUuid="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Datei a.txt öffnen" }));
    const area = await screen.findByLabelText("Inhalt von /a.txt");
    const save = screen.getByRole("button", { name: "Speichern" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.change(area, { target: { value: "neu" } });
    fireEvent.click(save);
    await waitFor(() => expect(write).toHaveBeenCalledWith("u1", "/a.txt", "neu"));
    expect(await screen.findByText("Datei gespeichert.")).toBeTruthy();
  });

  it("loescht nach Bestaetigung", async () => {
    const list = vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    const del = vi.spyOn(api, "deleteFile").mockResolvedValue(undefined as never);
    const conf = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<FileBrowser instanceUuid="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "a.txt löschen" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("u1", "/a.txt"));
    expect(conf).toHaveBeenCalledWith("'/a.txt' wirklich löschen?");
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
  });

  it("loescht nicht, wenn abgebrochen", async () => {
    vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    const del = vi.spyOn(api, "deleteFile");
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<FileBrowser instanceUuid="u1" />);
    fireEvent.click(await screen.findByRole("button", { name: "a.txt löschen" }));
    expect(del).not.toHaveBeenCalled();
  });

  it("lehnt zu grosse Uploads ab", async () => {
    vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    const write = vi.spyOn(api, "writeFile");
    render(<FileBrowser instanceUuid="u1" />);
    await screen.findByRole("button", { name: "Datei a.txt öffnen" });
    const big = new File(["x"], "big.txt", { type: "text/plain" });
    Object.defineProperty(big, "size", { value: 2 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText("Dateien hochladen"), { target: { files: [big] } });
    expect(await screen.findByText("'big.txt' ist zu gross (max. 1 MB).")).toBeTruthy();
    expect(write).not.toHaveBeenCalled();
  });

  it("zeigt Texte auf Englisch", async () => {
    setLang("en");
    vi.spyOn(api, "listFiles").mockResolvedValue(root as never);
    render(<FileBrowser instanceUuid="u1" />);
    expect(await screen.findByRole("button", { name: "Open file a.txt" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Upload" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Size" })).toBeTruthy();
  });

  it("zeigt Ladefehler als Alert", async () => {
    vi.spyOn(api, "listFiles").mockRejectedValue(new Error("kaputt"));
    render(<FileBrowser instanceUuid="u1" />);
    expect((await screen.findByRole("alert")).textContent).toContain("kaputt");
  });
});
