import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = new URL("../../../design/tokens.css", import.meta.url);
const copy = new URL("./tokens.css", import.meta.url);

describe("Design-Tokens", () => {
  // Nur prüfbar, wenn design/ vorhanden ist (im Docker-Build-Kontext frontend/ fehlt der Ordner)
  it.skipIf(!existsSync(source))("src/styles/tokens.css ist eine aktuelle Kopie von design/tokens.css", () => {
    const body = readFileSync(copy, "utf8").split("\n").slice(1).join("\n");
    expect(body).toBe(readFileSync(source, "utf8"));
  });
});
