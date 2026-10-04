import { LANG_OPTIONS, setLang, useLang, t } from "../i18n";

/** Sprachumschalter (Deutsch / English); aktuelle Sprache ist hervorgehoben. */
export function LanguageSwitch() {
  const lang = useLang();
  return (
    <div role="group" aria-label={t("lang.label")} style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
      {LANG_OPTIONS.map((o, i) => (
        <span key={o.value} style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
          {i > 0 && <span aria-hidden="true">|</span>}
          <button type="button" lang={o.value} onClick={() => setLang(o.value)}
            aria-pressed={lang === o.value}
            style={{
              background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit",
              color: lang === o.value ? "var(--text)" : "var(--accent)",
              fontWeight: lang === o.value ? 700 : 400,
              textDecoration: lang === o.value ? "none" : "underline",
            }}>
            {o.label}
          </button>
        </span>
      ))}
    </div>
  );
}
