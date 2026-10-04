import { useEffect, useRef, useState } from "react";
import { api, type FileEntry } from "../services/api";
import { Toast, useToast, btnDefault, btnPrimary } from "./ui";

interface FileBrowserProps {
  instanceUuid: string;
}

const ARCHIVE_EXTENSIONS = [".tar.gz", ".tgz", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z"];

// Der Backend-Write-Endpoint nimmt nur Text entgegen (kein Multipart-Upload).
const MAX_UPLOAD_BYTES = 1024 * 1024;

function isArchive(name: string): boolean {
  return ARCHIVE_EXTENSIONS.some(ext => name.toLowerCase().endsWith(ext));
}

export function FileBrowser({ instanceUuid }: FileBrowserProps) {
  const toast = useToast();
  const [directory, setDirectory] = useState("/");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [newFileName, setNewFileName] = useState("");
  const [newDirName, setNewDirName] = useState("");
  const [renameSrc, setRenameSrc] = useState("");
  const [renameTgt, setRenameTgt] = useState("");
  const [archiveName, setArchiveName] = useState("");
  const [decompressTarget, setDecompressTarget] = useState("");

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
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadFiles("/"); }, [instanceUuid]);

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
      await api.writeFile(instanceUuid, selectedFile, editContent);
      toast.success("Datei gespeichert.");
      setFileContent(editContent);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Speichern");
    }
  };

  const handleDelete = async (path: string) => {
    if (!confirm(`'${path}' wirklich löschen?`)) return;
    try {
      setError(null);
      await api.deleteFile(instanceUuid, path);
      toast.success(`'${path}' gelöscht.`);
      if (selectedFile === path) { setSelectedFile(null); setFileContent(null); setEditContent(null); }
      setSelected(prev => { const n = new Set(prev); n.delete(path); return n; });
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Löschen");
    }
  };

  const joinPath = (name: string) => (directory === "/" ? `/${name}` : `${directory}/${name}`);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    let ok = 0;
    for (const file of Array.from(files)) {
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error(`'${file.name}' ist zu gross (max. 1 MB).`);
        continue;
      }
      try {
        const text = await file.text();
        // Binärdateien würden beim Text-Write beschädigt -> ablehnen
        if (text.includes("\uFFFD") || text.includes("\0")) {
          toast.error(`'${file.name}' ist keine Textdatei und kann nicht hochgeladen werden.`);
          continue;
        }
        await api.writeFile(instanceUuid, joinPath(file.name), text);
        ok++;
      } catch (err) {
        toast.error(err instanceof Error ? err.message : `Upload von '${file.name}' fehlgeschlagen`);
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
    setUploading(false);
    if (ok > 0) {
      toast.success(`${ok} Datei(en) hochgeladen.`);
      await loadFiles(directory);
    }
  };

  const handleCreateFile = async () => {
    const name = newFileName.trim();
    if (!name) return;
    try {
      await api.writeFile(instanceUuid, joinPath(name), "");
      toast.success(`Datei '${name}' erstellt.`);
      setNewFileName("");
      await loadFiles(directory);
      await openFile(joinPath(name));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    }
  };

  const handleCreateDir = async () => {
    if (!newDirName.trim()) return;
    const path = directory === "/" ? `/${newDirName.trim()}` : `${directory}/${newDirName.trim()}`;
    try {
      setError(null);
      await api.createDirectory(instanceUuid, path);
      toast.success(`Ordner '${path}' erstellt.`);
      setNewDirName("");
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    }
  };

  const handleRename = async () => {
    if (!renameSrc.trim() || !renameTgt.trim()) return;
    try {
      setError(null);
      await api.renameFile(instanceUuid, renameSrc.trim(), renameTgt.trim());
      toast.success("Umbenannt.");
      setRenameSrc(""); setRenameTgt("");
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Aktion fehlgeschlagen");
    }
  };

  const handleCompress = async () => {
    if (selected.size === 0) { setError("Keine Dateien ausgewählt"); return; }
    const name = archiveName.trim() || "archive.tar.gz";
    const destination = directory === "/" ? `/${name}` : `${directory}/${name}`;
    try {
      setError(null);
      await api.compressFiles(instanceUuid, Array.from(selected), destination);
      toast.success(`${selected.size} Datei(en) komprimiert → '${name}'`);
      setArchiveName("");
      setSelected(new Set());
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Komprimieren");
    }
  };

  const handleDecompress = async (filePath: string) => {
    const dest = decompressTarget.trim() || directory;
    try {
      setError(null);
      await api.decompressFile(instanceUuid, filePath, dest);
      toast.success(`Entpackt nach '${dest}'`);
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fehler beim Entpacken");
    }
  };

  const toggleSelect = (path: string) => {
    setSelected(prev => {
      const n = new Set(prev);
      n.has(path) ? n.delete(path) : n.add(path);
      return n;
    });
  };

  const navigateUp = () => {
    if (directory === "/") return;
    loadFiles(directory.substring(0, directory.lastIndexOf("/")) || "/");
  };

  return (
    <div>
      <Toast {...toast} />

      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <button onClick={() => loadFiles("/")} style={smBtn} title="Root">🏠</button>
        {directory !== "/" && <button onClick={navigateUp} style={smBtn} title="Zurück">⬆</button>}
        <code style={{ fontSize: 13, color: "var(--fg-soft)" }}>{directory}</code>
        <button onClick={() => loadFiles(directory)} style={smBtn} title="Aktualisieren">🔄</button>
        {selected.size > 0 && (
          <span style={{ fontSize: 12, color: "var(--c-blue)", fontWeight: 600 }}>{selected.size} ausgewählt</span>
        )}
      </div>

      {error && (
        <div style={{ padding: 8, marginBottom: 8, backgroundColor: "var(--tint-red)", border: "1px solid var(--border-red)", borderRadius: 4, color: "var(--c-red)", fontSize: 12 }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: selectedFile ? "repeat(auto-fit, minmax(280px, 1fr))" : "1fr", gap: 16 }}>
        {/* Dateiliste */}
        <div>
          {loading ? (
            <p style={{ color: "var(--fg-muted)", fontSize: 13 }}>Wird geladen...</p>
          ) : entries.length === 0 ? (
            <p style={{ color: "var(--fg-muted)", fontSize: 13 }}>Verzeichnis leer</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border)" }}>
                  <th style={{ ...thS, width: 24 }}></th>
                  <th style={thS}>Name</th>
                  <th style={thS}>Grösse</th>
                  <th style={{ ...thS, width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {entries.map(entry => (
                  <tr
                    key={entry.path}
                    style={{
                      borderBottom: "1px solid var(--bg-subtle)",
                      backgroundColor: selected.has(entry.path) ? "var(--tint-blue)" : selectedFile === entry.path ? "var(--tint-blue)" : undefined,
                    }}
                  >
                    <td style={{ padding: "4px 4px 4px 8px" }}>
                      <input
                        type="checkbox"
                        aria-label={`${entry.name} auswählen`}
                        checked={selected.has(entry.path)}
                        onChange={() => toggleSelect(entry.path)}
                        onClick={e => e.stopPropagation()}
                      />
                    </td>
                    <td style={{ padding: 6, cursor: "pointer" }} onClick={() => entry.is_directory ? loadFiles(entry.path) : openFile(entry.path)}>
                      {entry.is_directory ? "📁 " : "📄 "}
                      {entry.name}
                    </td>
                    <td style={{ padding: 6, color: "var(--fg-muted)", fontSize: 12 }}>
                      {entry.is_file ? formatSize(entry.size) : "–"}
                    </td>
                    <td style={{ padding: 6 }}>
                      <div style={{ display: "flex", gap: 4 }}>
                        {entry.is_file && isArchive(entry.name) && (
                          <button onClick={e => { e.stopPropagation(); handleDecompress(entry.path); }} style={smBtn} title="Entpacken">📦</button>
                        )}
                        <button onClick={e => { e.stopPropagation(); handleDelete(entry.path); }} style={{ ...smBtn, color: "var(--c-red)" }} title="Löschen">🗑</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* ── Aktionen ── */}
          <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              aria-label="Dateien hochladen"
              onChange={e => handleUpload(e.target.files)}
            />
            <button onClick={() => fileInputRef.current?.click()} disabled={uploading} style={smBtn}>
              {uploading ? "Wird hochgeladen..." : "⬆ Hochladen"}
            </button>
            <small style={{ color: "var(--fg-muted)", fontSize: 11 }}>nur Textdateien, max. 1 MB</small>
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input type="text" value={newFileName} onChange={e => setNewFileName(e.target.value)} placeholder="Neue Datei" style={actionInput} />
            <button onClick={handleCreateFile} style={smBtn}>📄+</button>
            <input type="text" value={newDirName} onChange={e => setNewDirName(e.target.value)} placeholder="Neuer Ordner" style={actionInput} />
            <button onClick={handleCreateDir} style={smBtn}>📁+</button>
          </div>

          <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input type="text" value={renameSrc} onChange={e => setRenameSrc(e.target.value)} placeholder="Quelle" style={actionInput} />
            <span style={{ fontSize: 12 }}>→</span>
            <input type="text" value={renameTgt} onChange={e => setRenameTgt(e.target.value)} placeholder="Ziel" style={actionInput} />
            <button onClick={handleRename} style={smBtn}>✏️ Umbenennen</button>
          </div>

          {/* ── Compress-Bereich ── */}
          <div style={{ marginTop: 12, padding: 10, border: "1px solid var(--border)", borderRadius: 6, backgroundColor: "var(--tint-blue)" }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--c-blue)" }}>Komprimieren</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <input type="text" value={archiveName} onChange={e => setArchiveName(e.target.value)} placeholder="archiv.tar.gz" style={actionInput} />
              <button
                onClick={handleCompress}
                disabled={selected.size === 0}
                style={{ ...(selected.size > 0 ? btnPrimary : btnDefault), padding: "4px 12px", fontSize: 12 }}
              >
                📦 Komprimieren ({selected.size})
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
              <input type="text" value={decompressTarget} onChange={e => setDecompressTarget(e.target.value)} placeholder={`Ziel: ${directory}`} style={{ ...actionInput, width: 200 }} />
              <small style={{ color: "var(--fg-muted)", fontSize: 11 }}>Zielverzeichnis für 📦-Entpacken</small>
            </div>
          </div>
        </div>

        {/* Dateiinhalt / Editor */}
        {selectedFile && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <code style={{ fontSize: 12, color: "var(--fg-soft)" }}>{selectedFile}</code>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  onClick={saveFile}
                  disabled={editContent === fileContent}
                  style={{
                    ...smBtn,
                    backgroundColor: editContent !== fileContent ? "#2e7d32" : "var(--bg-subtle)",
                    color: editContent !== fileContent ? "#fff" : "var(--fg-muted)",
                    cursor: editContent !== fileContent ? "pointer" : "default",
                  }}
                >
                  💾 Speichern
                </button>
                <button onClick={() => { setSelectedFile(null); setFileContent(null); setEditContent(null); }} style={smBtn}>✕</button>
              </div>
            </div>
            <textarea
              value={editContent ?? ""}
              onChange={e => setEditContent(e.target.value)}
              style={{
                width: "100%", minHeight: 300, fontFamily: "monospace", fontSize: 12,
                padding: 8, border: "1px solid var(--border)", borderRadius: 6,
                boxSizing: "border-box", backgroundColor: "var(--bg-page)", resize: "vertical",
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const smBtn: React.CSSProperties = {
  padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4,
  backgroundColor: "var(--bg-card)", cursor: "pointer", fontSize: 12,
};

const actionInput: React.CSSProperties = {
  padding: "4px 8px", fontSize: 12, borderRadius: 4,
  border: "1px solid var(--border-strong)", width: 130,
};

const thS: React.CSSProperties = {
  padding: 6, textAlign: "left", fontSize: 12, fontWeight: 600, color: "var(--fg-soft)",
};
