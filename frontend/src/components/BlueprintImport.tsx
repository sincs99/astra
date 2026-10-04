import { useRef, useState } from "react";
import { api, type Blueprint } from "../services/api";
import { parseEgg } from "../lib/eggParser";
import { t } from "../i18n";
import { Field, ErrorBanner } from "./admin/AdminField";

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
      setError(err instanceof Error ? err.message : t("ainst.imp.invalid"));
    }
  };

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_EGG_BYTES) {
      setParsed(null);
      setError(t("ainst.imp.tooBig"));
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
      const message = err instanceof Error ? err.message : t("ainst.imp.failed");
      setError(message);
      onError(message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="egg-import-title">
      <div className="panel-head"><h2 id="egg-import-title">{t("ainst.imp.title")}</h2></div>
      <div className="panel-body">
        <p className="hint">{t("ainst.imp.intro")}</p>

        <Field label={t("ainst.imp.file")}>
          <input ref={fileRef} type="file" accept="application/json,.json" onChange={(e) => handleFile(e.target.files?.[0])} />
        </Field>

        <Field label={t("ainst.imp.text")}>
          <textarea
            className="inp mono"
            value={text}
            onChange={(e) => check(e.target.value)}
            rows={8}
            spellCheck={false}
            aria-invalid={error ? true : undefined}
            style={{ padding: "8px 12px", resize: "vertical" }}
            placeholder='{ "name": "Minecraft", "docker_images": { ... }, "variables": [ ... ] }'
          />
        </Field>

        {error && <ErrorBanner message={error} />}

        {parsed && (
          <div role="status" className="banner banner-info">
            <span className="dot dot-ok" aria-hidden="true" />
            <div className="banner-text">
              <strong>{parsed.preview.name}</strong>
              {parsed.preview.author && <> {t("ainst.imp.by", { author: parsed.preview.author })}</>}
              <div className="hint" style={{ color: "var(--text-2)" }}>
                {parsed.preview.image ? <>{t("ainst.imp.image")}: <span className="mono">{parsed.preview.image}</span> · </> : null}
                {t("ainst.imp.variableCount", { n: parsed.preview.variableCount })}
              </div>
            </div>
          </div>
        )}

        <div className="row-actions">
          <button type="button" className="btn btn-primary" onClick={handleImport} disabled={!parsed || importing}>
            {importing ? t("ainst.imp.importing") : t("ainst.imp.import")}
          </button>
          <button type="button" className="btn" onClick={reset} disabled={importing}>{t("ainst.imp.reset")}</button>
        </div>
      </div>
    </section>
  );
}
