# Astra – Frontend

React-Frontend für Astra (Vite + TypeScript, React Router, keine UI-Bibliothek: gemeinsame Komponenten
unter `src/components/ui`, Konventionen in [docs/ui-conventions.md](../docs/ui-conventions.md)).

## Voraussetzungen

- Node.js 20+
- npm

## Installation und Start

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, /api wird an http://localhost:5000 weitergeleitet
npm run build      # tsc -b && vite build
npm test           # Vitest (jsdom, @testing-library/react), Zeitzone fest auf UTC
```

## Routen

| Route | Seite | Wer |
|---|---|---|
| `/login`, `/register`, `/password-reset`, `/password-reset/confirm`, `/verify-email` | Anmeldung, Registrierung, Passwort-Reset, E-Mail-Bestätigung | öffentlich |
| `/impressum`, `/datenschutz`, `/agb` | Rechtsseiten (Platzhalter, siehe unten) | öffentlich |
| `/` | Dashboard (Kunden: eigene Server; Admins zusätzlich offene Bestellungen) | angemeldet |
| `/instances/:uuid` | Server-Detail (Steuerung, Konsole, Dateien, Backups, SFTP, Löschen) | angemeldet |
| `/shop`, `/orders` | Shop und Meine Bestellungen (Zahlung, Kündigung) | angemeldet |
| `/account`, `/account/ssh-keys` | Konto (Passwort, MFA, API-Keys), SSH-Keys | angemeldet |
| `/admin/agents`, `/admin/agents/monitoring` | Agents (Kapazität, Health), Fleet Monitoring | Admin |
| `/admin/blueprints`, `/admin/instances` | Blueprints (inkl. Egg-Import), Instances (Platzierung, Transfer, Löschen) | Admin |
| `/admin/products`, `/admin/orders` | Produkte, Bestellungen (Zahlung bestätigen, verlängern) | Admin |
| `/admin/webhooks`, `/admin/jobs`, `/admin/system` | Webhooks, Jobs, System | Admin |

Admin-Routen leiten Kunden aufs Dashboard um; das ist nur Komfort, die Absicherung liegt im Backend.
Geschützte Routen leiten ohne Login zu `/login?redirect=<Seite>` (nur interne Pfade).

## Projektstruktur

```
src/
├── app/            Router, Provider
├── pages/          eine Datei pro Route (+ Tests)
├── components/     fachliche Komponenten; ui/ = gemeinsame Bausteine (PageLayout, StatusBadge, Toast, ...)
├── hooks/          useAutoRefresh, useCurrentUser, useMediaQuery
├── lib/            reine Logik ohne React (Geld, Datum/UTC, Formulare, Umlaute, Weiterleitungen, Checkout)
├── legal/          Betreiberangaben und Texte, die der Betreiber pflegt
├── services/api.ts API-Client und Typen
└── test/           Test-Fixtures, feste Testzeitzone
```

## Vom Betreiber zu pflegen

- `src/legal/operator.ts`: Name, Anschrift, Kontakt, Register, USt-IdNr., Aufsichtsbehörde, Hosting- und
  Zahlungsanbieter für Impressum, Datenschutz und AGB. Offene Platzhalter erscheinen gelb markiert.
  Die Rechtstexte in `src/pages/LegalPages.tsx` sind nur eine Struktur und müssen rechtlich geprüft werden.
- `src/legal/payment.ts`: Hinweistext zur Zahlung per Überweisung (z. B. mit Bankverbindung).

## Hinweise für die Entwicklung

- Zeitstempel des Backends sind UTC; für die Anzeige immer `lib/dates.ts` verwenden (`parseUtc`).
- Backend-Fehlermeldungen laufen durch `lib/errors.ts` (verständliche Texte, Umlaute korrigiert).
- Texte für Kunden auf Deutsch, ohne Fachbegriffe ("Server" statt "Instance").
- Barrierefreiheit prüfen (axe-core, WCAG 2 A/AA) und Kontraste mindestens 4,5:1.
