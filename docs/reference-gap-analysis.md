# Reference Gap Analysis: Reference-Projekt vs. Astra

> Erstellt als Teil von M31 – Final Gap Check (Stand: 2026-03-16, Astra v0.30.0)

---

## 1. Terminologie-Mapping

Bevor ein Feature als «fehlend» bewertet wird, müssen die unterschiedlichen Begriffe bekannt sein. Astra verwendet bewusst modernere, neutralere Bezeichnungen.

| Reference-Projekt | Astra | Bemerkung |
|---|---|---|
| **Server** | **Instance** | Neutralerer Begriff, nicht provider-spezifisch |
| **Node** | **Agent** | Klarere Semantik: ein Agent führt etwas aus |
| **Allocation** | **Endpoint** | Beschreibt den Zweck (IP:Port für Verbindung) besser |
| **Egg** | **Blueprint** | Beschreibt Wiederverwendbarkeit, nicht Herkunft |
| **Subuser** | **Collaborator** | Beschreibt die Zusammenarbeit, nicht Unterordnung |
| **Schedule / Task** | **Routine / Action** | Aktiver, weniger technisch |
| **Wings** | **Agent / Runner** | Astra trennt zwischen Agent (Registrierung) und Runner (Protokoll) |

Fehlschlüsse wie «Kein Egg-System» oder «Keine Schedules» sind auf diese Umbenennungen zurückzuführen, **nicht** auf fehlende Features.

---

## 2. Vergleichsmatrix nach Domänen

### 2a. User & Access

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| User-Verwaltung (CRUD) | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Admin-Flag / Root-Zugriff | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Rollen (RBAC) | ✓ Role-Model | – | **Bewusst anders** | Astra nutzt `is_admin`-Flag + Collaborator-Permissions; kein separates Role-Modell nötig |
| API Keys | ✓ | ✓ (M19) | **Teilweise** | Astra hat API Keys; Reference hat zusätzlich Permission-Scoping pro Key |
| MFA / 2FA | ✓ (via Extension) | ✓ TOTP (M19) | **Vorhanden** | Astra hat natives TOTP, Reference via Extension |
| Session-Management | ✓ | ✓ (M19) | **Vorhanden** | Beide: JWT-basiert |
| SSH Key Management | ✓ | ✓ (M28) | **Vorhanden** | Voll gleichwertig |
| SFTP-/SSH-Key-Auth | ✓ (SftpAuthController) | ✓ (M30) | **Vorhanden** | Voll gleichwertig |
| Collaborators / Subusers | ✓ | ✓ (M14) | **Vorhanden** | Gleichwertig; Astra hat `file.sftp`-Permission (moderner) |
| OAuth / External Auth | ✓ OAuthController | – | **Fehlt** | Kein OAuth-Login in Astra |
| Multi-Language (i18n) | ✓ 30+ Sprachen | – | **Nicht im Scope** | Bewusst nicht implementiert; Pilotbetrieb Deutsch/Englisch |

---

### 2b. Workload / Instance Management

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| Instance Create/Delete | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Power Actions (Start/Stop/Restart/Kill) | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| Console (WebSocket) | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| Resource-Limits (CPU/Memory/Disk/IO/Swap) | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Reinstall | ✓ | ✓ (M16) | **Vorhanden** | Voll gleichwertig |
| Config Rebuild / Sync | ✓ | ✓ (M16) | **Vorhanden** | Voll gleichwertig |
| Instance Transfer (Node zu Node) | ✓ ServerTransfer | ✓ transferInstance() | **Vorhanden** | Voll gleichwertig |
| Suspension / Unsuspend | ✓ | ✓ (M29) | **Vorhanden** | Astra hat detailliertere Metadaten (Grund, Timestamp, Admin-ID) |
| Startup-Command-Anpassung | ✓ | ✓ (via Variables) | **Vorhanden** | Gleichwertig |
| Container-Status-Tracking | ✓ | ✓ (M15) | **Vorhanden** | Gleichwertig |
| Server Variables (Env-Vars) | ✓ | ✓ (M16) | **Vorhanden** | Gleichwertig |
| Resource Utilization (Live) | ✓ | ✓ (via Runner) | **Vorhanden** | Gleichwertig |

---

### 2c. Files / Backups / Databases

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| File Browser | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| File Read/Write/Delete | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| Directory Create / Rename | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| Compress / Decompress | ✓ | ✓ (M12) | **Vorhanden** | Voll gleichwertig |
| File Upload | ✓ FileUploadController | – | **Offen** | Direktes HTTP-File-Upload fehlt; Workaround via write-Endpoint |
| Backups (Create/Restore/Delete) | ✓ | ✓ (M13) | **Vorhanden** | Voll gleichwertig |
| Backup Storage (S3/lokal) | ✓ | ✓ (M13) | **Vorhanden** | Gleichwertig |
| Backup Ignore-Patterns | ✓ | – | **Offen** | Kein konfiguriertes Ignore-Pattern für Backups |
| Database Hosts / Provider | ✓ DatabaseHost | ✓ DatabaseProvider (M18) | **Vorhanden** | Voll gleichwertig |
| Database Create/Delete | ✓ | ✓ (M18) | **Vorhanden** | Voll gleichwertig |
| Password Rotation | ✓ | ✓ (M18) | **Vorhanden** | Voll gleichwertig |

---

### 2d. Fleet / Infrastructure

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| Node/Agent Registration | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Allocation/Endpoint Management | ✓ | ✓ | **Vorhanden** | Voll gleichwertig |
| Node Health / Agent Health | ✓ (basic) | ✓ (M20/M22) | **Übertroffen** | Astra hat detailliertere Health-States (healthy/stale/degraded/unreachable) |
| Fleet Monitoring / Capacity | – | ✓ (M22) | **Astra-Mehrwert** | Astra hat Capacity-Tracking, Overallocation-Support |
| Agent Maintenance Mode | – | ✓ (M25) | **Astra-Mehrwert** | Reference hat kein explizites Maintenance-Konzept |
| Node Configuration Export | ✓ | – | **Teilweise** | Kein exportierbares Node-Konfig-Format; wird über API verwaltet |
| Mount System (Shared Storage) | ✓ Mount-Model | – | **Fehlt** | Kein Shared-Volume-Konzept in Astra |

---

### 2e. Automation / Operations

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| Schedules / Routines | ✓ Schedule+Task | ✓ Routine+Action (M17) | **Vorhanden** | Funktional gleichwertig; Astra hat sauberere Struktur |
| Cron-Scheduling | ✓ | ✓ (M17) | **Vorhanden** | Gleichwertig |
| Task Chaining | ✓ | ✓ Actions (M17) | **Vorhanden** | Gleichwertig |
| Background Jobs / Queue | ✓ Laravel Queue | ✓ (M23) | **Vorhanden** | Astra hat explizites Job-Visibility-Dashboard (Mehrwert) |
| Webhooks (Event-Dispatch) | ✓ | ✓ (M10) | **Vorhanden** | Voll gleichwertig |
| Webhook-Katalog | ✓ | ✓ (M10+) | **Vorhanden** | Voll gleichwertig |
| Activity / Audit Log | ✓ ActivityLog | ✓ (M10) | **Vorhanden** | Voll gleichwertig |
| System Version Tracking | – | ✓ (M24) | **Astra-Mehrwert** | Reference: nur App-Version; Astra: strukturiertes Upgrade-Framework |
| Preflight Checks | – | ✓ (M24) | **Astra-Mehrwert** | Reference hat kein equivalentes Konzept |
| Upgrade / Rollback Doku | – | ✓ (M24) | **Astra-Mehrwert** | Strukturiertes Upgrade-Management |

---

### 2f. Templates (Blueprint / Egg)

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| Template CRUD | ✓ Egg | ✓ Blueprint | **Vorhanden** | Voll gleichwertig |
| Docker Image | ✓ (mehrere pro Egg) | ✓ (ein pro Blueprint) | **Teilweise** | Reference unterstützt mehrere Docker-Images pro Egg |
| Startup Command Template | ✓ | ✓ | **Vorhanden** | Gleichwertig |
| Install Script | ✓ | ✓ | **Vorhanden** | Gleichwertig |
| Variables / Env-Vars | ✓ EggVariable | ✓ (JSON-Array) | **Vorhanden** | Gleichwertig; Reference hat separates EggVariable-Modell |
| Template Inheritance | ✓ config_from, copy_script_from | – | **Fehlt** | Kein Blueprint-Parent-Konzept in Astra |
| File Denylist | ✓ | – | **Fehlt** | Kein Denylist-Konzept für Dateien pro Blueprint |
| Tags / Kategorisierung | ✓ | – | **Offen** | Kein Tagging für Blueprints |
| Import/Export Format | ✓ PLCN_v3 (JSON) | – | **Fehlt** | Kein standardisiertes Import/Export-Format |
| Auto-Update URL | ✓ update_url | – | **Nicht im Scope** | Kein Auto-Update-Konzept für Blueprints |

---

### 2g. Extensibility

| Feature | Reference | Astra | Status | Bewertung |
|---|---|---|---|---|
| Plugin System | ✓ Vollständiges Ökosystem | – | **Bewusst nicht in v1.0** | Kein Plugin-Loader, -Discovery oder -Lifecycle |
| Plugin-Einstellungsformulare | ✓ | – | **Bewusst nicht in v1.0** | Folgt Plugin-System |
| Avatar-Service (Gravatar etc.) | ✓ (Extension) | – | **Nicht im Scope** | Nicht relevant für Pilotbetrieb |
| Captcha-Integration | ✓ (Extension) | – | **Nicht im Scope** | Nicht relevant für Pilotbetrieb |
| OAuth / External Auth | ✓ | – | **P1** | Sinnvoll nach v1.0 für SSO-Integrationen |
| S3-Abstraktionsschicht | ✓ (Extension) | Teilweise (Backups) | **Teilweise** | S3 für Backups vorhanden; kein generalisiertes Storage-Backend |

---

## 3. Technische Gleichwertigkeit – Bewertung

### Übertroffen / Moderner in Astra

| Bereich | Warum Astra moderner |
|---|---|
| **Fleet Monitoring** | Dediziertes Capacity-Dashboard, Overallocation-Support, Health-State-Machine |
| **Agent Maintenance Mode** | Explizites Maintenance-Konzept mit Guard gegen neue Deployments |
| **Job Visibility** | Strukturiertes Job-Dashboard; Reference: Queue ist «invisible» |
| **Upgrade-Framework** | Preflight-Checks, Migrations-Validierung, Rollback-Guide |
| **Suspension** | Detaillierte Metadaten (Grund, Timestamp, auslösender Admin), zentrale Guards |
| **SFTP Auth** | Server-seitig berechnete Fingerprints; kein blindes Agent-Vertrauen |
| **Type Safety** | TypeScript Frontend; Reference: JavaScript/Vue ohne strenge Typen |

### Funktional Gleichwertig (anderer Name)

| Reference | Astra | Kommentar |
|---|---|---|
| Schedules + Tasks | Routines + Actions | Gleiche fachliche Semantik |
| Nodes + Allocations | Agents + Endpoints | Gleiche fachliche Semantik |
| Eggs | Blueprints | Gleiche fachliche Semantik |
| Subusers | Collaborators | Gleiche fachliche Semantik |

### Funktional Schwächer / Eingeschränkt

| Feature | Einschränkung |
|---|---|
| Blueprint (nur ein Docker-Image) | Reference: mehrere Images pro Egg wählbar |
| API-Key-Scoping | Reference: Permission-Scoping pro Key; Astra: Keys ohne Scope |
| Backup-Ignore-Patterns | Reference: konfigurierbar; Astra: nicht vorhanden |
| File Upload (HTTP) | Reference: direktes Upload; Astra: nur via Write-Endpoint |

---

## 4. Echte Lücken – Priorisiert

### P0 – Muss vor v1.0 geschlossen werden

**Keine P0-Lücken identifiziert.**

Alle kritischen Kernfunktionen sind implementiert:
- User-, Instance-, Agent-, Blueprint-, Endpoint-Management ✓
- Power, Files, Backups, Databases, Console ✓
- Auth, API Keys, MFA, SSH Keys, SFTP ✓
- Suspension, Collaborators, Webhooks, Activity ✓
- Jobs, Fleet Monitoring, Maintenance ✓

---

### P1 – Sollte kurz nach v1.0 kommen

| Gap | Begründung |
|---|---|
| **Blueprint Import/Export (JSON)** | Ermöglicht Wiederverwendung und Sharing von Templates; blockiert aber keinen Betrieb |
| **API-Key Permission-Scoping** | Sicherheitsverbesserung für Produktionssysteme mit vielen Nutzern |
| **OAuth / SSO** | Wichtig für Enterprise-Deployments; nicht nötig für Pilotbetrieb |
| **File Upload via HTTP** | Ergonomie; Workaround via Write-Endpoint existiert |
| **Blueprint: mehrere Docker-Images** | Flexibilität für komplexe Templates |

---

### P2 – Optional / Bewusst später

| Gap | Begründung |
|---|---|
| **Plugin-System** | Grosses Vorhaben; für v1.0 nicht nötig; monolithisch ist wartbarer |
| **Blueprint-Inheritance** | Niche-Feature; wird von wenigen gebraucht |
| **Mount System (Shared Volumes)** | Spezial-Feature; nicht im Kernbetrieb nötig |
| **Multi-Language / i18n** | Für Pilotbetrieb nicht relevant |
| **Backup Ignore-Patterns** | Nice-to-have; manuell steuerbar |
| **Captcha / Avatar-Dienste** | Kosmetik; kein Betriebsbedarf |
| **Prometheus/Grafana-Integration** | Sinnvoll für Monitoring-Infrastruktur, aber separat integrierbar |
| **Blueprint Auto-Update-URL** | Kein klarer Bedarf für v1.0 |

---

## 5. Bewusste Astra-Abweichungen (kein Defizit)

Diese Unterschiede sind **gewollte Design-Entscheidungen**, keine Versäumnisse:

1. **Kein Plugin-System in v1.0**: Bewusste Entscheidung für Wartbarkeit und Sicherheit. Ein monolithisches System ist für den Pilotbetrieb robuster.

2. **Python / Flask statt PHP / Laravel**: Moderne, team-interne Präferenz; bessere Testbarkeit; keine Legacy-Abhängigkeiten.

3. **Fleet Monitoring als Kernfunktion**: Reference hat nur basic Health-Checks; Astra hat Capacity-Dashboard und Maintenance-Mode – bewusst über das Reference hinausgegangen.

4. **Strukturiertes Upgrade-Framework**: Reference hat kein equivalentes Konzept; Astra hat Preflight-Checks und Rollback-Guide – bewusste Investition in Betriebsreife.

5. **TypeScript Frontend**: Reference-Projekt hat JavaScript/Vue; Astra hat React/TypeScript – bessere Typsicherheit, bessere IDE-Unterstützung.

6. **Separate «Runner»-Abstraktionsschicht**: Astra trennt zwischen Agent-Registrierung und Runner-Protokoll; erlaubt Stub-Testing ohne echten Daemon.

7. **Zentralisiertes Job-Dashboard**: Reference-Jobs sind unsichtbar; Astra hat explizites Job-Tracking (M23).

8. **Serverseitige SFTP-Fingerprint-Berechnung**: Reference-Implementierung vertraut Agent-Input; Astra berechnet FP serverseitig (sicherer).
