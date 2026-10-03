import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Instance } from "../services/api";
import { sftpUsername } from "../lib/sftp";
import { cardStyle, linkStyle, btnDefault } from "./ui";

interface SftpAccessProps {
  instance: Instance;
}

function CopyValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard nicht verfuegbar: Wert bleibt markierbar
    }
  };
  return (
    <tr>
      <th scope="row" style={{ textAlign: "left", fontWeight: 600, fontSize: 13, color: "#555", padding: "4px 12px 4px 0", whiteSpace: "nowrap" }}>
        {label}
      </th>
      <td style={{ padding: "4px 0" }}>
        <code style={{ userSelect: "all", background: "#f5f5f5", padding: "2px 6px", borderRadius: 4, fontSize: 13 }}>{value}</code>
        <button type="button" onClick={copy} aria-label={`${label} kopieren`} style={{ ...btnDefault, padding: "2px 8px", fontSize: 12, marginLeft: 8 }}>
          {copied ? "✓ Kopiert" : "📋"}
        </button>
      </td>
    </tr>
  );
}

/** SFTP-Zugangsdaten fuer eine Instance (Host, Port, Benutzername). */
export function SftpAccess({ instance }: SftpAccessProps) {
  const [username, setUsername] = useState<string | null>(null);
  const [adminPort, setAdminPort] = useState<number | null>(null);

  const host = instance.connection?.host ?? null;
  const port = instance.connection?.sftp_port ?? adminPort;

  useEffect(() => {
    let cancelled = false;
    api.getCurrentUser()
      .then(async (user) => {
        if (cancelled) return;
        setUsername(user.username);
        // Admins koennen den SFTP-Port aus der Agent-Liste lesen, falls das Backend ihn nicht mitliefert
        if (user.is_admin && instance.connection?.sftp_port === undefined) {
          const agent = (await api.getAgents()).find((a) => a.id === instance.agent_id);
          if (!cancelled && agent) setAdminPort(agent.daemon_sftp);
        }
      })
      .catch(() => { /* Box bleibt ohne Benutzername ausgeblendet */ });
    return () => { cancelled = true; };
  }, [instance.agent_id, instance.connection?.sftp_port]);

  if (!host || !username) return null;

  return (
    <div style={cardStyle}>
      <h3 style={{ marginTop: 0 }}>SFTP-Zugang</h3>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          <CopyValue label="Host" value={host} />
          {port !== null && port !== undefined && <CopyValue label="Port" value={String(port)} />}
          <CopyValue label="Benutzername" value={sftpUsername(username, instance.uuid)} />
        </tbody>
      </table>
      <p style={{ color: "#666", fontSize: 12, margin: "8px 0 0" }}>
        Passwort = Panel-Passwort oder ein hinterlegter SSH-Key.{" "}
        <Link to="/account/ssh-keys" style={linkStyle}>SSH-Keys verwalten</Link>
      </p>
    </div>
  );
}
