import { describe, expect, it } from "vitest";
import { fixUmlauts } from "./umlauts";

describe("fixUmlauts", () => {
  it("korrigiert bekannte ASCII-Woerter aus Backend-Meldungen", () => {
    expect(fixUmlauts("Ungueltige Anmeldedaten")).toBe("Ungültige Anmeldedaten");
    expect(fixUmlauts("Passwort geaendert, bitte bestaetige zuerst deine E-Mail")).toBe("Passwort geändert, bitte bestätige zuerst deine E-Mail");
    expect(fixUmlauts("Zu viele offene Bestellungen – bitte erst bezahlen oder stornieren")).toBe("Zu viele offene Bestellungen – bitte erst bezahlen oder stornieren");
    expect(fixUmlauts("Instance geloescht, Kuendigung zum Laufzeitende vorgemerkt")).toBe("Instance gelöscht, Kündigung zum Laufzeitende vorgemerkt");
  });

  it("korrigiert auch Fehlertexte der Platzierung", () => {
    expect(fixUmlauts("Kein Agent mit freiem Endpoint und ausreichender Kapazitaet verfügbar")).toBe("Kein Agent mit freiem Endpoint und ausreichender Kapazität verfügbar");
  });

  it("veraendert keine Teilwoerter und keine unbekannten Woerter", () => {
    const text = "neue Queue, true value, Dateien, Blueprint, continue, fuerst, Ueberblick";
    expect(fixUmlauts(text)).toBe(text);
  });

  it("laesst bereits korrekte Umlaute und Leerstring unveraendert", () => {
    expect(fixUmlauts("Gültig für dich")).toBe("Gültig für dich");
    expect(fixUmlauts("")).toBe("");
  });
});
