/**
 * Tests dürfen nie vom Inhalt von legal/operator.ts abhängen: der Betreiber trägt dort seine echten Daten ein
 * (Marke, Rechtsraum, Adresse …). Für alle Tests gilt stattdessen diese Fixture mit den Standardwerten
 * (brand "Astra", jurisdiction "DE", alle Angaben noch Platzhalter). Tests, die einen anderen Wert brauchen,
 * schalten ihn gezielt um (z. B. `OPERATOR.jurisdiction = "CH"`) und setzen ihn danach zurück.
 */
import { vi } from "vitest";

vi.mock("../legal/operator", () => {
  const PLACEHOLDER = "[vom Betreiber auszufüllen]";
  return {
    PLACEHOLDER,
    OPERATOR: {
      brand: "Astra",
      jurisdiction: "DE",
      name: PLACEHOLDER,
      legalForm: PLACEHOLDER,
      street: PLACEHOLDER,
      zipCity: PLACEHOLDER,
      country: PLACEHOLDER,
      email: PLACEHOLDER,
      phone: PLACEHOLDER,
      representative: PLACEHOLDER,
      register: PLACEHOLDER,
      vatId: PLACEHOLDER,
      supervisoryAuthority: PLACEHOLDER,
      hosting: PLACEHOLDER,
      paymentProvider: PLACEHOLDER,
      lastUpdated: PLACEHOLDER,
    },
    isPlaceholder: (value: string) => value === PLACEHOLDER,
  };
});

// Auf langsamen CI-Runnern darf ein findBy…/waitFor länger warten (Standard 1 s); bei schnellen Läufen kostet das nichts.
import { configure } from "@testing-library/react";
configure({ asyncUtilTimeout: 4000 });
