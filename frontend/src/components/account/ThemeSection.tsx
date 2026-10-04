import { useState } from "react";
import { cardStyle, labelStyle, inputStyle } from "../ui";
import { THEME_OPTIONS, getThemePreference, isThemePreference, setThemePreference, type ThemePreference } from "../../lib/theme";

/** Konto: Darstellung (hell, dunkel oder wie das Gerät); wird im Browser gemerkt. */
export function ThemeSection() {
  const [pref, setPref] = useState<ThemePreference>(getThemePreference);

  return (
    <section style={cardStyle} aria-labelledby="theme-title">
      <h2 id="theme-title" style={{ marginTop: 0, fontSize: 18 }}>Darstellung</h2>
      <label htmlFor="theme-select" style={labelStyle}>Farbschema</label>
      <select id="theme-select" value={pref} style={{ ...inputStyle, maxWidth: 260 }}
        onChange={(e) => {
          const v = e.target.value;
          if (!isThemePreference(v)) return;
          setPref(v);
          setThemePreference(v);
        }}>
        {THEME_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--fg-muted)" }}>
        Die Auswahl gilt nur für diesen Browser.
      </p>
    </section>
  );
}
