import { describe, expect, it } from "vitest";
import { friendlyApiMessage } from "./errors";

describe("friendlyApiMessage", () => {
  it("uebersetzt den Admin-Guard in eine verständliche Meldung", () => {
    expect(friendlyApiMessage(403, "Admin-Berechtigung erforderlich")).toBe("Nur Administratoren dürfen diese Aktion ausführen.");
  });
  it("laesst andere Meldungen unveraendert", () => {
    expect(friendlyApiMessage(403, "Fehlende Berechtigung: file.read")).toBe("Fehlende Berechtigung: file.read");
    expect(friendlyApiMessage(404, "Admin-Berechtigung erforderlich")).toBe("Admin-Berechtigung erforderlich");
  });
});

describe("Allgemeine Meldungen statt technischer Statuscodes", () => {
  it.each([
    [500, /Fehler aufgetreten/],
    [502, /später erneut/],
    [429, /Zu viele Anfragen/],
    [404, /nicht gefunden/],
    [403, /Berechtigung/],
    [400, /prüfe deine Eingaben/],
  ])("Status %i", (status, expected) => {
    expect(friendlyApiMessage(status, `Request failed: ${status}`)).toMatch(expected);
    expect(friendlyApiMessage(status, `Request failed: ${status}`)).not.toMatch(/Request failed/);
  });

  it("laesst konkrete Backend-Meldungen stehen", () => {
    expect(friendlyApiMessage(409, "Zu viele offene Bestellungen (5)")).toBe("Zu viele offene Bestellungen (5)");
  });
});
