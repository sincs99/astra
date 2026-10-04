import { useEffect, useState } from "react";
import {
  api,
  type CollaboratorEntry,
  type User,
  ALL_PERMISSIONS,
} from "../services/api";
import { hasKey, t } from "../i18n";
import { Icon } from "./ui/Icon";

interface CollaboratorManagerProps {
  instanceUuid: string;
  isOwner: boolean;
}

/** Übersetzt ein API-Recht; unbekannte Werte werden roh angezeigt. */
function permLabel(p: string): string {
  const key = `susers.perm.${p}`;
  return hasKey(key) ? t(key) : p;
}

const chipStyle = (on: boolean): React.CSSProperties => ({
  display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", cursor: "pointer",
  fontSize: "var(--fs-small)", border: "1px solid var(--border)", borderRadius: "var(--radius-badge)",
  background: on ? "var(--accent-soft)" : "var(--surface-2)", color: "var(--text)",
});

export function CollaboratorManager({ instanceUuid, isOwner }: CollaboratorManagerProps) {
  const [collaborators, setCollaborators] = useState<CollaboratorEntry[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const [newUserId, setNewUserId] = useState<number | "">("");
  const [newPerms, setNewPerms] = useState<string[]>([]);

  const [editId, setEditId] = useState<number | null>(null);
  const [editPerms, setEditPerms] = useState<string[]>([]);

  const fail = (err: unknown) => setError(err instanceof Error ? err.message : t("susers.failed"));

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [collabs, userList] = await Promise.all([
        api.getCollaborators(instanceUuid),
        api.getUsers(),
      ]);
      setCollaborators(collabs);
      setUsers(userList);
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOwner) loadAll();
  }, [instanceUuid, isOwner]);

  const showMsg = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(null), 3000);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserId || newPerms.length === 0) return;
    try {
      setActing(true);
      setError(null);
      await api.addCollaborator(instanceUuid, newUserId as number, newPerms);
      setNewUserId("");
      setNewPerms([]);
      showMsg(t("susers.added"));
      await loadAll();
    } catch (err) {
      fail(err);
    } finally {
      setActing(false);
    }
  };

  const handleUpdate = async (id: number) => {
    try {
      setActing(true);
      setError(null);
      await api.updateCollaborator(instanceUuid, id, editPerms);
      setEditId(null);
      showMsg(t("susers.updated"));
      await loadAll();
    } catch (err) {
      fail(err);
    } finally {
      setActing(false);
    }
  };

  const handleDelete = async (c: CollaboratorEntry) => {
    if (!confirm(t("susers.removeConfirm"))) return;
    try {
      setActing(true);
      setError(null);
      await api.deleteCollaborator(instanceUuid, c.id);
      showMsg(t("susers.removed"));
      await loadAll();
    } catch (err) {
      fail(err);
    } finally {
      setActing(false);
    }
  };

  const togglePerm = (list: string[], perm: string): string[] =>
    list.includes(perm) ? list.filter((p) => p !== perm) : [...list, perm];

  if (!isOwner) {
    return <p className="hint">{t("susers.ownerOnly")}</p>;
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      {error && <div className="banner banner-danger" role="alert">{error}</div>}
      {message && <div className="banner banner-info" role="status">{message}</div>}

      <form onSubmit={handleAdd} className="stack" style={{ gap: 10 }}>
        <div className="row-actions" style={{ marginTop: 0 }}>
          <div className="field" style={{ flex: "1 1 220px" }}>
            <label htmlFor="collab-user" className="sr-only">{t("susers.selectUser")}</label>
            <select id="collab-user" className="inp" value={newUserId} required
              onChange={(e) => setNewUserId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">{t("susers.selectPlaceholder")}</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.username} ({u.email})</option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={acting || newPerms.length === 0} className="btn btn-primary">
            <Icon name="plus" /> {t("susers.add")}
          </button>
        </div>
        <fieldset className="fieldset" style={{ gap: 8 }}>
          <legend className="sr-only">{t("susers.permissions")}</legend>
          <div className="row-actions" style={{ marginTop: 0 }}>
            {ALL_PERMISSIONS.map((p) => (
              <label key={p} style={chipStyle(newPerms.includes(p))}>
                <input type="checkbox" checked={newPerms.includes(p)} onChange={() => setNewPerms(togglePerm(newPerms, p))} />
                {permLabel(p)}
              </label>
            ))}
          </div>
        </fieldset>
      </form>

      {loading ? (
        <p className="hint">{t("susers.loading")}</p>
      ) : collaborators.length === 0 ? (
        <div className="card-empty">{t("susers.empty")}</div>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {collaborators.map((c) => {
            const user = users.find((u) => u.id === c.user_id);
            const name = user?.username ?? t("susers.userFallback", { id: c.user_id });
            const isEditing = editId === c.id;
            return (
              <div key={c.id} className="card">
                <div className="row-actions" style={{ marginTop: 0 }}>
                  <span className="card-title">{name}</span>
                  <span className="push row-actions" style={{ marginTop: 0 }}>
                    {isEditing ? (
                      <>
                        <button type="button" className="btn btn-sm btn-icon" onClick={() => handleUpdate(c.id)} disabled={acting}
                          aria-label={t("susers.save")} title={t("susers.save")}><Icon name="check" /></button>
                        <button type="button" className="btn btn-sm btn-icon" onClick={() => setEditId(null)}
                          aria-label={t("susers.cancel")} title={t("susers.cancel")}><Icon name="close" /></button>
                      </>
                    ) : (
                      <>
                        <button type="button" className="btn btn-sm btn-icon" onClick={() => { setEditId(c.id); setEditPerms([...c.permissions]); }}
                          aria-label={`${t("susers.edit")}: ${name}`} title={t("susers.edit")}><Icon name="settings" /></button>
                        <button type="button" className="btn btn-sm btn-icon btn-danger-text" onClick={() => handleDelete(c)} disabled={acting}
                          aria-label={`${t("susers.remove")}: ${name}`} title={t("susers.remove")}><Icon name="close" /></button>
                      </>
                    )}
                  </span>
                </div>
                <div className="row-actions" style={{ marginTop: 0 }}>
                  {isEditing ? (
                    ALL_PERMISSIONS.map((p) => (
                      <label key={p} style={chipStyle(editPerms.includes(p))}>
                        <input type="checkbox" checked={editPerms.includes(p)} onChange={() => setEditPerms(togglePerm(editPerms, p))} />
                        {permLabel(p)}
                      </label>
                    ))
                  ) : (
                    c.permissions.map((p) => (
                      <span key={p} className="card-sub" style={{ padding: "2px 8px", background: "var(--accent-soft)", borderRadius: "var(--radius-badge)", color: "var(--text)" }}>{permLabel(p)}</span>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
