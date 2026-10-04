// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../services/api";
import { getLang, setLang } from "../i18n";
import { adoptUserLocale, changeLanguage } from "./locale";

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); setLang("de"); });
afterEach(() => { localStorage.clear(); setLang("de"); });

describe("changeLanguage", () => {
  it("wechselt die Oberfläche und speichert die Sprache am Konto, wenn angemeldet", async () => {
    localStorage.setItem("astra_access_token", "t");
    const update = vi.spyOn(api, "updateAccountLocale").mockResolvedValue({});
    changeLanguage("en");
    expect(getLang()).toBe("en");
    await vi.waitFor(() => expect(update).toHaveBeenCalledWith("en"));
  });

  it("ruft ohne Anmeldung die API nicht auf", () => {
    const update = vi.spyOn(api, "updateAccountLocale").mockResolvedValue({});
    changeLanguage("en");
    expect(getLang()).toBe("en");
    expect(update).not.toHaveBeenCalled();
  });

  it("ignoriert Fehler des Backends (404/400/Netz) still, die Oberfläche bleibt umgestellt", async () => {
    localStorage.setItem("astra_access_token", "t");
    const update = vi.spyOn(api, "updateAccountLocale").mockRejectedValue(new Error("nicht gefunden"));
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    changeLanguage("en");
    await vi.waitFor(() => expect(update).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));
    process.off("unhandledRejection", unhandled);
    expect(unhandled).not.toHaveBeenCalled();
    expect(getLang()).toBe("en");
  });
});

describe("adoptUserLocale", () => {
  it("übernimmt die am Konto gespeicherte Sprache", () => {
    adoptUserLocale({ locale: "en" });
    expect(getLang()).toBe("en");
    adoptUserLocale({ locale: "de" });
    expect(getLang()).toBe("de");
  });

  it("lässt die Auswahl dieses Browsers bei null, fehlendem Feld oder unbekanntem Wert", () => {
    setLang("en");
    adoptUserLocale({ locale: null });
    adoptUserLocale({});
    adoptUserLocale({ locale: "fr" as never });
    adoptUserLocale(null);
    expect(getLang()).toBe("en");
  });
});
