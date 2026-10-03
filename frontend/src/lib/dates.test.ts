import { describe, expect, it } from "vitest";
import { formatDate, formatDateLong, formatDateTime, formatLogTime, formatTimeAgo, parseUtc } from "./dates";

describe("parseUtc", () => {
  it("behandelt Zeitstempel ohne Zeitzone als UTC", () => {
    expect(parseUtc("2026-10-03T12:00:00").toISOString()).toBe("2026-10-03T12:00:00.000Z");
    expect(parseUtc("2026-10-03T12:00:00.123456").toISOString()).toBe("2026-10-03T12:00:00.123Z");
  });
  it("laesst Angaben mit Zeitzone unveraendert", () => {
    expect(parseUtc("2026-10-03T12:00:00Z").toISOString()).toBe("2026-10-03T12:00:00.000Z");
    expect(parseUtc("2026-10-03T14:00:00+02:00").toISOString()).toBe("2026-10-03T12:00:00.000Z");
    expect(parseUtc("2026-10-03T10:00:00-02:00").toISOString()).toBe("2026-10-03T12:00:00.000Z");
  });
});

describe("Formatierung", () => {
  it("zeigt – ohne Wert oder bei ungueltigem Datum", () => {
    expect(formatDate(null)).toBe("–");
    expect(formatDate(undefined)).toBe("–");
    expect(formatDate("kein datum")).toBe("–");
    expect(formatDateTime("")).toBe("–");
  });
  it("formatiert Datum und Uhrzeit (UTC-Mitternacht bleibt am selben Tag in UTC-Umgebung)", () => {
    // Die Testumgebung laeuft in UTC; die Formatierung nutzt die lokale Zeit des Browsers.
    expect(formatDate("2026-11-15T00:00:00")).toBe(new Date("2026-11-15T00:00:00Z").toLocaleDateString("de-CH"));
    expect(formatDateTime("2026-11-15T09:05:00")).toMatch(/^\d{1,2}\.\d{1,2}\.2026 \d{2}:\d{2}$/);
  });
});

describe("formatTimeAgo", () => {
  const now = Date.UTC(2026, 9, 3, 12, 0, 0);

  it("rechnet naive Backend-Zeitstempel als UTC (unabhaengig von der Browser-Zeitzone)", () => {
    expect(formatTimeAgo("2026-10-03T11:59:30", now)).toBe("gerade eben");
    expect(formatTimeAgo("2026-10-03T11:55:00", now)).toBe("vor 5 Min.");
    expect(formatTimeAgo("2026-10-03T10:00:00", now)).toBe("vor 2 Std.");
    expect(formatTimeAgo("2026-09-30T12:00:00", now)).toBe("vor 3 Tagen");
  });

  it("liefert dasselbe Ergebnis mit und ohne Zeitzonen-Suffix", () => {
    expect(formatTimeAgo("2026-10-03T10:00:00+00:00", now)).toBe(formatTimeAgo("2026-10-03T10:00:00", now));
    expect(formatTimeAgo("2026-10-03T10:00:00Z", now)).toBe("vor 2 Std.");
  });

  it("behandelt Zukunft als 'gerade eben' und ungueltige Eingaben unveraendert", () => {
    expect(formatTimeAgo("2026-10-03T13:00:00", now)).toBe("gerade eben");
    expect(formatTimeAgo("kaputt", now)).toBe("kaputt");
  });
});

describe("Protokoll- und Langformat", () => {
  it("formatLogTime zeigt Sekunden und – ohne Wert", () => {
    expect(formatLogTime("2026-10-03T14:05:09")).toMatch(/14:05:09/);
    expect(formatLogTime(null)).toBe("–");
    expect(formatLogTime("x")).toBe("–");
  });
  it("formatDateLong schreibt den Monat aus", () => {
    expect(formatDateLong("2026-10-03T00:00:00")).toMatch(/2026/);
    expect(formatDateLong(undefined)).toBe("–");
  });
});
