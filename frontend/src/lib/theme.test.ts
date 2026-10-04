// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { THEME_STORAGE_KEY, applyTheme, getThemePreference, setThemePreference } from "./theme";

beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });
afterEach(() => { localStorage.clear(); document.documentElement.removeAttribute("data-theme"); });

describe("theme", () => {
  it("nimmt ohne gespeicherte Wahl 'system' und ignoriert ungültige Werte", () => {
    expect(getThemePreference()).toBe("system");
    localStorage.setItem(THEME_STORAGE_KEY, "neon");
    expect(getThemePreference()).toBe("system");
  });

  it("speichert Hell/Dunkel und setzt data-theme", () => {
    setThemePreference("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(getThemePreference()).toBe("dark");
    setThemePreference("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("'system' entfernt Speicherwert und data-theme wieder", () => {
    setThemePreference("dark");
    setThemePreference("system");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
