const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * Parst einen Zeitstempel des Backends. ISO-Strings ohne Zeitzone bedeuten UTC; ohne "Z" wuerde der
 * Browser sie als lokale Zeit lesen und um den Zeitzonenversatz verschieben.
 */
export function parseUtc(iso: string): Date {
  return new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
}

/** Datum fuer Tabellen, z.B. "31.10.2026"; "–" ohne Wert. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleDateString("de-CH");
}

/** Datum und Uhrzeit, z.B. "31.10.2026 14:05"; "–" ohne Wert. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return `${d.toLocaleDateString("de-CH")} ${d.toLocaleTimeString("de-CH", { hour: "2-digit", minute: "2-digit" })}`;
}
