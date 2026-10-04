/** Einmalige Hinweise über einen Seitenwechsel hinweg (z.B. nach dem Login), gespeichert in sessionStorage. */
export interface Flash {
  kind: "info" | "warning";
  text: string;
  /** Optionaler Link (interner Pfad) mit Beschriftung */
  link?: { to: string; label: string };
}

const KEY = "astra_flash";

export function setFlash(flash: Flash): void {
  try { sessionStorage.setItem(KEY, JSON.stringify(flash)); } catch { /* ohne Speicher entfällt der Hinweis */ }
}

/** Liest den Hinweis und löscht ihn (wird nur einmal angezeigt). */
export function takeFlash(): Flash | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const v = JSON.parse(raw) as Flash;
    return v && typeof v.text === "string" && (v.kind === "info" || v.kind === "warning") ? v : null;
  } catch {
    return null;
  }
}
