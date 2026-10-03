/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API Base-URL (Standard: /api) */
  readonly VITE_API_BASE_URL?: string;
  /** WebSocket Base-URL (Standard: auto aus window.location) */
  readonly VITE_WS_BASE_URL?: string;
  /** "true" blendet Shop/Bestellungen/Produkte in der Navigation ein (Phase 4) */
  readonly VITE_SHOP_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
