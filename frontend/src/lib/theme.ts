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

/** Löst "system" über prefers-color-scheme auf; ohne matchMedia gilt Dunkel (Standard des Designs). */
export function resolveTheme(pref: ThemePreference): "light" | "dark" {
  if (pref !== "system") return pref;
  try {
    return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Setzt data-theme immer explizit ("light" oder "dark"), da tokens.css keinen prefers-color-scheme-Block hat. */
export function applyTheme(pref: ThemePreference): void {
  document.documentElement.setAttribute("data-theme", resolveTheme(pref));
}

/** Folgt Änderungen der System-Einstellung, solange die Wahl "Wie das Gerät" ist. Gibt eine Abmeldefunktion zurück. */
export function watchSystemTheme(): () => void {
  let mq: MediaQueryList | undefined;
  try { mq = window.matchMedia?.("(prefers-color-scheme: light)"); } catch { mq = undefined; }
  if (!mq) return () => {};
  const onChange = () => { if (getThemePreference() === "system") applyTheme("system"); };
  mq.addEventListener?.("change", onChange);
  return () => mq!.removeEventListener?.("change", onChange);
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
