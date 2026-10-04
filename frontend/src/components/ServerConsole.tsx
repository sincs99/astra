import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../services/api";

type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

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
  const [lines, setLines] = useState<string[]>([]);
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

  const addLine = useCallback((text: string, prefix?: string) => {
    const formatted = prefix ? `${prefix} ${text}` : text;
    setLines((prev) => {
      const next = [...prev, formatted];
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
    addLine("Verbindung wird aufgebaut…", "[System]");

    try {
      // Credentials vom Backend holen
      const creds = await api.getWebsocketCredentials(instanceUuid);
      tokenRef.current = creds.token;

      const ws = new WebSocket(creds.socket);
      wsRef.current = ws;

      ws.onopen = () => {
        addLine("Verbunden, Anmeldung läuft…", "[System]");
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
          addLine(`Unbekannte Nachricht: ${event.data}`, "[?]");
        }
      };

      ws.onerror = () => {
        setConnectionState("error");
        setErrorMessage("Die Verbindung zur Konsole ist fehlgeschlagen.");
        addLine("Verbindung unterbrochen.", "[Fehler]");
      };

      ws.onclose = (event) => {
        setConnectionState("disconnected");
        addLine(
          `Verbindung getrennt (Code: ${event.code})`,
          "[System]"
        );
        wsRef.current = null;
      };
    } catch (err) {
      setConnectionState("error");
      const msg =
        err instanceof Error ? err.message : "Verbindung fehlgeschlagen";
      setErrorMessage(msg);
      addLine(`Fehler: ${msg}`, "[System]");
    }
  }, [instanceUuid, addLine]);

  const handleWingsEvent = useCallback(
    (data: WingsEvent) => {
      switch (data.event) {
        case "auth success":
          setConnectionState("connected");
          addLine("Verbunden.", "[System]");
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
          addLine(`Server: ${data.args[0]}`, "[Status]");
          break;

        case "stats":
          // Stats leise ignorieren (werden separat angezeigt)
          break;

        case "daemon error":
          addLine(data.args[0] || "Der Server meldet einen Fehler", "[Daemon]");
          break;

        case "token expiring":
        case "token expired":
          addLine("Sitzung wird erneuert…", "[System]");
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
      addLine("Sitzung erneuert", "[System]");
    } catch {
      addLine("Die Sitzung konnte nicht erneuert werden. Bitte lade die Seite neu.", "[Fehler]");
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

      addLine(`> ${cmd}`, "");
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

  const stateColor: Record<ConnectionState, string> = {
    disconnected: "var(--neutral)",
    connecting: "var(--warn)",
    connected: "var(--ok)",
    error: "var(--danger)",
  };

  const stateLabel: Record<ConnectionState, string> = {
    disconnected: "Getrennt",
    connecting: "Verbindet...",
    connected: "Verbunden",
    error: "Fehler",
  };

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: "50%",
              backgroundColor: stateColor[connectionState],
            }}
          />
          <span style={{ fontSize: 12, color: stateColor[connectionState] }}>
            {stateLabel[connectionState]}
          </span>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {connectionState === "disconnected" ||
          connectionState === "error" ? (
            <button onClick={connect} style={consoleBtnStyle}>
              Verbinden
            </button>
          ) : connectionState === "connected" ? (
            <button
              onClick={() => {
                wsRef.current?.close();
                setConnectionState("disconnected");
              }}
              style={consoleBtnStyle}
            >
              Trennen
            </button>
          ) : null}
          <button
            onClick={() => setLines([])}
            style={consoleBtnStyle}
            title="Ausgabe leeren"
          >
            Clear
          </button>
        </div>
      </div>

      {errorMessage && (
        <div style={consoleErrorStyle}>{errorMessage}</div>
      )}

      {/* Output */}
      <div ref={outputRef} style={consoleOutputStyle}>
        {lines.length === 0 ? (
          <div style={{ color: "var(--text-3)" }}>
            Klicke "Verbinden" um die Console zu starten...
          </div>
        ) : (
          lines.map((line, i) => (
            <div key={i} style={lineStyle(line)}>
              {line}
            </div>
          ))
        )}
      </div>

      {/* Input */}
      <div style={consoleInputContainer}>
        <span style={{ color: "var(--ok)", marginRight: 4 }}>{">"}</span>
        <input
          type="text"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            connectionState === "connected"
              ? "Befehl eingeben..."
              : "Nicht verbunden"
          }
          disabled={connectionState !== "connected"}
          style={consoleInputStyle}
        />
      </div>
    </div>
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

function lineStyle(line: string): React.CSSProperties {
  const base: React.CSSProperties = {
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
    lineHeight: 1.4,
    fontSize: 13,
  };

  if (line.startsWith("[System]")) {
    return { ...base, color: "var(--accent)" };
  }
  if (line.startsWith("[Status]")) {
    return { ...base, color: "var(--warn)" };
  }
  if (line.startsWith("[Fehler]") || line.startsWith("[Daemon]")) {
    return { ...base, color: "var(--danger)" };
  }
  if (line.startsWith(">")) {
    return { ...base, color: "var(--ok)", fontWeight: 600 };
  }
  return { ...base, color: "var(--text-console)" };
}

// ── Styles ──────────────────────────────────────────

const consoleOutputStyle: React.CSSProperties = {
  backgroundColor: "var(--console)",
  color: "var(--text-console)",
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
  fontSize: 13,
  padding: 12,
  borderRadius: "4px 4px 0 0",
  height: 300,
  overflowY: "auto",
  border: "1px solid var(--border)",
  borderBottom: "none",
};

const consoleInputContainer: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  backgroundColor: "var(--console)",
  padding: "8px 12px",
  borderRadius: "0 0 4px 4px",
  border: "1px solid var(--border)",
  borderTop: "1px solid var(--border)",
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
};

const consoleInputStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: "transparent",
  border: "none",
  outline: "none",
  color: "var(--text)",
  fontFamily: "inherit",
  fontSize: 13,
};

const consoleBtnStyle: React.CSSProperties = {
  padding: "4px 10px",
  border: "1px solid var(--border)",
  borderRadius: 4,
  backgroundColor: "var(--surface-2)",
  color: "var(--text)",
  cursor: "pointer",
  fontSize: 12,
};

const consoleErrorStyle: React.CSSProperties = {
  backgroundColor: "var(--danger-soft)",
  border: "1px solid var(--danger-border)",
  color: "var(--danger)",
  padding: 8,
  borderRadius: 4,
  marginBottom: 8,
  fontSize: 12,
};
