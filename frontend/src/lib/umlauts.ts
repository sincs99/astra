/**
 * Das Backend liefert viele deutsche Meldungen in ASCII-Schreibweise ("Ungueltige Anmeldedaten").
 * Fuer Kunden korrigieren wir bekannte ganze Woerter; unbekannte Woerter bleiben unveraendert,
 * damit nie ein Wort wie "neue" oder "Queue" verfaelscht wird.
 */
const WORDS: Record<string, string> = {
  fuer: "für", Fuer: "Für", zurueck: "zurück", Zurueck: "Zurück", ueber: "über", Ueber: "Über", ueberein: "überein",
  geloescht: "gelöscht", Geloescht: "Gelöscht", loeschen: "löschen", Loeschen: "Löschen", Loescht: "Löscht", Loest: "Löst",
  moeglich: "möglich", gueltig: "gültig", gueltige: "gültige", gueltiges: "gültiges", gueltigen: "gültigen",
  ungueltig: "ungültig", Ungueltig: "Ungültig", ungueltige: "ungültige", Ungueltige: "Ungültige",
  ungueltiger: "ungültiger", Ungueltiger: "Ungültiger", ungueltiges: "ungültiges", Ungueltiges: "Ungültiges",
  geaendert: "geändert", aendern: "ändern", bestaetigt: "bestätigt", bestaetige: "bestätige", bestaetigen: "bestätigen",
  Bestaetigung: "Bestätigung", Bestaetigungs: "Bestätigungs", unbestaetigt: "unbestätigt",
  Kuendigung: "Kündigung", gekuendigt: "gekündigt", Verlaengerung: "Verlängerung", verlaengert: "verlängert",
  ueberfaellig: "überfällig", Ueberfaellige: "Überfällige", ueberfaelliger: "überfälliger",
  verfuegbar: "verfügbar", hinzugefuegt: "hinzugefügt", hinzufuegen: "hinzufügen", ausgefuehrt: "ausgeführt", ausfuehren: "ausführen",
  gehoert: "gehört", zugehoerigen: "zugehörigen", spaeter: "später", hoechstens: "höchstens",
  zurueckgesetzt: "zurückgesetzt", zuruecksetzen: "zurücksetzen", Zuruecksetzen: "Zurücksetzen",
  Prueft: "Prüft", prueft: "prüft", laeuft: "läuft", Verraet: "Verrät", unterstuetzter: "unterstützter", Unterstuetzt: "Unterstützt",
  Kapazitaet: "Kapazität", kapazitaet: "kapazität", Ueberallokation: "Überallokation", ueberallokation: "überallokation",
  Passwoerter: "Passwörter", zusaetzlich: "zusätzlich", ausgeloest: "ausgelöst",
};

const PATTERN = new RegExp(`\\b(${Object.keys(WORDS).sort((a, b) => b.length - a.length).join("|")})\\b`, "g");

export function fixUmlauts(text: string): string {
  return text.replace(PATTERN, (word) => WORDS[word]);
}
