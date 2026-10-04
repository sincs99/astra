import { describe, expect, it } from "vitest";
import { statusLabel } from "./StatusBadge";

describe("statusLabel", () => {
  it("benennt Erstattung und Zahlungsstreit auf Deutsch", () => {
    expect(statusLabel("refunded")).toBe("Erstattet");
    expect(statusLabel("disputed")).toBe("Zahlung angefochten");
  });

  it("faellt bei unbekanntem Status auf den Rohwert zurueck", () => {
    expect(statusLabel("irgendwas")).toBe("irgendwas");
  });
});
