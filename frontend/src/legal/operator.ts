/**
 * Angaben des Betreibers fuer Impressum, Datenschutzerklaerung und AGB.
 *
 * Diese Datei ist der EINE Ort, an dem der Betreiber seine Daten einträgt. Solange ein Feld den
 * Platzhalter enthaelt, wird es auf den Rechtsseiten hervorgehoben dargestellt.
 * Die Rechtstexte selbst (siehe pages/LegalPages.tsx) sind nur eine Struktur und ersetzen keine
 * Rechtsberatung – sie muessen vom Betreiber geprueft und angepasst werden.
 */
export const PLACEHOLDER = "[vom Betreiber auszufüllen]";

export const OPERATOR = {
  /** Name der Firma bzw. des Betreibers */
  name: PLACEHOLDER,
  /** Rechtsform, z.B. Einzelunternehmen, GmbH */
  legalForm: PLACEHOLDER,
  street: PLACEHOLDER,
  zipCity: PLACEHOLDER,
  country: PLACEHOLDER,
  email: PLACEHOLDER,
  phone: PLACEHOLDER,
  /** Vertretungsberechtigte Person(en) */
  representative: PLACEHOLDER,
  /** Handelsregister und Registernummer, falls vorhanden */
  register: PLACEHOLDER,
  /** Umsatzsteuer-Identifikationsnummer, falls vorhanden */
  vatId: PLACEHOLDER,
  /** Zustaendige Datenschutz-Aufsichtsbehoerde */
  supervisoryAuthority: PLACEHOLDER,
  /** Hosting-Anbieter / Rechenzentrum */
  hosting: PLACEHOLDER,
  /** Zahlungsanbieter, sobald angebunden (z.B. Stripe) */
  paymentProvider: PLACEHOLDER,
  /** Stand der Texte */
  lastUpdated: PLACEHOLDER,
} as const;

export function isPlaceholder(value: string): boolean {
  return value === PLACEHOLDER;
}
