import { useEffect, useState } from "react";
import {
  api,
  type CollaboratorEntry,
  type User,
  ALL_PERMISSIONS,
} from "../services/api";

interface CollaboratorManagerProps {
  instanceUuid: string;
  isOwner: boolean;
}

export function CollaboratorManager({ instanceUuid, isOwner }: CollaboratorManagerProps) {
  const [collaborators, setCollaborators] = useState<CollaboratorEntry[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  // Add-Form
  const [newUserId, setNewUserId] = useState<number | "">("");
  const [newPerms, setNewPerms] = useState<string[]>([]);

  // Edit
  const [editId, setEditId] = useState<number | null>(null);
  const [editPerms, setEditPerms] = useState<string[]>([]);

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
      setError(err instanceof Error ? err.message : "Fehler");
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
      showMsg("Collaborator hinzugefügt");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
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
      showMsg("Permissions aktualisiert");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setActing(false);
    }
  };

  const handleDelete = async (c: CollaboratorEntry) => {
    if (!confirm("Collaborator wirklich entfernen?")) return;
    try {
      setActing(true);
      setError(null);
      await api.deleteCollaborator(instanceUuid, c.id);
      showMsg("Collaborator entfernt");
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setActing(false);
    }
  };

  const togglePerm = (list: string[], perm: string): string[] =>
    list.includes(perm) ? list.filter((p) => p !== perm) : [...list, perm];

  if (!isOwner) {
    return <p style={{ color: "#888", fontSize: 13 }}>Nur der Owner kann Collaborators verwalten.</p>;
  }

  return (
    <div>
      {error && <div style={errStyle}>{error}</div>}
      {message && <div style={msgStyle}>{message}</div>}

      {/* Add-Formular */}
      <form onSubmit={handleAdd} style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <select
            value={newUserId}
            onChange={(e) => setNewUserId(e.target.value ? Number(e.target.value) : "")}
            required
            style={{ padding: 6, fontSize: 13, flex: 1 }}
          >
            <option value="">– User wählen –</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.username} ({u.email})</option>
            ))}
          </select>
          <button type="submit" disabled={acting || newPerms.length === 0} style={btnS}>
            + Hinzufügen
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {ALL_PERMISSIONS.map((p) => (
            <label key={p} style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 2, padding: "2px 6px", border: "1px solid #ddd", borderRadius: 3, backgroundColor: newPerms.includes(p) ? "#e8f0fe" : "#fff", cursor: "pointer" }}>
              <input type="checkbox" checked={newPerms.includes(p)} onChange={() => setNewPerms(togglePerm(newPerms, p))} style={{ width: 12, height: 12 }} />
              {p}
            </label>
          ))}
        </div>
      </form>

      {/* Liste */}
      {loading ? (
        <p style={{ color: "#888" }}>Wird geladen...</p>
      ) : collaborators.length === 0 ? (
        <p style={{ color: "#888", fontSize: 13 }}>Keine Collaborators vorhanden.</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {collaborators.map((c) => {
            const user = users.find((u) => u.id === c.user_id);
            const isEditing = editId === c.id;
            return (
              <div key={c.id} style={{ border: "1px solid #eee", borderRadius: 6, padding: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: 13 }}>{user?.username ?? `User #${c.user_id}`}</strong>
                  <div style={{ display: "flex", gap: 4 }}>
                    {isEditing ? (
                      <>
                        <button onClick={() => handleUpdate(c.id)} disabled={acting} style={{ ...smBtn, color: "#5cb85c" }}>💾</button>
                        <button onClick={() => setEditId(null)} style={smBtn}>✕</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => { setEditId(c.id); setEditPerms([...c.permissions]); }} style={smBtn}>✏️</button>
                        <button onClick={() => handleDelete(c)} disabled={acting} style={{ ...smBtn, color: "#c00" }}>🗑</button>
                      </>
                    )}
                  </div>
                </div>
                <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 3 }}>
                  {isEditing ? (
                    ALL_PERMISSIONS.map((p) => (
                      <label key={p} style={{ fontSize: 10, display: "flex", alignItems: "center", gap: 2, padding: "1px 4px", border: "1px solid #ddd", borderRadius: 2, backgroundColor: editPerms.includes(p) ? "#e8f0fe" : "#fff", cursor: "pointer" }}>
                        <input type="checkbox" checked={editPerms.includes(p)} onChange={() => setEditPerms(togglePerm(editPerms, p))} style={{ width: 10, height: 10 }} />
                        {p}
                      </label>
                    ))
                  ) : (
                    c.permissions.map((p) => (
                      <span key={p} style={{ fontSize: 10, padding: "1px 6px", backgroundColor: "#e8f0fe", borderRadius: 3, color: "#336" }}>{p}</span>
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

const btnS: React.CSSProperties = { padding: "6px 12px", border: "1px solid #ddd", borderRadius: 4, cursor: "pointer", fontSize: 12, backgroundColor: "#fff" };
const smBtn: React.CSSProperties = { padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, backgroundColor: "#fff", cursor: "pointer", fontSize: 12 };
const errStyle: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#fee", border: "1px solid #c00", borderRadius: 4, color: "#c00", fontSize: 12 };
const msgStyle: React.CSSProperties = { padding: 8, marginBottom: 8, backgroundColor: "#efe", border: "1px solid #0a0", borderRadius: 4, color: "#060", fontSize: 12 };
