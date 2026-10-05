/**
 * Angaben des Betreibers fuer Impressum, Datenschutzerklaerung und AGB.
 *
 * Diese Datei ist der EINE Ort, an dem der Betreiber seine Daten einträgt. Solange ein Feld den
 * Platzhalter enthaelt, wird es auf den Rechtsseiten hervorgehoben dargestellt.
 * Die Rechtstexte selbst (siehe pages/LegalPages.tsx) sind nur eine Struktur und ersetzen keine
 * Rechtsberatung – sie muessen vom Betreiber geprueft und angepasst werden.
 */
export const PLACEHOLDER = "[vom Betreiber auszufüllen]";

/** Rechtsraum des Betreibers: bestimmt die Fassung der Rechtstexte (Impressum, Datenschutz, AGB) und den Kaufhinweis im Shop. */
export type Jurisdiction = "DE" | "CH";

export interface Operator {
  jurisdiction: Jurisdiction;
  name: string;
  legalForm: string;
  street: string;
  zipCity: string;
  country: string;
  email: string;
  phone: string;
  representative: string;
  register: string;
  vatId: string;
  supervisoryAuthority: string;
  hosting: string;
  paymentProvider: string;
  lastUpdated: string;
}

export const OPERATOR: Operator = {
  /** "DE" (Standard) oder "CH" (Schweiz: Anbieterkennzeichnung nach UWG, Datenschutz nach DSG, kein Widerrufsrecht) */
  jurisdiction: "DE",
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
  /** Umsatzsteuer-Identifikationsnummer bzw. in der Schweiz UID/MWST-Nummer, falls vorhanden */
  vatId: PLACEHOLDER,
  /** Zustaendige Datenschutz-Aufsichtsbehoerde (nur DE; in der Schweiz ist es der EDÖB) */
  supervisoryAuthority: PLACEHOLDER,
  /** Hosting-Anbieter / Rechenzentrum */
  hosting: PLACEHOLDER,
  /** Zahlungsanbieter, sobald angebunden (z.B. Stripe) */
  paymentProvider: PLACEHOLDER,
  /** Stand der Texte */
  lastUpdated: PLACEHOLDER,
};

export function isPlaceholder(value: string): boolean {
  return value === PLACEHOLDER;
}
