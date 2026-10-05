import { describe, expect, it, vi } from "vitest";

/** Prüft nur die Form der echten Betreiberdatei, nie ihren Inhalt: die Werte trägt der Betreiber ein. */
describe("legal/operator.ts (echte Datei)", () => {
  it("hat alle Felder als nicht leere Texte, einen gültigen Rechtsraum und eine Marke", async () => {
    const real = await vi.importActual<typeof import("./operator")>("./operator");
    const keys = ["brand", "jurisdiction", "name", "legalForm", "street", "zipCity", "country", "email", "phone",
      "representative", "register", "vatId", "supervisoryAuthority", "hosting", "paymentProvider", "lastUpdated"] as const;
    for (const key of keys) {
      expect(typeof real.OPERATOR[key], key).toBe("string");
      expect(real.OPERATOR[key].trim().length, key).toBeGreaterThan(0);
    }
    expect(["DE", "CH"]).toContain(real.OPERATOR.jurisdiction);
  });

  it("lässt sich für den Build lesen: brand steht als einfaches String-Literal in der Datei (Vite-Plugin für index.html)", async () => {
    const { readFileSync } = await import("node:fs");
    const source = readFileSync(new URL("./operator.ts", import.meta.url), "utf8");
    expect(/\bbrand:\s*"([^"]+)"/.exec(source)?.[1]).toBeTruthy();
  });
});
