import { useEffect, useState } from "react";
import { api, type FileEntry } from "../services/api";

interface FileBrowserProps {
  instanceUuid: string;
}

export function FileBrowser({ instanceUuid }: FileBrowserProps) {
  const [directory, setDirectory] = useState("/");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Neue Datei/Ordner Inputs
  const [newDirName, setNewDirName] = useState("");
  const [renameSrc, setRenameSrc] = useState("");
  const [renameTgt, setRenameTgt] = useState("");

  const loadFiles = async (dir: string) => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.listFiles(instanceUuid, dir);
      setEntries(result.entries);
      setDirectory(result.directory);
      setSelectedFile(null);
      setFileContent(null);
      setEditContent(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFiles("/");
  }, [instanceUuid]);

  const openFile = async (path: string) => {
    try {
      setError(null);
      const result = await api.readFile(instanceUuid, path);
      setSelectedFile(result.path);
      setFileContent(result.content);
      setEditContent(result.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Lesen");
    }
  };

  const saveFile = async () => {
    if (!selectedFile || editContent === null) return;
    try {
      setError(null);
      const result = await api.writeFile(instanceUuid, selectedFile, editContent);
      setMessage(result.message);
      setFileContent(editContent);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Speichern");
    }
  };

  const handleDelete = async (path: string) => {
    try {
      setError(null);
      const result = await api.deleteFile(instanceUuid, path);
      setMessage(result.message);
      if (selectedFile === path) {
        setSelectedFile(null);
        setFileContent(null);
        setEditContent(null);
      }
      await loadFiles(directory);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Löschen");
    }
  };

  const handleCreateDir = async () => {
    if (!newDirName.trim()) return;
    const path = directory === "/" ? `/${newDirName.trim()}` : `${directory}/${newDirName.trim()}`;
    try {
      setError(null);
      const result = await api.createDirectory(instanceUuid, path);
      setMessage(result.message);
      setNewDirName("");
      await loadFiles(directory);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    }
  };

  const handleRename = async () => {
    if (!renameSrc.trim() || !renameTgt.trim()) return;
    try {
      setError(null);
      const result = await api.renameFile(instanceUuid, renameSrc.trim(), renameTgt.trim());
      setMessage(result.message);
      setRenameSrc("");
      setRenameTgt("");
      await loadFiles(directory);
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    }
  };

  const navigateUp = () => {
    if (directory === "/") return;
    const parent = directory.substring(0, directory.lastIndexOf("/")) || "/";
    loadFiles(parent);
  };

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <button onClick={() => loadFiles("/")} style={smBtn} title="Root">🏠</button>
        {directory !== "/" && (
          <button onClick={navigateUp} style={smBtn} title="Zurück">⬆</button>
        )}
        <code style={{ fontSize: 13, color: "#555" }}>{directory}</code>
        <button onClick={() => loadFiles(directory)} style={smBtn} title="Aktualisieren">🔄</button>
      </div>

      {error && <div style={errStyle}>{error}</div>}
      {message && <div style={msgStyle}>{message}</div>}

      <div style={{ display: "grid", gridTemplateColumns: selectedFile ? "1fr 1fr" : "1fr", gap: 16 }}>
        {/* Dateiliste */}
        <div>
          {loading ? (
            <p style={{ color: "#888" }}>Wird geladen...</p>
          ) : entries.length === 0 ? (
            <p style={{ color: "#888" }}>Verzeichnis leer</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #ddd" }}>
                  <th style={thS}>Name</th>
                  <th style={thS}>Grösse</th>
                  <th style={{ ...thS, width: 50 }}></th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.path}
                    style={{
                      borderBottom: "1px solid #eee",
                      backgroundColor: selectedFile === entry.path ? "#e8f0fe" : undefined,
                      cursor: "pointer",
                    }}
                    onClick={() => {
                      if (entry.is_directory) loadFiles(entry.path);
                      else openFile(entry.path);
                    }}
                  >
                    <td style={{ padding: 6 }}>
                      {entry.is_directory ? "📁 " : "📄 "}
                      {entry.name}
                    </td>
                    <td style={{ padding: 6, color: "#888", fontSize: 12 }}>
                      {entry.is_file ? formatSize(entry.size) : "–"}
                    </td>
                    <td style={{ padding: 6 }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(entry.path); }}
                        style={{ ...smBtn, color: "#c00", fontSize: 11 }}
                        title="Löschen"
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Aktionen */}
          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              type="text"
              value={newDirName}
              onChange={(e) => setNewDirName(e.target.value)}
              placeholder="Neuer Ordner"
              style={{ padding: 4, fontSize: 12, width: 120 }}
            />
            <button onClick={handleCreateDir} style={smBtn}>📁+</button>
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              type="text"
              value={renameSrc}
              onChange={(e) => setRenameSrc(e.target.value)}
              placeholder="Quelle"
              style={{ padding: 4, fontSize: 12, width: 110 }}
            />
            <span style={{ fontSize: 12, lineHeight: "28px" }}>→</span>
            <input
              type="text"
              value={renameTgt}
              onChange={(e) => setRenameTgt(e.target.value)}
              placeholder="Ziel"
              style={{ padding: 4, fontSize: 12, width: 110 }}
            />
            <button onClick={handleRename} style={smBtn}>✏️</button>
          </div>
        </div>

        {/* Dateiinhalt / Editor */}
        {selectedFile && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <code style={{ fontSize: 12, color: "#555" }}>{selectedFile}</code>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  onClick={saveFile}
                  disabled={editContent === fileContent}
                  style={{
                    ...smBtn,
                    backgroundColor: editContent !== fileContent ? "#5cb85c" : "#ddd",
                    color: editContent !== fileContent ? "#fff" : "#888",
                  }}
                >
                  💾 Speichern
                </button>
                <button
                  onClick={() => { setSelectedFile(null); setFileContent(null); setEditContent(null); }}
                  style={smBtn}
                >
                  ✕
                </button>
              </div>
            </div>
            <textarea
              value={editContent ?? ""}
              onChange={(e) => setEditContent(e.target.value)}
              style={{
                width: "100%",
                minHeight: 300,
                fontFamily: "monospace",
                fontSize: 12,
                padding: 8,
                border: "1px solid #ddd",
                borderRadius: 4,
                boxSizing: "border-box",
                backgroundColor: "#fafafa",
                resize: "vertical",
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const smBtn: React.CSSProperties = {
  padding: "4px 8px",
  border: "1px solid #ddd",
  borderRadius: 3,
  backgroundColor: "#fff",
  cursor: "pointer",
  fontSize: 12,
};

const thS: React.CSSProperties = {
  padding: 6,
  textAlign: "left",
  fontSize: 12,
  fontWeight: 600,
};

const errStyle: React.CSSProperties = {
  padding: 8,
  marginBottom: 8,
  backgroundColor: "#fee",
  border: "1px solid #c00",
  borderRadius: 4,
  color: "#c00",
  fontSize: 12,
};

const msgStyle: React.CSSProperties = {
  padding: 8,
  marginBottom: 8,
  backgroundColor: "#efe",
  border: "1px solid #0a0",
  borderRadius: 4,
  color: "#060",
  fontSize: 12,
};
