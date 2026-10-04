# Astra – Projektregeln für Claude Code

## Reference-Ordner
`reference/` (Pterodactyl-Referenzpanel) ist schreibgeschützt: nur lesen, nie erstellen, bearbeiten oder löschen. Details in `.roo/rules.md`.

## Design
Alle UI-Arbeit folgt `design/DESIGN.md`. Farben, Schrift und Maße kommen ausschließlich aus `design/tokens.css` (CSS-Variablen), keine Hex-Werte im Komponenten-Code. Visuelle Referenz: `design/mockups/*.html` – vor dem Bau einer Seite das passende Mockup lesen und dessen Markup/Styles übernehmen.

## Prüfungen vor einem Push
- Backend: alle `backend/test_m*.py` einzeln mit `python3` ausführen (ohne gesetzte `APP_ENV`/`SECRET_KEY`), Migrations-Roundtrip auf SQLite.
- Frontend: `npx tsc --noEmit -p .`, `npx vitest run`, `npm run build`; bei Änderungen am Kundenfluss zusätzlich `./e2e/run-local.sh`.
