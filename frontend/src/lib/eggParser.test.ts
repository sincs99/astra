import { describe, expect, it } from "vitest";
import { parseEgg } from "./eggParser";

describe("parseEgg", () => {
  it("liest Name, Autor, erstes Image und Variablenanzahl", () => {
    const { egg, preview } = parseEgg(JSON.stringify({
      name: "Minecraft",
      author: "a@b.de",
      docker_images: { Java17: "ghcr.io/x/java:17", Java21: "ghcr.io/x/java:21" },
      variables: [{}, {}, {}],
    }));
    expect(egg.name).toBe("Minecraft");
    expect(preview).toEqual({ name: "Minecraft", author: "a@b.de", image: "ghcr.io/x/java:17", variableCount: 3 });
  });

  it("unterstuetzt das alte Feld 'image' und fehlende Variablen", () => {
    const { preview } = parseEgg(JSON.stringify({ name: "Old", image: "foo/bar" }));
    expect(preview.image).toBe("foo/bar");
    expect(preview.variableCount).toBe(0);
    expect(preview.author).toBeNull();
  });

  it("lehnt ungueltiges JSON ab", () => {
    expect(() => parseEgg("nope")).toThrow("Kein gültiges JSON");
  });

  it.each(["[]", "null", "42", '"text"'])("lehnt Nicht-Objekt %s ab", (input) => {
    expect(() => parseEgg(input)).toThrow("JSON-Objekt");
  });

  it("verlangt ein nicht leeres 'name'", () => {
    expect(() => parseEgg("{}")).toThrow("'name'");
    expect(() => parseEgg('{"name":"  "}')).toThrow("'name'");
    expect(() => parseEgg('{"name":5}')).toThrow("'name'");
  });
});
