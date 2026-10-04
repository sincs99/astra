import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../services/api";
import { t } from "../i18n";

type ConnectionState = "disconnected" | "connecting" | "connected" | "error";
type LineKind = "system" | "status" | "error" | "daemon" | "cmd" | "out";

interface ConsoleLine {
  kind: LineKind;
  text: string;
}

interface WingsEvent {
  event: string;
  args: string[];
}

interface Props {
  instanceUuid: string;
}

export function ServerConsole({ instanceUuid }: Props) {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [lines, setLines] = useState<ConsoleLine[]>([]);
  const [command, setCommand] = useState("");
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const tokenRef = useRef<string | null>(null);

  // Auto-scroll
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [lines]);

  const addLine = useCallback((text: string, kind: LineKind = "out") => {
    setLines((prev) => {
      const next = [...prev, { kind, text }];
      // Max 500 Zeilen behalten
      return next.length > 500 ? next.slice(-500) : next;
    });
  }, []);

  const connect = useCallback(async () => {
    // Bestehende Verbindung schliessen
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState("connecting");
    setErrorMessage(null);
    addLine(t("sconsole.connecting"), "system");

    try {
      // Credentials vom Backend holen
      const creds = await api.getWebsocketCredentials(instanceUuid);
      tokenRef.current = creds.token;

      const ws = new WebSocket(creds.socket);
      wsRef.current = ws;

      ws.onopen = () => {
        addLine(t("sconsole.connectedAuth"), "system");
        // Auth-Event senden
        ws.send(
          JSON.stringify({
            event: "auth",
            args: [creds.token],
          })
        );
      };

      ws.onmessage = (event) => {
        try {
          const data: WingsEvent = JSON.parse(event.data);
          handleWingsEvent(data);
        } catch {
          addLine(t("sconsole.unknownMessage", { text: String(event.data) }), "error");
        }
      };

      ws.onerror = () => {
        setConnectionState("error");
        setErrorMessage(t("sconsole.connectionFailed"));
        addLine(t("sconsole.connectionLost"), "error");
      };

      ws.onclose = (event) => {
        setConnectionState("disconnected");
        addLine(t("sconsole.closed", { code: event.code }), "system");
        wsRef.current = null;
      };
    } catch (err) {
      setConnectionState("error");
      const msg =
        err instanceof Error ? err.message : t("sconsole.failedGeneric");
      setErrorMessage(msg);
      addLine(t("sconsole.errorLine", { message: msg }), "system");
    }
  }, [instanceUuid, addLine]);

  const handleWingsEvent = useCallback(
    (data: WingsEvent) => {
      switch (data.event) {
        case "auth success":
          setConnectionState("connected");
          addLine(t("sconsole.connected"), "system");
          // Logs anfordern
          wsRef.current?.send(
            JSON.stringify({ event: "send logs", args: [null] })
          );
          break;

        case "console output":
        case "install output":
          if (data.args[0]) {
            // ANSI-Codes für einfache Darstellung entfernen
            const clean = stripAnsi(data.args[0]);
            addLine(clean);
          }
          break;

        case "status":
          addLine(t("sconsole.serverStatus", { state: String(data.args[0]) }), "status");
          break;

        case "stats":
          // Stats leise ignorieren (werden separat angezeigt)
          break;

        case "daemon error":
          addLine(data.args[0] || t("sconsole.daemonDefault"), "daemon");
          break;

        case "token expiring":
        case "token expired":
          addLine(t("sconsole.renewing"), "system");
          renewToken();
          break;

        default:
          // Unbekannte Events leise ignorieren
          break;
      }
    },
    [addLine]
  );

  const renewToken = useCallback(async () => {
    try {
      const creds = await api.getWebsocketCredentials(instanceUuid);
      tokenRef.current = creds.token;
      wsRef.current?.send(
        JSON.stringify({ event: "auth", args: [creds.token] })
      );
      addLine(t("sconsole.renewed"), "system");
    } catch {
      addLine(t("sconsole.renewFailed"), "error");
    }
  }, [instanceUuid, addLine]);

  const sendCommand = useCallback(
    (cmd: string) => {
      if (
        !cmd.trim() ||
        !wsRef.current ||
        connectionState !== "connected"
      ) {
        return;
      }

      wsRef.current.send(
        JSON.stringify({ event: "send command", args: [cmd] })
      );

      addLine(`> ${cmd}`, "cmd");
      setCommandHistory((prev) => [...prev, cmd]);
      setHistoryIndex(-1);
      setCommand("");
    },
    [connectionState, addLine]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      sendCommand(command);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (commandHistory.length > 0) {
        const newIdx =
          historyIndex === -1
            ? commandHistory.length - 1
            : Math.max(0, historyIndex - 1);
        setHistoryIndex(newIdx);
        setCommand(commandHistory[newIdx]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIndex >= 0) {
        const newIdx = historyIndex + 1;
        if (newIdx >= commandHistory.length) {
          setHistoryIndex(-1);
          setCommand("");
        } else {
          setHistoryIndex(newIdx);
          setCommand(commandHistory[newIdx]);
        }
      }
    }
  };

  // Disconnect bei Unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const stateDot: Record<ConnectionState, string> = {
    disconnected: "",
    connecting: "dot-warn",
    connected: "dot-ok",
    error: "dot-danger",
  };

  const stateLabel: Record<ConnectionState, string> = {
    disconnected: t("sconsole.stateDisconnected"),
    connecting: t("sconsole.stateConnecting"),
    connected: t("sconsole.stateConnected"),
    error: t("sconsole.stateError"),
  };

  const online = connectionState === "connected";

  return (
    <section className="card" aria-label={t("sconsole.title")}>
      <div className="row-actions" style={{ marginTop: 0 }}>
        <span className="hint" role="status" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span
            className={`dot ${stateDot[connectionState]}`}
            style={connectionState === "disconnected" ? { background: "var(--text-3)" } : undefined}
            aria-hidden="true"
          />
          {stateLabel[connectionState]}
        </span>
        <span className="push" style={{ display: "inline-flex", gap: 8 }}>
          {connectionState === "disconnected" || connectionState === "error" ? (
            <button type="button" className="btn btn-sm btn-primary" onClick={connect}>
              {t("sconsole.connect")}
            </button>
          ) : online ? (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                wsRef.current?.close();
                setConnectionState("disconnected");
              }}
            >
              {t("sconsole.disconnect")}
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setLines([])}
            aria-label={t("sconsole.clearAria")}
          >
            {t("sconsole.clear")}
          </button>
        </span>
      </div>

      {errorMessage && (
        <div className="banner banner-danger" role="alert">
          <span className="banner-text text-danger">{errorMessage}</span>
        </div>
      )}

      <div
        ref={outputRef}
        className="box-console mono"
        role="log"
        aria-label={t("sconsole.outputLabel")}
        tabIndex={0}
        style={{ height: 300, overflowY: "auto", gap: 0 }}
      >
        {lines.length === 0 ? (
          <div style={{ color: "var(--console-dim)" }}>{t("sconsole.empty")}</div>
        ) : (
          lines.map((line, i) => (
            <div key={i} style={lineStyle(line.kind)}>
              {line.text}
            </div>
          ))
        )}
      </div>

      <div className="box-console mono" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <span style={{ color: "var(--ok)" }} aria-hidden="true">
          {">"}
        </span>
        <input
          type="text"
          className="inp mono"
          style={{ background: "transparent", border: "none", boxShadow: "none", color: "var(--text-console)", flex: 1 }}
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label={t("sconsole.inputLabel")}
          placeholder={online ? t("sconsole.placeholderConnected") : t("sconsole.placeholderOffline")}
          disabled={!online}
          autoComplete="off"
          spellCheck={false}
        />
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => sendCommand(command)}
          disabled={!online || !command.trim()}
          aria-label={t("sconsole.send")}
        >
          {t("sconsole.send")}
        </button>
      </div>
    </section>
  );
}

// ── Hilfsfunktionen ──────────────────────────────────

function stripAnsi(text: string): string {
  // Entfernt ANSI-Escape-Codes für einfache Text-Darstellung
  return text.replace(
    // eslint-disable-next-line no-control-regex
    /\u001b\[[0-9;]*[a-zA-Z]/g,
    ""
  );
}

const LINE_COLOR: Record<LineKind, string> = {
  system: "var(--accent)",
  status: "var(--warn)",
  error: "var(--danger)",
  daemon: "var(--danger)",
  cmd: "var(--ok)",
  out: "var(--text-console)",
};

function lineStyle(kind: LineKind): React.CSSProperties {
  return {
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
    lineHeight: 1.4,
    fontSize: "var(--fs-small)",
    color: LINE_COLOR[kind],
    fontWeight: kind === "cmd" ? 600 : undefined,
  };
}
