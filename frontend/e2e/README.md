# E2E-Durchlauf (Playwright)

Ein Browser-Durchlauf gegen das **echte Backend** (SQLite, Stub-Runner, `PAYMENT_PROVIDER=manual`):

1. Admin legt per API Blueprint, Node (mit Endpoints) und Paket an
2. Kunde registriert sich und meldet sich an
3. Kunde bestellt das Paket im Shop (Status "Zahlung ausstehend")
4. Admin markiert die Bestellung als bezahlt
5. Kunde sieht den Server im Dashboard

## Lokal starten

```bash
cd frontend
npm ci
PYTHON=/pfad/zum/python ./e2e/run-local.sh      # Python-Umgebung mit backend/requirements.txt
```

Das Skript legt eine temporäre Datenbank an, startet Backend (Port 5000) und Frontend-Preview (Port 4190), führt
`e2e/flow.mjs` aus und räumt danach alles wieder auf. Das Frontend wird bei jedem Lauf neu gebaut.

- Chromium: `CHROMIUM_PATH` setzen oder `npx playwright-core install chromium` (vorinstalliert unter `/opt/pw-browsers/chromium` wird automatisch gefunden).
- Die Ports sind fest (die Vite-Proxy-Konfiguration zeigt auf `localhost:5000`); sind sie belegt, bricht das Skript ab.
- Bei einem Fehler schreibt der Lauf `e2e-fehler-<Schritt>.png` ins aktuelle Verzeichnis.

## CI

`.github/workflows/e2e.yml` führt denselben Durchlauf aus (manuell und bei Änderungen an `frontend/e2e/**`).
Der Job wurde lokal, aber noch nicht auf GitHub-Runnern verifiziert. Läuft er dort nicht stabil, bleibt der lokale Lauf der
Referenzweg und der Job kann auf `workflow_dispatch` beschränkt oder entfernt werden.

Hinweis: Preview, Proxy-Ziel und Test-URLs sind bewusst auf `127.0.0.1` festgelegt. Mit `localhost` bindet der Preview-Server auf manchen Runnern (Node 20, GitHub Actions) nur an IPv6, und der Erreichbarkeits-Check über IPv4 schlägt fehl.
