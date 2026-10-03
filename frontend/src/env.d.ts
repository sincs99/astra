/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API Base-URL (Standard: /api) */
  readonly VITE_API_BASE_URL?: string;
  /** WebSocket Base-URL (Standard: auto aus window.location) */
  readonly VITE_WS_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
