// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { de } from "./de";
import { en } from "./en";
import { LANG_STORAGE_KEY, getLang, initLang, setLang, t } from "./index";
import { LangRoot } from "./LangRoot";
import { LoginPage } from "../pages/LoginPage";
import { formatPeriod } from "../lib/money";
import { formatTimeAgo } from "../lib/dates";
import { statusLabel } from "../components/ui/StatusBadge";

beforeEach(() => { localStorage.clear(); initLang(); });
afterEach(() => { cleanup(); localStorage.clear(); initLang(); });

const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");

describe("Woerterbuecher", () => {
  it("haben dieselben Schluessel, keine leeren Texte und gleiche Platzhalter", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(de).sort());
    for (const key of Object.keys(de) as (keyof typeof de)[]) {
      expect(de[key].trim(), `de ${key}`).not.toBe("");
      expect(en[key].trim(), `en ${key}`).not.toBe("");
      expect(placeholders(en[key]), `Platzhalter ${key}`).toBe(placeholders(de[key]));
    }
  });
});

describe("t()", () => {
  it("liefert Deutsch als Standard und ersetzt Platzhalter", () => {
    expect(getLang()).toBe("de");
    expect(t("auth.minLength", { n: 8 })).toBe("Mindestens 8 Zeichen");
  });

  it("wechselt auf Englisch, merkt die Wahl und kehrt zu Deutsch zurueck", () => {
    setLang("en");
    expect(t("auth.minLength", { n: 8 })).toBe("At least 8 characters");
    expect(localStorage.getItem(LANG_STORAGE_KEY)).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    initLang();
    expect(getLang()).toBe("en");
    setLang("de");
    expect(localStorage.getItem(LANG_STORAGE_KEY)).toBeNull();
  });

  it("uebersetzt auch Status, Zeitangaben und Zeitraeume", () => {
    setLang("en");
    expect(statusLabel("pending_payment")).toBe("Payment pending");
    expect(formatPeriod(1)).toBe("1 day");
    expect(formatPeriod(30)).toBe("30 days");
    expect(formatTimeAgo(new Date(Date.now() - 5 * 60_000).toISOString())).toBe("5 min ago");
  });
});

describe("Umschalter", () => {
  it("wechselt die Seite per Klick auf English und zurueck", () => {
    render(<MemoryRouter><LangRoot><LoginPage /></LangRoot></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Astra Login" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("heading", { name: "Astra Sign in" })).toBeTruthy();
    expect(screen.getByLabelText("Username or email")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Deutsch" }).getAttribute("lang")).toBe("de");
    fireEvent.click(screen.getByRole("button", { name: "Deutsch" }));
    expect(screen.getByRole("heading", { name: "Astra Login" })).toBeTruthy();
  });
});
