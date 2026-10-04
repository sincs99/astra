import { useEffect, useState } from "react";
import { api, type BackupEntry } from "../services/api";
import { formatDateTime } from "../lib/dates";
import { dateLocale, t } from "../i18n";
import { Icon } from "./ui/Icon";

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
      setError(err instanceof Error ? err.message : t("sbackups.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBackups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instanceUuid]);

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(null), 4000);
  };

  const run = async (action: () => Promise<string | null>) => {
    try {
      setActing(true);
      setError(null);
      const msg = await action();
      if (msg) showMsg(msg);
      await loadBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("sbackups.actionFailed"));
    } finally {
      setActing(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    await run(async () => {
      await api.createBackup(instanceUuid, name);
      setNewName("");
      return t("sbackups.created");
    });
  };

  const handleRestore = async (backup: BackupEntry) => {
    if (!confirm(t("sbackups.restoreConfirm", { name: backup.name }))) return;
    await run(async () => (await api.restoreBackup(instanceUuid, backup.uuid)).message);
  };

  const handleDelete = async (backup: BackupEntry) => {
    if (!confirm(t("sbackups.deleteConfirm", { name: backup.name }))) return;
    await run(async () => (await api.deleteBackup(instanceUuid, backup.uuid)).message);
  };

  return (
    <div className="stack" style={{ gap: 12 }}>
      <form onSubmit={handleCreate} className="row-actions" style={{ marginTop: 0, flexWrap: "nowrap" }}>
        <input
          type="text"
          className="inp"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder={t("sbackups.namePlaceholder")}
          aria-label={t("sbackups.nameLabel")}
          required
        />
        <button type="submit" className="btn btn-primary" disabled={acting}>
          <Icon name="package" />
          {t("sbackups.create")}
        </button>
      </form>

      {error && (
        <div className="banner banner-danger" role="alert">
          <span className="banner-text text-danger">{error}</span>
        </div>
      )}
      {message && (
        <div className="banner" role="status">
          <span className="dot dot-ok" aria-hidden="true" />
          <span className="banner-text">{message}</span>
        </div>
      )}

      {loading ? (
        <p className="hint" role="status">{t("sbackups.loading")}</p>
      ) : backups.length === 0 ? (
        <p className="hint">{t("sbackups.empty")}</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="tbl" aria-label={t("sbackups.listLabel")}>
            <thead>
              <tr>
                <th scope="col">{t("sbackups.colName")}</th>
                <th scope="col">{t("sbackups.colSize")}</th>
                <th scope="col">{t("sbackups.colStatus")}</th>
                <th scope="col">{t("sbackups.colCreated")}</th>
                <th scope="col">{t("sbackups.colActions")}</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((b) => (
                <tr key={b.uuid}>
                  <td>
                    {b.name}
                    {b.is_locked && <span className="hint"> ({t("sbackups.locked")})</span>}
                    <div className="hint mono">{b.uuid.substring(0, 8)}…</div>
                  </td>
                  <td className="mono">{formatBytes(b.bytes)}</td>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span className={`dot ${b.is_successful ? "dot-ok" : "dot-warn"}`} aria-hidden="true" />
                      {b.is_successful ? t("sbackups.ok") : t("sbackups.pending")}
                    </span>
                  </td>
                  <td>{formatDateTime(b.created_at)}</td>
                  <td>
                    <div className="row-actions" style={{ marginTop: 0, flexWrap: "nowrap" }}>
                      {b.is_successful && (
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => handleRestore(b)}
                          disabled={acting}
                          aria-label={t("sbackups.restoreAria", { name: b.name })}
                        >
                          <Icon name="restart" size={14} />
                          {t("sbackups.restore")}
                        </button>
                      )}
                      {!b.is_locked && (
                        <button
                          type="button"
                          className="btn btn-sm btn-danger-text"
                          onClick={() => handleDelete(b)}
                          disabled={acting}
                          aria-label={t("sbackups.deleteAria", { name: b.name })}
                        >
                          {t("sbackups.delete")}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatBytes(bytes: number): string {
  const nf = (n: number) => n.toLocaleString(dateLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${nf(bytes / 1024)} KB`;
  return `${nf(bytes / (1024 * 1024))} MB`;
}
