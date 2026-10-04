import { useEffect, useRef, useState } from "react";
import { api, type FileEntry } from "../services/api";
import { Toast, useToast } from "./ui";
import { Icon } from "./ui/Icon";
import { t } from "../i18n";

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
      setError(err instanceof Error ? err.message : t("sfiles.errLoad"));
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
      setError(err instanceof Error ? err.message : t("sfiles.errRead"));
    }
  };

  const saveFile = async () => {
    if (!selectedFile || editContent === null) return;
    try {
      setError(null);
      await api.writeFile(instanceUuid, selectedFile, editContent);
      toast.success(t("sfiles.saved"));
      setFileContent(editContent);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errSave"));
    }
  };

  const handleDelete = async (path: string) => {
    if (!confirm(t("sfiles.deleteConfirm", { path }))) return;
    try {
      setError(null);
      await api.deleteFile(instanceUuid, path);
      toast.success(t("sfiles.deleted", { path }));
      if (selectedFile === path) { setSelectedFile(null); setFileContent(null); setEditContent(null); }
      setSelected(prev => { const n = new Set(prev); n.delete(path); return n; });
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errDelete"));
    }
  };

  const joinPath = (name: string) => (directory === "/" ? `/${name}` : `${directory}/${name}`);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    let ok = 0;
    for (const file of Array.from(files)) {
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error(t("sfiles.uploadTooBig", { name: file.name }));
        continue;
      }
      try {
        const text = await file.text();
        // Binärdateien würden beim Text-Write beschädigt -> ablehnen
        if (text.includes("\uFFFD") || text.includes("\0")) {
          toast.error(t("sfiles.uploadNotText", { name: file.name }));
          continue;
        }
        await api.writeFile(instanceUuid, joinPath(file.name), text);
        ok++;
      } catch (err) {
        toast.error(err instanceof Error ? err.message : t("sfiles.uploadFailed", { name: file.name }));
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
    setUploading(false);
    if (ok > 0) {
      toast.success(t("sfiles.uploaded", { n: ok }));
      await loadFiles(directory);
    }
  };

  const handleCreateFile = async () => {
    const name = newFileName.trim();
    if (!name) return;
    try {
      await api.writeFile(instanceUuid, joinPath(name), "");
      toast.success(t("sfiles.fileCreated", { name }));
      setNewFileName("");
      await loadFiles(directory);
      await openFile(joinPath(name));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errAction"));
    }
  };

  const handleCreateDir = async () => {
    if (!newDirName.trim()) return;
    const path = directory === "/" ? `/${newDirName.trim()}` : `${directory}/${newDirName.trim()}`;
    try {
      setError(null);
      await api.createDirectory(instanceUuid, path);
      toast.success(t("sfiles.dirCreated", { path }));
      setNewDirName("");
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errAction"));
    }
  };

  const handleRename = async () => {
    if (!renameSrc.trim() || !renameTgt.trim()) return;
    try {
      setError(null);
      await api.renameFile(instanceUuid, renameSrc.trim(), renameTgt.trim());
      toast.success(t("sfiles.renamed"));
      setRenameSrc(""); setRenameTgt("");
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errAction"));
    }
  };

  const handleCompress = async () => {
    if (selected.size === 0) { setError(t("sfiles.noneSelected")); return; }
    const name = archiveName.trim() || "archive.tar.gz";
    const destination = directory === "/" ? `/${name}` : `${directory}/${name}`;
    try {
      setError(null);
      await api.compressFiles(instanceUuid, Array.from(selected), destination);
      toast.success(t("sfiles.compressed", { n: selected.size, name }));
      setArchiveName("");
      setSelected(new Set());
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errCompress"));
    }
  };

  const handleDecompress = async (filePath: string) => {
    const dest = decompressTarget.trim() || directory;
    try {
      setError(null);
      await api.decompressFile(instanceUuid, filePath, dest);
      toast.success(t("sfiles.decompressed", { dest }));
      await loadFiles(directory);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("sfiles.errDecompress"));
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

  const closeEditor = () => { setSelectedFile(null); setFileContent(null); setEditContent(null); };
  const dirty = editContent !== fileContent;

  return (
    <div className="stack">
      <Toast {...toast} />

      <nav aria-label={t("sfiles.nav")} className="row-actions">
        <button type="button" className="btn btn-sm" onClick={() => loadFiles("/")}>{t("sfiles.root")}</button>
        {directory !== "/" && (
          <button type="button" className="btn btn-sm btn-icon" onClick={navigateUp} aria-label={t("sfiles.up")} title={t("sfiles.up")}>
            <Icon name="back" />
          </button>
        )}
        <span className="mono">{directory}</span>
        <button type="button" className="btn btn-sm btn-icon" onClick={() => loadFiles(directory)} aria-label={t("sfiles.refresh")} title={t("sfiles.refresh")}>
          <Icon name="restart" />
        </button>
        {selected.size > 0 && <span className="hint" role="status">{t("sfiles.selectedCount", { n: selected.size })}</span>}
      </nav>

      {error && <div className="banner banner-danger" role="alert"><span className="banner-text text-danger">{error}</span></div>}

      <div className="cards-grid" style={selectedFile ? undefined : { gridTemplateColumns: "1fr" }}>
        <div className="stack">
          <div className="panel">
            {loading ? (
              <p className="hint panel-body" role="status">{t("sfiles.loading")}</p>
            ) : entries.length === 0 ? (
              <p className="hint panel-body">{t("sfiles.empty")}</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table className="tbl">
                  <caption className="sr-only">{t("sfiles.listCaption", { dir: directory })}</caption>
                  <thead>
                    <tr>
                      <th scope="col" style={{ width: 32 }}><span className="sr-only">{t("sfiles.colSelect")}</span></th>
                      <th scope="col">{t("sfiles.colName")}</th>
                      <th scope="col">{t("sfiles.colSize")}</th>
                      <th scope="col"><span className="sr-only">{t("sfiles.colActions")}</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map(entry => (
                      <tr
                        key={entry.path}
                        style={selected.has(entry.path) || selectedFile === entry.path ? { background: "var(--accent-soft)" } : undefined}
                      >
                        <td>
                          <input
                            type="checkbox"
                            aria-label={t("sfiles.selectEntry", { name: entry.name })}
                            checked={selected.has(entry.path)}
                            onChange={() => toggleSelect(entry.path)}
                          />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm mono"
                            aria-label={t(entry.is_directory ? "sfiles.openDir" : "sfiles.openFile", { name: entry.name })}
                            onClick={() => entry.is_directory ? loadFiles(entry.path) : openFile(entry.path)}
                          >
                            {entry.name}{entry.is_directory ? "/" : ""}
                          </button>
                        </td>
                        <td className="mono">{entry.is_file ? formatSize(entry.size) : "–"}</td>
                        <td>
                          <div className="row-actions" style={{ marginTop: 0 }}>
                            {entry.is_file && isArchive(entry.name) && (
                              <button type="button" className="btn btn-sm" aria-label={t("sfiles.decompressEntry", { name: entry.name })} onClick={() => handleDecompress(entry.path)}>
                                {t("sfiles.decompress")}
                              </button>
                            )}
                            <button type="button" className="btn btn-sm btn-danger-text" aria-label={t("sfiles.deleteEntry", { name: entry.name })} onClick={() => handleDelete(entry.path)}>
                              {t("sfiles.delete")}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <div className="row-actions">
              <input ref={fileInputRef} type="file" multiple hidden aria-label={t("sfiles.uploadInput")} onChange={e => handleUpload(e.target.files)} />
              <button type="button" className="btn btn-sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                <Icon name="download" size={14} />
                {uploading ? t("sfiles.uploading") : t("sfiles.upload")}
              </button>
              <span className="hint">{t("sfiles.uploadHint")}</span>
            </div>

            <div className="row-actions">
              <input className="inp" style={{ width: 180 }} type="text" value={newFileName} onChange={e => setNewFileName(e.target.value)} aria-label={t("sfiles.newFile")} placeholder={t("sfiles.newFile")} />
              <button type="button" className="btn btn-sm" onClick={handleCreateFile}><Icon name="plus" size={14} />{t("sfiles.createFile")}</button>
            </div>
            <div className="row-actions">
              <input className="inp" style={{ width: 180 }} type="text" value={newDirName} onChange={e => setNewDirName(e.target.value)} aria-label={t("sfiles.newDir")} placeholder={t("sfiles.newDir")} />
              <button type="button" className="btn btn-sm" onClick={handleCreateDir}><Icon name="plus" size={14} />{t("sfiles.createDir")}</button>
            </div>

            <div className="row-actions">
              <input className="inp" style={{ width: 180 }} type="text" value={renameSrc} onChange={e => setRenameSrc(e.target.value)} aria-label={t("sfiles.renameSrc")} placeholder={t("sfiles.renameSrc")} />
              <span aria-hidden="true">→</span>
              <input className="inp" style={{ width: 180 }} type="text" value={renameTgt} onChange={e => setRenameTgt(e.target.value)} aria-label={t("sfiles.renameTgt")} placeholder={t("sfiles.renameTgt")} />
              <button type="button" className="btn btn-sm" onClick={handleRename}>{t("sfiles.rename")}</button>
            </div>
          </div>

          <div className="card">
            <h3 className="card-title">{t("sfiles.compressTitle")}</h3>
            <div className="row-actions">
              <input className="inp" style={{ width: 180 }} type="text" value={archiveName} onChange={e => setArchiveName(e.target.value)} aria-label={t("sfiles.archiveName")} placeholder={t("sfiles.archivePlaceholder")} />
              <button type="button" className={`btn btn-sm${selected.size > 0 ? " btn-primary" : ""}`} onClick={handleCompress} disabled={selected.size === 0}>
                {t("sfiles.compress", { n: selected.size })}
              </button>
            </div>
            <div className="row-actions">
              <input className="inp" style={{ width: 240 }} type="text" value={decompressTarget} onChange={e => setDecompressTarget(e.target.value)} aria-label={t("sfiles.decompressTarget")} placeholder={t("sfiles.decompressPlaceholder", { dir: directory })} />
              <span className="hint">{t("sfiles.decompressHint")}</span>
            </div>
          </div>
        </div>

        {selectedFile && (
          <div className="card">
            <div className="row-actions">
              <span className="mono card-sub">{selectedFile}</span>
              <span className="push row-actions" style={{ marginTop: 0 }}>
                <button type="button" className={`btn btn-sm${dirty ? " btn-primary" : ""}`} onClick={saveFile} disabled={!dirty}>
                  {t("sfiles.save")}
                </button>
                <button type="button" className="btn btn-sm btn-icon" onClick={closeEditor} aria-label={t("sfiles.closeEditor")} title={t("sfiles.closeEditor")}>
                  <Icon name="close" />
                </button>
              </span>
            </div>
            <textarea
              className="inp mono"
              style={{ minHeight: 300, padding: 8, resize: "vertical" }}
              aria-label={t("sfiles.editorLabel", { path: selectedFile })}
              value={editContent ?? ""}
              onChange={e => setEditContent(e.target.value)}
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
