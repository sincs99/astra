// Kopiert die Design-Tokens (Quelle: ../design/tokens.css) nach src/styles/tokens.css.
import { readFileSync, writeFileSync } from "node:fs";
const src = new URL("../../design/tokens.css", import.meta.url);
const dst = new URL("../src/styles/tokens.css", import.meta.url);
const header = "/* KOPIE von ../design/tokens.css (Quelle). Nicht hier bearbeiten: `npm run sync:tokens` ausführen. Der Docker-Build-Kontext ist frontend/, daher die Kopie. */\n";
writeFileSync(dst, header + readFileSync(src, "utf8"));
console.log("Tokens synchronisiert");
