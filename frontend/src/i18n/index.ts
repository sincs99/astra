/**
 * Leichtgewichtiges i18n: Deutsch ist Standard, Englisch umschaltbar (Konto, Login-Seite).
 * Texte stehen in de.ts (Referenz, bestimmt die Schlüssel) und en.ts (muss alle Schlüssel haben, vom Compiler geprüft).
 * t() ist überall nutzbar; die Sprache wechselt über LangRoot, das den Baum bei Wechsel neu aufbaut.
 */
import { useSyncExternalStore } from "react";
import { de, type MessageKey } from "./de";
import { OPERATOR } from "../legal/operator";
import { en } from "./en";

export type Lang = "de" | "en";
export const LANG_STORAGE_KEY = "astra_lang";
export const LANG_OPTIONS: { value: Lang; label: string }[] = [
  { value: "de", label: "Deutsch" },
  { value: "en", label: "English" },
];

const MESSAGES: Record<Lang, Record<MessageKey, string>> = { de, en };

export function isLang(v: unknown): v is Lang {
  return v === "de" || v === "en";
}

function readStored(): Lang {
  try {
    const v = localStorage.getItem(LANG_STORAGE_KEY);
    return isLang(v) ? v : "de";
  } catch {
    return "de";
  }
}

let current: Lang = readStored();
const listeners = new Set<() => void>();

export function getLang(): Lang {
  return current;
}

export function setLang(lang: Lang): void {
  if (lang === current) return;
  current = lang;
  try {
    if (lang === "de") localStorage.removeItem(LANG_STORAGE_KEY);
    else localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    // Speichern nicht möglich: Wahl gilt nur bis zum Neuladen
  }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
  listeners.forEach((l) => l());
}

/** Liest die gespeicherte Sprache neu ein (nach Test-Setup oder externer Änderung). */
export function initLang(): void {
  current = readStored();
  if (typeof document !== "undefined") document.documentElement.lang = current;
}

export function hasKey(key: string): key is MessageKey {
  return key in de;
}

/** Übersetzt einen Schlüssel; {name}-Platzhalter werden aus params ersetzt. */
export function t(key: MessageKey, params?: Record<string, string | number>): string {
  const text = MESSAGES[current][key] ?? de[key];
  // {brand} steht in jedem Text zur Verfügung (Markenname des Betreibers)
  const all: Record<string, string | number> = { brand: OPERATOR.brand, ...params };
  return text.replace(/\{(\w+)\}/g, (m, name: string) => (name in all ? String(all[name]) : m));
}

/** BCP-47-Tag für Datums- und Zahlenformate der aktuellen Sprache. */
export function dateLocale(): string {
  return current === "en" ? "en-GB" : "de-CH";
}
/** Format für Geldbeträge; Schweizer Franken folgen der Schweizer Schreibweise ("CHF 1’234.56"), alle anderen der Sprache. */
export function moneyLocale(currency?: string): string {
  if (currency === "CHF") return current === "en" ? "en-CH" : "de-CH";
  return current === "en" ? "en-GB" : "de-DE";
}

export function useLang(): Lang {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    getLang,
    getLang,
  );
}

export type { MessageKey };
