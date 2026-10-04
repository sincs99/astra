import { useRef, useState } from "react";
import { api, type Blueprint } from "../services/api";
import { parseEgg } from "../lib/eggParser";
import { cardStyle, inputStyle, labelStyle, btnPrimary, btnDefault, ErrorState } from "./ui";

const MAX_EGG_BYTES = 1024 * 1024;

interface BlueprintImportProps {
  onImported: (blueprint: Blueprint) => void;
  onError: (message: string) => void;
}

export function BlueprintImport({ onImported, onError }: BlueprintImportProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<ReturnType<typeof parseEgg> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  const reset = () => {
    setText("");
    setParsed(null);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const check = (value: string) => {
    setText(value);
    if (!value.trim()) { setParsed(null); setError(null); return; }
    try {
      setParsed(parseEgg(value));
      setError(null);
    } catch (err) {
      setParsed(null);
      setError(err instanceof Error ? err.message : "Ungültige Eingabe");
    }
  };

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_EGG_BYTES) {
      setParsed(null);
      setError("Die Datei ist zu gross (max. 1 MB).");
      return;
    }
    check(await file.text());
  };

  const handleImport = async () => {
    if (!parsed) return;
    try {
      setImporting(true);
      const blueprint = await api.importBlueprint(parsed.egg);
      onImported(blueprint);
      reset();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Import fehlgeschlagen";
      setError(message);
      onError(message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div style={cardStyle}>
      <h2 style={{ marginTop: 0, fontSize: 18, fontWeight: 700 }}>Blueprint importieren</h2>
      <p style={{ marginTop: -8, color: "var(--fg-muted)", fontSize: 13 }}>
        Pterodactyl-Egg als JSON-Datei hochladen oder einfügen.
      </p>

      <div style={{ marginBottom: 12 }}>
        <label htmlFor="egg-file" style={labelStyle}>Egg-Datei (.json)</label>
        <input
          id="egg-file"
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label htmlFor="egg-text" style={labelStyle}>oder JSON einfügen</label>
        <textarea
          id="egg-text"
          value={text}
          onChange={(e) => check(e.target.value)}
          rows={8}
          spellCheck={false}
          style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
          placeholder='{ "name": "Minecraft", "docker_images": { ... }, "variables": [ ... ] }'
        />
      </div>

      {error && <ErrorState message={error} />}

      {parsed && (
        <div style={{ padding: 10, marginBottom: 12, backgroundColor: "var(--tint-green)", borderRadius: 6, fontSize: 13 }}>
          <strong>{parsed.preview.name}</strong>
          {parsed.preview.author && <> von {parsed.preview.author}</>}
          <div style={{ color: "var(--fg-soft)" }}>
            {parsed.preview.image ? <>Image: <code>{parsed.preview.image}</code> · </> : null}
            {parsed.preview.variableCount} Variable(n)
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={handleImport} disabled={!parsed || importing}
          style={{ ...btnPrimary, opacity: !parsed || importing ? 0.6 : 1, cursor: !parsed || importing ? "not-allowed" : "pointer" }}>
          {importing ? "Wird importiert..." : "Importieren"}
        </button>
        <button type="button" onClick={reset} disabled={importing} style={btnDefault}>Zurücksetzen</button>
      </div>
    </div>
  );
}
