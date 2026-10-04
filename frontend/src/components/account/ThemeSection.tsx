import { useState } from "react";
import { LANG_OPTIONS, isLang, setLang, t, useLang } from "../../i18n";
import { cardStyle, labelStyle, inputStyle } from "../ui";
import { themeOptions, getThemePreference, isThemePreference, setThemePreference, type ThemePreference } from "../../lib/theme";

/** Konto: Darstellung (hell, dunkel oder wie das Gerät); wird im Browser gemerkt. */
export function ThemeSection() {
  const [pref, setPref] = useState<ThemePreference>(getThemePreference);
  const lang = useLang();

  return (
    <section style={cardStyle} aria-labelledby="theme-title">
      <h2 id="theme-title" style={{ marginTop: 0, fontSize: 18 }}>{t("account.appearance")}</h2>
      <label htmlFor="theme-select" style={labelStyle}>{t("account.colorScheme")}</label>
      <select id="theme-select" value={pref} style={{ ...inputStyle, maxWidth: 260 }}
        onChange={(e) => {
          const v = e.target.value;
          if (!isThemePreference(v)) return;
          setPref(v);
          setThemePreference(v);
        }}>
        {themeOptions().map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <label htmlFor="lang-select" style={{ ...labelStyle, marginTop: 16 }}>{t("account.language")}</label>
      <select id="lang-select" value={lang} style={{ ...inputStyle, maxWidth: 260 }}
        onChange={(e) => { if (isLang(e.target.value)) setLang(e.target.value); }}>
        {LANG_OPTIONS.map((o) => <option key={o.value} value={o.value} lang={o.value}>{o.label}</option>)}
      </select>
      <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--fg-muted)" }}>
        {t("account.browserOnly")} {t("account.languageHint")}
      </p>
    </section>
  );
}
