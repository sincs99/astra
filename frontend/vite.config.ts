import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { readFileSync } from "node:fs";

/** Setzt den Markennamen aus src/legal/operator.ts in den <title> von index.html (vor dem ersten Rendern, ohne Aufblitzen). */
function brandTitle() {
  return {
    name: "brand-title",
    transformIndexHtml(html: string) {
      const source = readFileSync(fileURLToPath(new URL("./src/legal/operator.ts", import.meta.url)), "utf8");
      const brand = /\bbrand:\s*"([^"]+)"/.exec(source)?.[1] ?? "Astra";
      const safe = brand.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
      return html.replace(/<title>[^<]*<\/title>/, `<title>${safe}</title>`);
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), brandTitle()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    globalSetup: ["./src/test/tz.ts"],
  },
  // Build-Konfiguration fuer Produktion
  build: {
    outDir: "dist",
    sourcemap: mode !== "production",
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:5000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
}));
