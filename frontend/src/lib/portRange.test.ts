import { describe, expect, it } from "vitest";
import { parsePortRange } from "./portRange";

describe("parsePortRange", () => {
  it("parst einen Einzelport", () => {
    expect(parsePortRange("25565")).toEqual({ start: 25565, end: 25565 });
  });
  it("parst Bereiche mit Bindestrich, Leerzeichen und Gedankenstrich", () => {
    expect(parsePortRange("25565-25600")).toEqual({ start: 25565, end: 25600 });
    expect(parsePortRange(" 25565 - 25600 ")).toEqual({ start: 25565, end: 25600 });
    expect(parsePortRange("25565\u201325600")).toEqual({ start: 25565, end: 25600 });
  });
  it.each(["", "abc", "1-", "-5", "1-2-3", "12.5"])("lehnt '%s' ab", (input) => {
    expect(typeof parsePortRange(input)).toBe("string");
  });
  it("prueft Grenzen, Reihenfolge und Maximalgroesse", () => {
    expect(parsePortRange("0")).toMatch(/1 und 65535/);
    expect(parsePortRange("1-70000")).toMatch(/1 und 65535/);
    expect(parsePortRange("200-100")).toMatch(/kleiner oder gleich/);
    expect(parsePortRange("1-1001")).toMatch(/Maximal 1000/);
    expect(parsePortRange("1-1000")).toEqual({ start: 1, end: 1000 });
  });
});
