/**
 * Angaben des Betreibers fuer Impressum, Datenschutzerklaerung und AGB.
 *
 * Diese Datei ist der EINE Ort, an dem der Betreiber seine Daten einträgt. Solange ein Feld den
 * Platzhalter enthaelt, wird es auf den Rechtsseiten hervorgehoben dargestellt.
 *
 * Pflichtangaben: brand, jurisdiction, name, street, zipCity, country, email, lastUpdated. Alle anderen Felder sind
 * optional: leer lassen (""), wenn es sie nicht gibt (z. B. Telefon, Handelsregister oder MWST-Nr. einer Schweizer
 * Einzelfirma); sie werden dann samt Beschriftung auf den Rechtsseiten ausgelassen.
 * Die Rechtstexte selbst (siehe pages/LegalPages.tsx) sind nur eine Struktur und ersetzen keine
 * Rechtsberatung – sie muessen vom Betreiber geprueft und angepasst werden.
 */
export const PLACEHOLDER = "[vom Betreiber auszufüllen]";

/** Rechtsraum des Betreibers: bestimmt die Fassung der Rechtstexte (Impressum, Datenschutz, AGB) und den Kaufhinweis im Shop. */
export type Jurisdiction = "DE" | "CH";

export interface Operator {
  /** Marke, unter der das Panel betrieben wird (Logo-Wortmarke, Tab-Titel, Texte) */
  brand: string;
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
  /** Markenname der Oberfläche; "Astra" ist der Name der Software, ein Betreiber kann hier seine eigene Marke eintragen */
  brand: "Astra",
  /** "DE" (Standard) oder "CH" (Schweiz: Anbieterkennzeichnung nach UWG, Datenschutz nach DSG, kein Widerrufsrecht) */
  jurisdiction: "DE",
  /** Name der Firma bzw. des Betreibers */
  name: PLACEHOLDER,
  /** Rechtsform, z.B. Einzelunternehmen, GmbH. Optional: leer lassen (""), wenn nicht vorhanden */
  legalForm: PLACEHOLDER,
  street: PLACEHOLDER,
  zipCity: PLACEHOLDER,
  country: PLACEHOLDER,
  email: PLACEHOLDER,
  /** Telefon. Optional: leer lassen (""), wenn nicht vorhanden */
  phone: PLACEHOLDER,
  /** Vertretungsberechtigte Person(en) (nur DE-Impressum). Optional: leer lassen (""), wenn nicht vorhanden */
  representative: PLACEHOLDER,
  /** Handelsregister und Registernummer. Optional: leer lassen (""), wenn nicht vorhanden */
  register: PLACEHOLDER,
  /** Umsatzsteuer-Identifikationsnummer bzw. in der Schweiz UID/MWST-Nummer. Optional: leer lassen (""), wenn nicht vorhanden */
  vatId: PLACEHOLDER,
  /** Zustaendige Datenschutz-Aufsichtsbehoerde (nur DE; in der Schweiz ist es der EDÖB). Optional: leer lassen (""), wenn nicht vorhanden */
  supervisoryAuthority: PLACEHOLDER,
  /** Hosting-Anbieter / Rechenzentrum. Optional: leer lassen (""), wenn nicht vorhanden */
  hosting: PLACEHOLDER,
  /** Zahlungsanbieter, sobald angebunden (z.B. Stripe). Optional: leer lassen (""), wenn nicht vorhanden */
  paymentProvider: PLACEHOLDER,
  /** Stand der Texte */
  lastUpdated: PLACEHOLDER,
};

export function isPlaceholder(value: string): boolean {
  return value === PLACEHOLDER;
}
