# Astra – Pilot-Rollout-Plan

> Stand: 2026-03-16 · Ergebnis von M32 · Gilt für Astra v0.31+ und den Weg zu v1.0.0

---

## 1. Ziel des Pilotbetriebs

Der Pilot ist ein zeitlich begrenzter, kontrollierter Betrieb von Astra in einer **echten, aber risikobegrenzten Umgebung**. Er hat drei Ziele:

1. **Validierung**: Kernflows funktionieren im echten Betrieb (nicht nur in Tests)
2. **Stabilität**: Keine unerwarteten Ausfälle oder Datenverluste über die Pilotdauer
3. **Feedback**: Klare Rückmeldung zu Usability, Fehlern und Priorisierung der P1-Features

Der Pilot ist **keine Testphase** im Sinne von QA-Tests – diese sind bereits durch die Milestone-Tests (M10–M31) abgedeckt. Der Pilot ist der erste **reale Nutzungstest** durch echte Betreiber und Nutzer.

---

## 2. Pilotumfang

### Im Pilot aktiv

| Feature | Kernflow |
|---|---|
| User-Management | Benutzer anlegen, verwalten, API Keys vergeben |
| Agent/Fleet | 1–2 Agents registrieren, Health überwachen |
| Blueprint | Mindestens 1 reales Blueprint anlegen |
| Instance-Lifecycle | Erstellen, Install, Start, Stop, Delete |
| Console | Echtzeit-Konsole an laufender Instance |
| Files | Browse, Read, Write, Delete, Rename |
| Backups | Backup erstellen, wiederherstellen |
| Databases | Database anlegen, Passwort rotieren |
| Collaborators | Collaborator mit file.sftp und file.read einladen |
| Routines | Mindestens eine Routine definieren und ausführen |
| Webhooks | Webhook registrieren, Event auslösen |
| SSH Keys + SFTP | SSH Key hinterlegen, SFTP-Verbindung testen |
| Suspension | Instance sperren und entsperren |
| Maintenance | Agent in Maintenance setzen und wieder freigeben |
| Jobs | Job-Dashboard auf Plausibilität prüfen |
| System | Preflight, Version, Upgrade-Status prüfen |

### Bewusst NICHT im Pilot

| Feature | Begründung |
|---|---|
| Blueprint Import/Export | Nicht implementiert; P1-Backlog |
| OAuth / SSO | Nicht implementiert; P1-Backlog |
| Plugin-System | Bewusst nach v1.0 verschoben |
| Multi-Language | Nicht nötig für Pilotbetrieb |
| Mehrere Docker-Images pro Blueprint | P1-Backlog |
| Prometheus/Grafana | Externe Integration, kein Astra-Feature |

---

## 3. Beteiligte Rollen

| Rolle | Verantwortung |
|---|---|
| **Pilot-Admin** | Umgebung aufbauen, Bootstrapping, Agent-Setup |
| **Pilot-Nutzer (1–3)** | Echte Instance-Nutzung (Files, Console, Backups, SFTP) |
| **Reviewer** | Pilot-Findings dokumentieren, Abnahme durchführen |
| **Dev-Bereitschaft** | Ansprechbar für Blocker während des Pilots |

---

## 4. Pilotumgebung

### Minimale Infrastruktur

```
┌─────────────────────────────────────────────┐
│  Internet / User-Browser                    │
└─────────────────┬───────────────────────────┘
                  │ HTTPS (Port 443)
┌─────────────────▼───────────────────────────┐
│  Reverse Proxy (Nginx/Caddy/Traefik)        │
│  TLS-Terminierung, SSL-Zertifikat           │
└────────┬──────────────────────┬─────────────┘
         │ /api/*               │ /*
┌────────▼──────────┐  ┌───────▼────────────┐
│  Backend (Flask)  │  │  Frontend (React)  │
│  Port 5000        │  │  Port 80 (Nginx)   │
└────────┬──────────┘  └────────────────────┘
         │
┌────────▼──────────────────────────────────┐
│  PostgreSQL (Port 5432)                   │
│  Redis (Port 6379)                        │
└────────┬──────────────────────────────────┘
         │ Wings API
┌────────▼──────────────────────────────────┐
│  Agent 1 (Wings Daemon)                   │
│  z.B. 1–2 Pilot-Instances                 │
└───────────────────────────────────────────┘
```

### Mindest-Sizing

| Komponente | Minimum | Empfehlung |
|---|---|---|
| Astra Backend | 1 vCPU, 512 MB RAM | 2 vCPU, 1 GB RAM |
| PostgreSQL | shared oder 1 vCPU, 1 GB RAM | dediziert |
| Redis | 256 MB RAM | 512 MB RAM |
| Agent (Wings) | 2 vCPU, 2 GB RAM | 4 vCPU, 4 GB RAM |
| Gesamt | 4 vCPU, 4 GB RAM | 8 vCPU, 8 GB RAM |

### Konfiguration

```env
# backend/.env (Pilot)
APP_ENV=production
SECRET_KEY=<sicherer-zufallswert>
JWT_SECRET_KEY=<sicherer-zufallswert>
DATABASE_URL=postgresql://astra:pass@postgres:5432/astra
REDIS_URL=redis://redis:6379/0
RUNNER_ADAPTER=wings
BASE_URL=https://astra.pilot.example.com
CORS_ORIGINS=https://astra.pilot.example.com
AUTO_MIGRATE=true
PROXY_FIX_ENABLED=true
SESSION_COOKIE_SECURE=true
```

### Deployment

```bash
# 1. Umgebungsvariablen setzen
cp backend/.env.example .env && nano .env

# 2. Container starten
docker compose -f docker-compose.prod.yml up -d

# 3. Admin bootstrappen
docker compose exec backend python cli.py bootstrap \
    --username admin --email admin@example.com --password <passwort>

# 4. Health-Check
curl https://astra.pilot.example.com/health/ready
```

Vollständige Deployment-Anleitung: [operations.md](operations.md)

---

## 5. Pilot Go/No-Go-Checkliste

Vor Pilotstart muss jeder Punkt abgehakt sein:

### Infrastruktur

- [ ] Deployment erfolgreich (`docker compose up -d` ohne Fehler)
- [ ] PostgreSQL erreichbar und konfiguriert
- [ ] Redis erreichbar und konfiguriert
- [ ] Reverse Proxy mit TLS läuft, Zertifikat gültig
- [ ] `GET /health/ready` → 200 OK

### Astra-Backend

- [ ] Migrationen aktuell (`flask db current` = HEAD)
- [ ] Preflight grün (`GET /ops/preflight` → `compatible: true`)
- [ ] Bootstrap-Admin vorhanden und Login funktioniert
- [ ] Worker für Job-Queue gestartet (oder SyncQueue explizit als Pilot-Kompromiss akzeptiert)
- [ ] `GET /api/admin/health/detailed` → alle Checks grün

### Agent

- [ ] Mindestens 1 Agent in Astra registriert
- [ ] Agent-Health-Status = `healthy`
- [ ] Wings-Daemon auf Agent läuft und erreichbar
- [ ] Test-Endpoint angelegt

### Pilot-Readiness

- [ ] Test-Blueprint vorhanden
- [ ] Test-Instance erfolgreich erstellt (Status: `ready`)
- [ ] Test-Instance: Start/Stop funktioniert
- [ ] Test-Instance: Konsole öffnet sich
- [ ] Test-Backup erstellt
- [ ] Pilot-Nutzer haben Zugangsdaten erhalten

**Go-Entscheidung**: Alle Punkte grün → **Pilot kann starten**. Offene Punkte → Blocker klären, kein Pilotstart.

---

## 6. Pilot-Kernflows (verbindlich)

Die folgenden 12 Flows werden im Pilot **zwingend durchgeführt** – durch Pilot-Nutzer, nicht durch Dev-Team.

| # | Flow | Wer | Akzeptanzkriterium |
|---|---|---|---|
| 1 | Login & Navigation | Pilot-Admin + Nutzer | Login gelingt, alle Seiten ladbar |
| 2 | Agent anlegen / Health prüfen | Pilot-Admin | Agent erscheint healthy im Monitoring |
| 3 | Blueprint anlegen | Pilot-Admin | Blueprint mit Docker-Image und Variable |
| 4 | Instance erstellen | Pilot-Admin | Instance erhält Status `ready` |
| 5 | Instance: Power + Console | Pilot-Nutzer | Start/Stop, Konsole zeigt Output |
| 6 | Files: lesen / schreiben / löschen | Pilot-Nutzer | Alle Dateioperationen erfolgreich |
| 7 | Backup: erstellen / wiederherstellen | Pilot-Nutzer | Backup erstellt, Restore greift |
| 8 | Collaborator: einladen + Rechte prüfen | Pilot-Admin | Collaborator hat korrekte Rechte, falsche werden blockiert |
| 9 | SSH Key + SFTP-Auth | Pilot-Nutzer | Key hinterlegt, SFTP-Verbindung mit Key erlaubt |
| 10 | Suspension: sperren / entsperren | Pilot-Admin | SFTP + Console während Suspension blockiert, nach Unsuspend frei |
| 11 | Agent Maintenance: setzen / aufheben | Pilot-Admin | Deployment auf Maintenance-Agent wird blockiert (409) |
| 12 | Webhook + Activity-Log | Pilot-Admin | Event wird ausgelöst, Activity-Log zeigt Eintrag |

Jeder Flow wird im Pilot-Protokoll mit Pass/Fail und Anmerkungen dokumentiert.

---

## 7. Pilot-Protokoll

Vorlage für Pilot-Funde:

```markdown
## Pilot-Fund #<NR>

**Datum**: YYYY-MM-DD
**Reporter**: <Name>
**Flow**: <Nummer und Name aus Kernflows>
**Severity**: Blocker | Major | Minor | Nice-to-have

### Beschreibung
Was ist passiert?

### Erwartetes Verhalten
Was hätte passieren sollen?

### Schritte zur Reproduktion
1.
2.
3.

### Entscheidung
[ ] Release-Blocker → muss vor v1.0 behoben werden
[ ] P1 → nach v1.0 geplant
[ ] Akzeptiert / Won't fix
```

---

## 8. Feedback-Priorisierung

| Kategorie | Definition | Release-Konsequenz |
|---|---|---|
| **Blocker** | Datenverlust, Auth-Bypass, Absturz, Security-Lücke | Pilot-Stop, muss vor v1.0 behoben sein |
| **Major** | Kernflow unbrauchbar, konsistente Fehlfunktion | Behebt sich idealerweise vor v1.0; wenn nicht: dokumentiert und kommuniziert |
| **Minor** | Ergonomie-Problem, inkonsistente UX, seltener Fehler | P1-Backlog; kein v1.0-Blocker |
| **Nice-to-have** | Verbesserungsvorschlag, Wunschfeature | P2-Backlog |

**Release-Blockierend** ist nur «Blocker». Alles andere schiebt sich in den Post-v1.0-Backlog.

---

## 9. Pilotdauer

- **Empfohlene Pilotdauer**: 2–4 Wochen
- **Mindestbetrieb**: 5 Werktage ohne Blocker-Fund
- **Abschluss**: Alle 12 Kernflows als Pass dokumentiert, keine offenen Blocker

---

## 10. Rollback während des Pilots

Falls ein Blocker auftritt, der einen Pilot-Stop erfordert:

```bash
# 1. Astra stoppen
docker compose -f docker-compose.prod.yml down

# 2. Datenbank wiederherstellen (aus Pilot-Backup vor dem Fund)
./scripts/restore.sh ./backups/astra_backup_YYYYMMDD_HHMMSS.tar.gz

# 3. Alten Stand einspielen
git checkout <letzter-stabiler-tag>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 4. Migration rückgängig machen (falls nötig)
docker compose exec backend flask db downgrade -1
```

Vollständige Rollback-Anleitung: [upgrade-guide.md](upgrade-guide.md)

---

## 11. Scope-Freeze bis v1.0

Ab Pilotstart gilt Scope-Freeze. Folgendes ist erlaubt:

| Erlaubt | Beispiele |
|---|---|
| Bugfixes | Fehler, die im Pilot gefunden werden |
| Security Fixes | Authentifizierungs- oder Datenlecks |
| Ops-/Deployment-Fixes | Konfigurationsfehler, Health-Endpunkte |
| Kleine UX-Klarstellungen | Fehlermeldungen, Labels, Hinweistexte |
| Dokumentations-Updates | Ops-Guide, Limitations, Pilot-Protokoll |

| Nicht erlaubt | Beispiele |
|---|---|
| Neue Fachmodule | Plugin-System, OAuth, Mount-System |
| API-Breaking-Changes | neue Pflichtfelder, geänderte Response-Struktur |
| Schema-Umbauten | neue Felder ohne direkten Bugfix-Bezug |
| Neue Seiten / Flows | neue Frontendseiten ohne Bugfix-Bezug |
| P1/P2-Features | Blueprint-Import, Multiple-Docker-Images |

Ausnahme: Ein Blocker-Fund aus dem Pilot kann auch strukturelle Änderungen rechtfertigen, wenn keine andere Lösung möglich ist. Entscheidung explizit und dokumentiert.
