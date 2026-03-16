import { useEffect, useState } from "react";
import { api, type BackupEntry } from "../services/api";

interface BackupManagerProps {
  instanceUuid: string;
}

export function BackupManager({ instanceUuid }: BackupManagerProps) {
  const [backups, setBackups] = useState<BackupEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [acting, setActing] = useState(false);

  const loadBackups = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBackups(instanceUuid);
      setBackups(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBackups();
  }, [instanceUuid]);

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(null), 4000);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      setActing(true);
      setError(null);
      await api.createBackup(instanceUuid, newName.trim());
      setNewName("");
      showMsg("Backup erstellt");
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setActing(false);
    }
  };

  const handleRestore = async (backup: BackupEntry) => {
    if (!confirm(`Backup "${backup.name}" wirklich wiederherstellen?`)) return;
    try {
      setActing(true);
      setError(null);
      const result = await api.restoreBackup(instanceUuid, backup.uuid);
      showMsg(result.message);
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setActing(false);
    }
  };

  const handleDelete = async (backup: BackupEntry) => {
    if (!confirm(`Backup "${backup.name}" wirklich löschen?`)) return;
    try {
      setActing(true);
      setError(null);
      const result = await api.deleteBackup(instanceUuid, backup.uuid);
      showMsg(result.message);
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setActing(false);
    }
  };

  return (
    <div>
      {/* Erstell-Formular */}
      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="Backup-Name"
          required
          style={{ flex: 1, padding: 6, fontSize: 13 }}
        />
        <button type="submit" disabled={acting} style={btnStyle}>
          {acting ? "..." : "📦 Backup erstellen"}
        </button>
      </form>

      {error && <div style={errStyle}>{error}</div>}
      {message && <div style={msgStyle}>{message}</div>}

      {/* Backup-Liste */}
      {loading ? (
        <p style={{ color: "#888" }}>Backups werden geladen...</p>
      ) : backups.length === 0 ? (
        <p style={{ color: "#888" }}>Noch keine Backups vorhanden.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #ddd" }}>
              <th style={thS}>Name</th>
              <th style={thS}>Grösse</th>
              <th style={thS}>Status</th>
              <th style={thS}>Erstellt</th>
              <th style={{ ...thS, width: 120 }}>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.uuid} style={{ borderBottom: "1px solid #eee" }}>
                <td style={tdS}>
                  {b.is_locked && "🔒 "}
                  {b.name}
                  <div style={{ fontSize: 11, color: "#aaa" }}>
                    {b.uuid.substring(0, 8)}…
                  </div>
                </td>
                <td style={tdS}>{formatBytes(b.bytes)}</td>
                <td style={tdS}>
                  {b.is_successful ? (
                    <span style={{ color: "#5cb85c" }}>✅ Erfolgreich</span>
                  ) : (
                    <span style={{ color: "#f0ad4e" }}>⏳ Ausstehend</span>
                  )}
                </td>
                <td style={tdS}>
                  {b.created_at
                    ? new Date(b.created_at).toLocaleString("de-CH")
                    : "–"}
                </td>
                <td style={tdS}>
                  <div style={{ display: "flex", gap: 4 }}>
                    {b.is_successful && (
                      <button
                        onClick={() => handleRestore(b)}
                        disabled={acting}
                        style={{ ...smBtn, color: "#5bc0de" }}
                        title="Wiederherstellen"
                      >
                        🔄
                      </button>
                    )}
                    {!b.is_locked && (
                      <button
                        onClick={() => handleDelete(b)}
                        disabled={acting}
                        style={{ ...smBtn, color: "#c00" }}
                        title="Löschen"
                      >
                        🗑
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const btnStyle: React.CSSProperties = { padding: "6px 14px", border: "1px solid #ddd", borderRadius: 4, cursor: "pointer", fontSize: 13, backgroundColor: "#fff" };
const smBtn: React.CSSProperties = { padding: "4px 8px", border: "1px solid #ddd", borderRadius: 3, backgroundColor: "#fff", cursor: "pointer", fontSize: 13 };
const thS: React.CSSProperties = { padding: 8, textAlign: "left", fontSize: 12, fontWeight: 600 };
const tdS: React.CSSProperties = { padding: 8, fontSize: 13 };
const errStyle: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#fee", border: "1px solid #c00", borderRadius: 4, color: "#c00", fontSize: 12 };
const msgStyle: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#efe", border: "1px solid #0a0", borderRadius: 4, color: "#060", fontSize: 12 };
