// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { THEME_STORAGE_KEY, applyTheme, getThemePreference, resolveTheme, setThemePreference, watchSystemTheme } from "./theme";

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

  it("'system' entfernt den Speicherwert und setzt data-theme explizit nach der System-Einstellung", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("light"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    setThemePreference("dark");
    setThemePreference("system");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    applyTheme("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    vi.unstubAllGlobals();
  });

  it("gilt ohne matchMedia als dunkel (Standard)", () => {
    expect(resolveTheme("system")).toBe("dark");
  });

  it("folgt Systemwechseln nur bei der Wahl 'system'", () => {
    let listener: () => void = () => {};
    let light = false;
    vi.stubGlobal("matchMedia", (q: string) => ({
      get matches() { return light && q.includes("light"); }, media: q,
      addEventListener: (_: string, l: () => void) => { listener = l; }, removeEventListener: () => {},
    }));
    const stop = watchSystemTheme();
    light = true; listener();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    setThemePreference("dark");
    light = false; listener();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    stop();
    vi.unstubAllGlobals();
  });
});
