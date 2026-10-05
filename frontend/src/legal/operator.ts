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
  brand: "Astrahost",
  /** "DE" (Standard) oder "CH" (Schweiz: Anbieterkennzeichnung nach UWG, Datenschutz nach DSG, kein Widerrufsrecht) */
  jurisdiction: "CH",
  /** Name der Firma bzw. des Betreibers */
  name: 'Pascal Konezciny',
  /** Rechtsform, z.B. Einzelunternehmen, GmbH */
  legalForm: 'EG',
  street: 'Heimstrasse 5',
  zipCity: '5430 Wettingen',
  country: 'Switzerland',
  email: 'hello@astrahost.ch',
  phone: '079 123 45 67',
  /** Vertretungsberechtigte Person(en) */
  representative: 'Pascal Konezciny',
  /** Handelsregister und Registernummer, falls vorhanden */
  register: 'CHE-123.456.789',
  /** Umsatzsteuer-Identifikationsnummer bzw. in der Schweiz UID/MWST-Nummer, falls vorhanden */
  vatId: 'CHE-123.456.789',
  /** Zustaendige Datenschutz-Aufsichtsbehoerde (nur DE; in der Schweiz ist es der EDÖB) */
  supervisoryAuthority: 'EDÖB',
  /** Hosting-Anbieter / Rechenzentrum */
  hosting: 'Astrahost',
  /** Zahlungsanbieter, sobald angebunden (z.B. Stripe) */
  paymentProvider: 'Stripe',
  /** Stand der Texte */
  lastUpdated: '05.10.2026',
};

export function isPlaceholder(value: string): boolean {
  return value === PLACEHOLDER;
}
