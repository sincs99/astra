import { t } from "../i18n";

/** Darstellung: "system" folgt dem Betriebssystem, "light"/"dark" überschreiben es (im Browser gemerkt). */
export type ThemePreference = "system" | "light" | "dark";

export const THEME_STORAGE_KEY = "astra_theme";
export const themeOptions = (): { value: ThemePreference; label: string }[] => [
  { value: "system", label: t("account.themeSystem") },
  { value: "light", label: t("account.themeLight") },
  { value: "dark", label: t("account.themeDark") },
];

export function isThemePreference(v: unknown): v is ThemePreference {
  return v === "system" || v === "light" || v === "dark";
}

export function getThemePreference(): ThemePreference {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(v) ? v : "system";
  } catch {
    return "system";
  }
}

/** Setzt data-theme am <html>-Element; "system" entfernt es, dann entscheidet prefers-color-scheme. */
export function applyTheme(pref: ThemePreference): void {
  const root = document.documentElement;
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
}

export function setThemePreference(pref: ThemePreference): void {
  try {
    if (pref === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, pref);
  } catch {
    // Speichern nicht möglich (z.B. privater Modus): Wahl gilt nur bis zum Neuladen
  }
  applyTheme(pref);
}
