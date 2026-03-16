# Astra v1.0 – Scope-Definition

> Ergebnis des M31 Gap-Checks. Stand: 2026-03-16, Astra v0.30.0.
> Dieses Dokument definiert verbindlich, was zu v1.0 gehört, was bewusst nicht darin ist und was danach kommt.

---

## Bestandteil von v1.0

### User & Authentication

- [x] Benutzerverwaltung (CRUD, Admin-Flag)
- [x] Passwort-basierter Login
- [x] JWT-Session-Management
- [x] API-Key-Management (Bearer-Token, Erstellen/Widerrufen)
- [x] MFA / TOTP (Einrichten, Verifizieren, Deaktivieren)
- [x] SSH-Public-Key-Verwaltung pro Benutzer
- [x] Schlüsselbasierte SFTP-Authentifizierung (serverseitige Entscheidung)

### Instanz-Management

- [x] Instance Erstellen / Löschen
- [x] Power-Aktionen (Start, Stop, Restart, Kill)
- [x] Echtzeit-Konsole (WebSocket)
- [x] Ressourcen-Limits (CPU, Memory, Disk, IO, Swap)
- [x] Reinstallation
- [x] Config Rebuild / Sync
- [x] Instance Transfer zwischen Agents
- [x] Administrative Suspension / Unsuspend (mit Metadaten und Audit)
- [x] Container-Status-Tracking
- [x] Startup-Command-Konfiguration
- [x] Environment-Variablen (Instance-Level)

### Dateisystem & Console

- [x] Datei-Browser (Verzeichnislisting)
- [x] Datei lesen / schreiben
- [x] Datei löschen / umbenennen
- [x] Verzeichnis erstellen
- [x] Compress / Decompress
- [x] Echtzeit-Konsole (WebSocket-Credentials-Delegation)

### Backups

- [x] Backup erstellen / wiederherstellen / löschen
- [x] S3-Backend und lokaler Storage

### Datenbank-Provisioning

- [x] Database Provider-Verwaltung (Admin)
- [x] Datenbank per Instance erstellen / löschen
- [x] Passwort-Rotation

### Blueprints (Templates)

- [x] Blueprint CRUD (Admin)
- [x] Docker-Image, Startup-Command, Install-Script
- [x] Variable-Definitionen (env_var, default_value, user_viewable, user_editable)
- [x] Variable-Übertragung beim Instance-Erstellen

### Collaborators

- [x] Collaborator hinzufügen / bearbeiten / entfernen (Owner-Only)
- [x] Permission-Modell: control.*, file.*, backup.*, database.*, file.sftp
- [x] Suspension blockiert Collaborator-Zugriff

### Agent / Fleet

- [x] Agent-Registrierung und Verwaltung
- [x] Endpoint-Verwaltung (IP:Port-Allokation)
- [x] Agent Health-States (healthy / stale / degraded / unreachable)
- [x] Fleet Monitoring / Capacity Dashboard
- [x] Agent Maintenance Mode (Schutz vor neuen Deployments)
- [x] Agent Last-Seen-Tracking

### Routinen / Automation

- [x] Routine CRUD mit Cron-Expression
- [x] Action CRUD (Befehle pro Routine)
- [x] Manuelle Routine-Ausführung

### Webhooks & Events

- [x] Webhook-Verwaltung (Create, Update, Delete, Test)
- [x] Vollständiger Event-Katalog (30+ Events)
- [x] Webhook-Dispatch via Job-Queue
- [x] Activity-Log / Audit-Trail pro Instance

### Background Jobs

- [x] Job-Infrastruktur (SyncQueue / ThreadQueue / RedisQueue)
- [x] Job-Dashboard (Admin)
- [x] Asynchrone Webhook-Dispatch
- [x] Asynchrone Routine-Ausführung

### System / Operations

- [x] Zentralisiertes Versions-Management
- [x] Preflight-Checks vor Upgrades
- [x] Upgrade-Status-Tracking
- [x] Admin-Systemseite (Version, Upgrade-Status)
- [x] Detaillierte Health-Endpunkte (/health, /health/detailed)

### Dokumentation

- [x] Upgrade-Guide mit Rollback-Anleitung
- [x] Fleet-Monitoring-Guide
- [x] Agent-Maintenance-Guide
- [x] SSH-/SFTP-Auth-Guide
- [x] Background-Jobs-Guide
- [x] Operations-Guide
- [x] UI-Conventions-Guide
- [x] Known Limitations (akzeptierte Einschränkungen)
- [x] Release-Candidate-Checkliste
- [x] Manuelle Abnahmedokumentation
- [x] Reference Gap Analysis (dieses Dokument)

---

## Bewusst NICHT in v1.0

Diese Features sind **gewollt nicht Teil von v1.0**. Sie werden entweder nach dem Pilot bewertet oder kommen in einer späteren Version.

### Plugin-System

**Begründung:** Ein vollständiges Plugin-Ökosystem (Discovery, Versioning, Einstellungsformulare, Provider-Registration) ist ein substanzielles Vorhaben. Für den Pilotbetrieb ist ein monolithisches System wartbarer und sicherer. Plugin-Unterstützung wird nach ausreichend stabilem Betrieb evaluiert.

### OAuth / SSO

**Begründung:** Für den Pilotbetrieb nicht nötig. Kann nach v1.0 ergänzt werden, wenn Kunden SSO-Integration (LDAP, SAML, OAuth2) benötigen.

### Blueprint-Vererbung (Template-Hierarchie)

**Begründung:** Niche-Feature für sehr komplexe Template-Strukturen. Einfache Blueprints decken die Mehrheit der Anwendungsfälle ab.

### Mount System (Shared Volumes)

**Begründung:** Shared Storage zwischen Instances ist ein Spezial-Feature, das zusätzliche Agent-Infrastruktur voraussetzt. Kein bekannter Bedarf für den Pilotbetrieb.

### Multi-Language / i18n

**Begründung:** Pilotbetrieb läuft in kontrolliertem Umfeld. Internationalisierung wird bei Bedarf nach v1.0 ergänzt.

### Blueprint Import/Export-Format

**Begründung:** Blueprints können über die API verwaltet werden. Ein portables JSON-Format (vergleichbar mit Pterodactyl PLCN_v3) ist sinnvoll, aber kein Blocker für den ersten Betrieb.

### Mehrere Docker-Images pro Blueprint

**Begründung:** Ein Docker-Image pro Blueprint deckt die Standardfälle ab. Mehrere Images sind ein Advanced-Feature für spezielle Deployment-Szenarien.

### API-Key Permission-Scoping

**Begründung:** Alle API Keys haben derzeit vollen Zugriff (im Kontext des Benutzers). Granulares Scoping (Key darf nur bestimmte Operationen) ist eine Sicherheitsverbesserung, aber kein Blocker.

### Prometheus / Grafana / APM-Integration

**Begründung:** Observability wird über externe Systeme gelöst. Astra liefert Health-Endpunkte; die Integration in Monitoring-Stack ist operativer Konfigurationsaufwand, kein Astra-Feature.

### File Upload via HTTP Multipart

**Begründung:** Direktes HTTP-File-Upload fehlt; Workaround via Write-Endpoint (Base64 oder Text) existiert. File-Upload ist ein Ergonomie-Feature, kein Kern-Blocker.

---

## Akzeptierte Known Limitations für v1.0

Diese Einschränkungen sind bekannt, dokumentiert und für v1.0 akzeptiert:

| Einschränkung | Akzeptiert weil |
|---|---|
| Stub-Adapter als Dev-Default | Wings-Adapter für Produktion vorhanden |
| SyncQueue als Dev-Default | RedisQueue für Produktion konfigurierbar |
| SQLite in Dev/Test | PostgreSQL für Produktion empfohlen |
| Rate Limiting In-Memory | Ausreichend für Single-Instance |
| Kein automatisches Agent-Drain bei Maintenance | Manuelle Prozedur dokumentiert |
| MFA ohne Recovery-Code-Flow | Fallback via Admin-Reset möglich |
| Fleet Monitoring DB-basiert, kein Live-Stream | Ausreichend für Betrieb; Prometheus optional |
| Kein Kubernetes-Manifest | Docker/Compose ist vorbereitet |
| Responsive Design nicht Mobile-optimiert | Primär Desktop-Tool |

---

## Roadmap nach v1.0

Priorität nach Nutzernutzen und Implementierungsaufwand:

### Kurzfristig (1–2 Monate nach v1.0)

1. **Blueprint Import/Export** (JSON-Format ähnlich PLCN_v3) — hoher Nutzen, überschaubarer Aufwand
2. **File Upload via HTTP Multipart** — Ergonomie
3. **API-Key Permission-Scoping** — Sicherheitsverbesserung

### Mittelfristig (3–6 Monate nach v1.0)

4. **OAuth / SSO-Integration** (LDAP, SAML, OAuth2) — relevant für Enterprise-Kunden
5. **Mehrere Docker-Images pro Blueprint** — Flexibilität für Advanced-Templates
6. **Backup Ignore-Patterns** — Konfigurierbarkeit
7. **MFA Recovery-Codes-Flow** — Sicherheitsnetz für Nutzer

### Langfristig / Nach Evaluation

8. **Plugin-System** — nur nach stabiler Betriebsbasis und klarem Bedarf
9. **Mount System** — nur bei konkreten Shared-Storage-Anforderungen
10. **Multi-Language / i18n** — bei internationalem Rollout
11. **Kubernetes-Manifeste** — bei Bedarf nach Skalierung

---

## Pilot-/v1.0-Empfehlung

### Bewertung

**Astra ist bereit für Pilotbetrieb und v1.0-Release.**

**Begründung:**

1. **Keine P0-Lücken**: Alle Kernfunktionen sind implementiert und getestet (M10–M30).
2. **Übertrifft Reference in mehreren Bereichen**: Fleet Monitoring, Maintenance Mode, Job-Dashboard, Upgrade-Framework, SFTP-Auth-Sicherheit.
3. **Bekannte Lücken sind nicht betriebsblockierend**: Plugin-System, OAuth, Blueprint-Import/Export blockieren keinen Pilotbetrieb.
4. **Dokumentation ist vollständig**: Upgrade-Guide, Operations-Guide, SSH-Auth-Doku, Known Limitations, manuelle Abnahmedoku.
5. **Test-Coverage**: Milestone-Tests M10–M30, Security-Tests, Regression-Tests.

### Voraussetzungen für Produktion

Vor dem ersten Produktionseinsatz sicherstellen:
- [ ] Wings-Adapter mit echter Wings-Instanz getestet
- [ ] Redis für Job-Queue konfiguriert
- [ ] PostgreSQL als Datenbank konfiguriert
- [ ] Reverse Proxy mit SSL/TLS konfiguriert
- [ ] Deployment via Docker Compose verifiziert
- [ ] Manuelle Abnahme-Checkliste durchgeführt (`docs/manual-acceptance.md`)
- [ ] RC-Checkliste abgearbeitet (`docs/release-candidate-checklist.md`)

### Empfehlung

> **Astra v1.0 ist freigabereif für Pilotbetrieb mit dokumentierten Einschränkungen.**
> Die P1-Features (Blueprint-Export, OAuth, API-Scoping) sollten im ersten Quartal nach dem Pilot evaluiert und priorisiert werden.
> Das Plugin-System ist bewusst auf «nach stabile Produktion» verschoben.
