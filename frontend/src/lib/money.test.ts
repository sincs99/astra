import { describe, expect, it } from "vitest";
import { centsToEuroInput, formatMoney, formatPeriod, formatPrice, parseEuroToCents } from "./money";

const plain = (s: string) => s.replace(/ | /g, " ");

describe("parseEuroToCents", () => {
  it.each([["9.99", 999], ["9,99", 999], ["10", 1000], ["0", 0], ["0,5", 50], ["0.05", 5], [" 12,3 ", 1230], ["19.90", 1990]])(
    "wandelt '%s' in %i Cent um", (input, cents) => { expect(parseEuroToCents(input)).toBe(cents); });

  it("vermeidet Gleitkomma-Fehler", () => {
    expect(parseEuroToCents("19.99")).toBe(1999);
    expect(parseEuroToCents("0.29")).toBe(29);
    expect(parseEuroToCents("1.15")).toBe(115);
  });

  it.each(["", "abc", "-1", "1.234", "1,2,3", "9.", ".5", "1e3", "12345678"])("lehnt '%s' ab", (input) => {
    expect(parseEuroToCents(input)).toBeNull();
  });
});

describe("Formatierung", () => {
  it("centsToEuroInput", () => {
    expect(centsToEuroInput(999)).toBe("9.99");
    expect(centsToEuroInput(5)).toBe("0.05");
    expect(centsToEuroInput(1000)).toBe("10.00");
    expect(centsToEuroInput(0)).toBe("0.00");
  });
  it("formatMoney und formatPrice", () => {
    expect(plain(formatMoney(999))).toBe("9,99 €");
    expect(plain(formatMoney(100000))).toBe("1.000,00 €");
    expect(plain(formatPrice(999, "EUR", 30))).toBe("9,99 € / 30 Tage");
    expect(plain(formatPrice(500, "EUR", 1))).toBe("5,00 € / 1 Tag");
  });
  it("kommt mit unbekannter Waehrung klar", () => {
    expect(formatMoney(999, "???")).toContain("9,99");
  });
  it("formatPeriod", () => {
    expect(formatPeriod(1)).toBe("1 Tag");
    expect(formatPeriod(30)).toBe("30 Tage");
  });
});
