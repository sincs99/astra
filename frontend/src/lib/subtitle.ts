/** Unterzeile einer Karte: "{Spiel} · {Paket}", ohne Spielname nur das Paket. */
export function gamePackageLabel(blueprint?: string | null, product?: string | null): string {
  return [blueprint, product].filter(Boolean).join(" \u00b7 ");
}
