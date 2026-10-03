import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, parseUtc } from "./dates";

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
