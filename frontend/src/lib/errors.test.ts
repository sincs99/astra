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
