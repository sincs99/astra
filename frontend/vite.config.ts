import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
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
