import { dateLocale, t } from "../i18n";

const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * Parst einen Zeitstempel des Backends. ISO-Strings ohne Zeitzone bedeuten UTC; ohne "Z" wuerde der
 * Browser sie als lokale Zeit lesen und um den Zeitzonenversatz verschieben.
 */
export function parseUtc(iso: string): Date {
  return new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
}

/** Datum für Tabellen, z.B. "31.10.2026"; "–" ohne Wert. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleDateString(dateLocale());
}

/** Datum und Uhrzeit, z.B. "31.10.2026 14:05"; "–" ohne Wert. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return `${d.toLocaleDateString(dateLocale())} ${d.toLocaleTimeString(dateLocale(), { hour: "2-digit", minute: "2-digit" })}`;
}

/** Relative Angabe wie "vor 5 Min."; `now` ist für Tests ueberschreibbar. Zukunft/Uhrenabweichung = "gerade eben". */
export function formatTimeAgo(iso: string, now: number = Date.now()): string {
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = Math.floor((now - d.getTime()) / 1000);
  if (diff < 60) return t("time.justNow");
  if (diff < 3600) return t("time.minutesAgo", { n: Math.floor(diff / 60) });
  if (diff < 86400) return t("time.hoursAgo", { n: Math.floor(diff / 3600) });
  const days = Math.floor(diff / 86400);
  return days === 1 ? t("time.dayAgo") : t("time.daysAgo", { n: days });
}

/** Kurzes Datum mit Uhrzeit inkl. Sekunden für Protokolle, z.B. "03.10., 14:05:09". */
export function formatLogTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return d.toLocaleString(dateLocale(), { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" });
}

/** Datum mit ausgeschriebenem Monat, z.B. "3. Okt. 2026"; "–" ohne Wert. */
export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return d.toLocaleDateString(dateLocale(), { year: "numeric", month: "short", day: "numeric" });
}
