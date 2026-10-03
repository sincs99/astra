/** Preise werden im Backend in Cent gespeichert; im UI als Euro mit 2 Dezimalstellen bearbeitet. */

/**
 * Wandelt "9.99", "9,99" oder "10" in Cent um (ohne Gleitkomma-Rundung).
 * Liefert null bei leerer/ungueltiger Eingabe, negativen Werten oder mehr als 2 Dezimalstellen.
 */
export function parseEuroToCents(input: string): number | null {
  const m = /^(\d{1,7})(?:[.,](\d{1,2}))?$/.exec(input.trim());
  if (!m) return null;
  const euros = Number(m[1]);
  const cents = m[2] === undefined ? 0 : Number(m[2].padEnd(2, "0"));
  return euros * 100 + cents;
}

/** Cent -> Eingabewert für Formulare, z.B. 999 -> "9.99". */
export function centsToEuroInput(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.round(cents));
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** "9,99 €" (Waehrung nach ISO-Code, Standard EUR). */
export function formatMoney(cents: number, currency = "EUR"): string {
  try {
    return new Intl.NumberFormat("de-DE", { style: "currency", currency }).format(cents / 100);
  } catch {
    return `${centsToEuroInput(cents).replace(".", ",")} ${currency}`;
  }
}

/** "30 Tage" / "1 Tag" */
export function formatPeriod(days: number): string {
  return days === 1 ? "1 Tag" : `${days} Tage`;
}

/** "9,99 € / 30 Tage" */
export function formatPrice(cents: number, currency: string, days: number): string {
  return `${formatMoney(cents, currency)} / ${formatPeriod(days)}`;
}
