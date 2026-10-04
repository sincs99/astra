// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ServerConsole } from "./ServerConsole";
import { api } from "../services/api";
import { setLang } from "../i18n";

class FakeWS {
  static last: FakeWS | null = null;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(public url: string) { FakeWS.last = this; }
  send(d: string) { this.sent.push(d); }
  close() { this.onclose?.({ code: 1000 }); }
}

async function connect() {
  fireEvent.click(screen.getByRole("button", { name: /Verbinden|Connect/ }));
  await waitFor(() => expect(FakeWS.last).not.toBeNull());
  act(() => FakeWS.last!.onopen!());
  return FakeWS.last!;
}
const emit = (ws: FakeWS, event: string, args: string[]) =>
  act(() => ws.onmessage!({ data: JSON.stringify({ event, args }) }));

describe("ServerConsole", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setLang("de");
    FakeWS.last = null;
    vi.stubGlobal("WebSocket", FakeWS);
    vi.spyOn(api, "getWebsocketCredentials").mockResolvedValue({ token: "tok", socket: "wss://x/ws" });
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); setLang("de"); });

  it("verbindet, sendet Auth, zeigt Ausgabe und sendet Befehle", async () => {
    render(<ServerConsole instanceUuid="u1" />);
    expect(screen.getByText("Getrennt")).toBeTruthy();
    const ws = await connect();
    expect(ws.url).toBe("wss://x/ws");
    expect(JSON.parse(ws.sent[0])).toEqual({ event: "auth", args: ["tok"] });
    expect(screen.getByText("Verbunden, Anmeldung läuft…")).toBeTruthy();

    emit(ws, "auth success", []);
    expect(await screen.findByText("Verbunden")).toBeTruthy();
    expect(JSON.parse(ws.sent[1]).event).toBe("send logs");

    emit(ws, "console output", ["\u001b[31mHallo Welt\u001b[0m"]);
    expect(screen.getByText("Hallo Welt")).toBeTruthy();

    const input = screen.getByLabelText("Konsolenbefehl") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "say hi" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(JSON.parse(ws.sent[2])).toEqual({ event: "send command", args: ["say hi"] });
    expect(screen.getByText("> say hi")).toBeTruthy();
    expect(input.value).toBe("");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("say hi");
  });

  it("Eingabe ist ohne Verbindung gesperrt; Clear leert die Ausgabe", async () => {
    render(<ServerConsole instanceUuid="u1" />);
    expect((screen.getByLabelText("Konsolenbefehl") as HTMLInputElement).disabled).toBe(true);
    await connect();
    fireEvent.click(screen.getByRole("button", { name: "Ausgabe leeren" }));
    expect(screen.queryByText("Verbunden, Anmeldung läuft…")).toBeNull();
  });

  it("zeigt Verbindungsfehler als alert", async () => {
    render(<ServerConsole instanceUuid="u1" />);
    const ws = await connect();
    act(() => ws.onerror!());
    expect((await screen.findByRole("alert")).textContent).toContain("Die Verbindung zur Konsole ist fehlgeschlagen.");
  });

  it("zeigt Texte auf Englisch", async () => {
    setLang("en");
    render(<ServerConsole instanceUuid="u1" />);
    expect(screen.getByText("Disconnected")).toBeTruthy();
    const ws = await connect();
    expect(screen.getByText("Connected, signing in…")).toBeTruthy();
    emit(ws, "status", ["running"]);
    expect(screen.getByText("Server: running")).toBeTruthy();
    emit(ws, "auth success", []);
    expect(await screen.findByLabelText("Console command")).toBeTruthy();
  });
});
