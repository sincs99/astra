/** Datum fuer Tabellen, z.B. "31.10.2026"; "–" ohne Wert. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleDateString("de-CH");
}
