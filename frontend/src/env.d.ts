/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API Base-URL (Standard: /api) */
  readonly VITE_API_BASE_URL?: string;
  /** WebSocket Base-URL (Standard: auto aus window.location) */
  readonly VITE_WS_BASE_URL?: string;
  /** "true" zeigt "Passwort aendern" auf der Konto-Seite (Backend: POST /auth/change-password) */
  readonly VITE_CHANGE_PASSWORD_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
