import { useEffect, useRef, useState } from "react";

/**
 * Ruft `callback` periodisch auf (Polling), solange aktiviert und der Tab sichtbar ist.
 * Beim Zurueckkehren in den Tab wird sofort einmal aktualisiert.
 */
export function useAutoRefresh(callback: () => void, intervalMs: number, enabled: boolean) {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (!enabled) return;
    const tick = () => {
      if (document.visibilityState === "visible") saved.current();
    };
    const timer = setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [intervalMs, enabled]);
}

/** Zustand fuer den Auto-Refresh-Schalter, pro Seite im localStorage gemerkt. */
export function useAutoRefreshSetting(key: string, defaultValue = true) {
  const storageKey = `astra.autorefresh.${key}`;
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(storageKey);
      return v === null ? defaultValue : v === "1";
    } catch {
      return defaultValue;
    }
  });

  const update = (value: boolean) => {
    setEnabled(value);
    try { localStorage.setItem(storageKey, value ? "1" : "0"); } catch { /* ignorieren */ }
  };

  return [enabled, update] as const;
}
