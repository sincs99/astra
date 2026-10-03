/** Feste Zeitzone fuer alle Tests, damit Datumsformatierungen auf jedem Rechner gleich ausfallen. */
export function setup() {
  process.env.TZ = "UTC";
}
