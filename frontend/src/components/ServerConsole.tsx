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
    addLine("Verbindung wird aufgebaut...", "[System]");

    try {
      // Credentials vom Backend holen
      const creds = await api.getWebsocketCredentials(instanceUuid);
      tokenRef.current = creds.token;

      const ws = new WebSocket(creds.socket);
      wsRef.current = ws;

      ws.onopen = () => {
        addLine("WebSocket verbunden, authentifiziere...", "[System]");
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
        setErrorMessage("WebSocket-Verbindungsfehler");
        addLine("Verbindungsfehler!", "[Fehler]");
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
          addLine("Authentifizierung erfolgreich!", "[System]");
          // Logs anfordern
          wsRef.current?.send(
            JSON.stringify({ event: "send logs", args: [null] })
          );
          break;

        case "console output":
        case "install output":
          if (data.args[0]) {
            // ANSI-Codes fuer einfache Darstellung entfernen
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
          addLine(data.args[0] || "Daemon-Fehler", "[Daemon]");
          break;

        case "token expiring":
        case "token expired":
          addLine("Token laeuft ab, erneuere...", "[System]");
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
      addLine("Token erneuert", "[System]");
    } catch {
      addLine("Token-Erneuerung fehlgeschlagen", "[Fehler]");
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
    disconnected: "#999",
    connecting: "#f0ad4e",
    connected: "#5cb85c",
    error: "#d9534f",
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
          <div style={{ color: "#666" }}>
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
        <span style={{ color: "#5cb85c", marginRight: 4 }}>{">"}</span>
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
  // Entfernt ANSI-Escape-Codes fuer einfache Text-Darstellung
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
    return { ...base, color: "#5bc0de" };
  }
  if (line.startsWith("[Status]")) {
    return { ...base, color: "#f0ad4e" };
  }
  if (line.startsWith("[Fehler]") || line.startsWith("[Daemon]")) {
    return { ...base, color: "#d9534f" };
  }
  if (line.startsWith(">")) {
    return { ...base, color: "#5cb85c", fontWeight: 600 };
  }
  return { ...base, color: "#ddd" };
}

// ── Styles ──────────────────────────────────────────

const consoleOutputStyle: React.CSSProperties = {
  backgroundColor: "#1a1a2e",
  color: "#ddd",
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
  fontSize: 13,
  padding: 12,
  borderRadius: "4px 4px 0 0",
  height: 300,
  overflowY: "auto",
  border: "1px solid #333",
  borderBottom: "none",
};

const consoleInputContainer: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  backgroundColor: "#1a1a2e",
  padding: "8px 12px",
  borderRadius: "0 0 4px 4px",
  border: "1px solid #333",
  borderTop: "1px solid #444",
  fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
};

const consoleInputStyle: React.CSSProperties = {
  flex: 1,
  backgroundColor: "transparent",
  border: "none",
  outline: "none",
  color: "#eee",
  fontFamily: "inherit",
  fontSize: 13,
};

const consoleBtnStyle: React.CSSProperties = {
  padding: "4px 10px",
  border: "1px solid #555",
  borderRadius: 4,
  backgroundColor: "#333",
  color: "#eee",
  cursor: "pointer",
  fontSize: 12,
};

const consoleErrorStyle: React.CSSProperties = {
  backgroundColor: "#3a1a1a",
  border: "1px solid #d9534f",
  color: "#f99",
  padding: 8,
  borderRadius: 4,
  marginBottom: 8,
  fontSize: 12,
};
