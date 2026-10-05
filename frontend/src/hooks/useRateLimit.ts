import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../services/api";
import { t } from "../i18n";

/** HTTP 429 (rate_limited): Hinweis mit Wartezeit in Minuten (aufgerundet); blockiert solange den Absende-Button. */
export function useRateLimit() {
  const [until, setUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (until <= Date.now()) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 5000);
    const end = setTimeout(() => setNow(Date.now()), Math.max(0, until - Date.now()) + 50);
    return () => { clearInterval(id); clearTimeout(end); };
  }, [until]);

  /** Liefert true, wenn der Fehler ein 429 war (und die Sperre gesetzt wurde). */
  const apply = useCallback((err: unknown): boolean => {
    if (!(err instanceof ApiError) || err.status !== 429) return false;
    const seconds = Number(err.data?.retry_after_seconds);
    const wait = Number.isFinite(seconds) && seconds > 0 ? seconds : 60;
    const start = Date.now();
    setNow(start);
    setUntil(start + wait * 1000);
    return true;
  }, []);

  const blocked = until > now;
  const minutes = Math.max(1, Math.ceil((until - now) / 60000));
  return { blocked, message: blocked ? (minutes === 1 ? t("auth.rate.waitOne") : t("auth.rate.wait", { n: minutes })) : null, apply };
}
