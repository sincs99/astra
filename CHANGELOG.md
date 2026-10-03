# Changelog

Alle relevanten Aenderungen an Astra werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Security (M35 – Admin-Guard)
- Der gesamte `/api/admin`-Blueprint verlangt jetzt einen angemeldeten Admin (`before_request`, JWT, API-Key oder in Dev/Test `X-User-Id`). Ausnahme: `GET /api/admin/health`. Ohne Login 401, ohne Admin-Recht 403
- Schalter `ADMIN_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus, damit die Legacy-Tests M10–M32 ohne Auth weiterlaufen
- `backend/test_m35.py` (20 Tests, prueft u.a. jede registrierte Admin-Route per Routentabelle)

### Security (M36 – Agent-Guard)
- `/api/agent/*` verlangt jetzt den Node-Token (`Authorization: Bearer {token_id}.{token}`, gleiche Pruefung wie `/api/remote`). Ausnahme: `GET /api/agent/health`
- Ein Agent darf nur Instanzen seines eigenen Nodes melden (`install`, `container/status` -> 403, `sftp-auth` -> `allowed: false, reason: instance_not_on_node`)
- Schalter `AGENT_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus
- `backend/test_m36.py` (17 Tests)

### Added (M37 – Egg-Import)
- `backend/app/domain/blueprints/egg_import.py`: `convert_egg()` wandelt Pterodactyl-Eggs (PTDL_v1/v2) und Pelican-Eggs (PLCN_v1..v3) in Blueprint-Felder um (JSON-String-Configs, `docker_images`, `startup_commands`, `env_variable` -> `env_var`, `^C` -> `^SIGINT`); Platzhalter bleiben unveraendert
- `POST /api/admin/blueprints/import` – Egg oder natives Blueprint-JSON (`"format": "astra"`) -> 201 mit Blueprint, 400 bei ungueltigen Daten
- CLI: `python cli.py import-blueprint <datei.json|yaml>`
- `blueprints/minecraft-paper.json` – reduziertes Beispiel-Egg (Paper, Java 21). Die Minecraft-EULA wird nicht automatisch akzeptiert
- `backend/test_m37.py` (35 Tests)

### Added (Self-Service Teil 1)
- `POST /api/auth/register` – Selbstregistrierung, standardmaessig AUS (`REGISTRATION_ENABLED=true` zum Aktivieren), neue Nutzer sind nie Admin
- `POST /api/auth/password-reset/request` und `/confirm` – Reset per signiertem, zeitlich begrenztem Einmal-Link (`PASSWORD_RESET_TTL_MINUTES`, Standard 60), antwortet unabhaengig von der Adresse gleich
- `backend/app/infrastructure/mail.py` – SMTP-Versand (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`), ohne `MAIL_SERVER` nur Logging
- `FRONTEND_URL` fuer den Link in der Reset-Mail
- Neue Auth-Pfade unterliegen dem Rate Limiting
- `backend/test_m34.py` (18 Tests)
- Noch offen: E-Mail-Verifizierung bei Registrierung, Frontend-Seiten (Registrieren, Passwort vergessen)

### Changed
- Rate Limiting fuer `/api/auth/login` nutzt jetzt Redis (geteilter Zaehler ueber alle Gunicorn-Worker), mit In-Memory-Fallback wenn Redis nicht erreichbar ist (`backend/app/infrastructure/ratelimit.py`)
- `redis` zu `backend/requirements.txt` hinzugefuegt

### Added (Frontend)
- `PageLayout`: SPA-Navigation per `react-router` (kein Seiten-Reload), `aria-current`, Abmelden-Button
- `FileBrowser`: Upload von Textdateien (max. 1 MB, Workaround ueber Write-Endpoint) und "Neue Datei"
- Auto-Refresh (15s, abschaltbar, nur bei sichtbarem Tab) fuer Jobs-Dashboard, Fleet Monitoring, Dashboard und Admin-Instances (`hooks/useAutoRefresh.ts`, `AutoRefreshToggle`)
- 401-Handling: abgelaufene Sitzung leitet zu `/login?expired=1` mit Hinweis um
- `ErrorBoundary` gegen weisse Seite bei Render-Fehlern, `NotFoundPage` als Catch-all-Route
- Navigation: Link-Leiste scrollt separat, Abmelden-Button bleibt auf schmalen Screens sichtbar; Login leitet eingeloggte Nutzer zum Dashboard
- `LoginPage`: gemeinsame UI-Styles, Label-Verknuepfung, `autocomplete`, `role="alert"`

### Changed (Frontend)
- Responsive Layout: dynamisches Padding, horizontal scrollbare Tabellen, `FileBrowser`-Grid bricht auf schmalen Screens um

## [0.33.0-rc] - 2026-10-03

### Added (M33 – Wings Remote-API)
- `backend/app/api/remote/` – Remote-API unter `/api/remote`, die ein unveraenderter Wings-Daemon
  (Pterodactyl/Pelican) am Panel aufruft. Pfade und Formate wie `routes/api-remote.php` im Referenz-Panel:
  - `GET /servers` (paginiert, Wings-Boot), `POST /servers/reset`
  - `GET /servers/{uuid}` (settings + process_configuration), `GET/POST /servers/{uuid}/install`
  - `POST /servers/{uuid}/container/status`, `GET|POST /servers/{uuid}/transfer/success|failure`
  - `POST /sftp/auth` (Passwort und Public Key, Wings-Permission-Mapping)
  - `POST /activity` (Wings-Events werden als ActivityLog mit subject_type=instance gespeichert)
  - `GET|POST /backups/{uuid}`, `POST /backups/{uuid}/restore`
- Node-Token-Authentifizierung (`Authorization: Bearer {token_id}.{token}`), konstante Zeitvergleiche,
  jeder Request aktualisiert `last_seen_at` des Agents
- Agent-Credentials werden beim Anlegen automatisch erzeugt; `POST /api/admin/agents/{id}/rotate-credentials`
- `GET /api/admin/agents/{id}/configuration` – Wings `config.yml` (YAML + JSON) pro Agent
- `PATCH /api/admin/agents/{id}` – Wings-Verbindungsfelder pflegen (scheme, behind_proxy, Ports, daemon_base, upload_size)
- Agent-Felder: `uuid`, `behind_proxy`, `daemon_sftp`, `daemon_base`, `upload_size`
- Blueprint-Felder fuer die Wings-Prozesskonfiguration: `install_container`, `install_entrypoint`,
  `config_startup`, `config_stop`, `config_files`, `file_denylist`
- `config_builder.py`: `egg`-Block in den settings, `build_process_configuration()`,
  `build_install_payload()`, Platzhalter-Ersetzung (`{{server.*}}`, `{{env.*}}`) fuer Config-Dateien
- Frontend: Agents-Seite zeigt Token-ID, config.yml-Dialog und Credential-Rotation; Blueprint-Formular
  mit Install-Container, Stop-Befehl, Startup-Erkennung und Datei-Denylist
- Migration `l2g3h4i5j6k7_milestone33_wings_remote_api`
- `docs/wings-remote-api.md` – Endpunkte, Auth, Node-Einrichtung, Fehlersuche
- Testsuite `backend/test_m33.py`

### Changed
- Backups/Restore: Wings antwortet asynchron (202). Ein Backup gilt erst nach dem Remote-Callback als
  erfolgreich; der Stub meldet weiterhin synchron (`completed: true`)
- Websocket-Token enthaelt `user_uuid` (User-ID als String) fuer Wings-Activity-Events; `iss` faellt auf `BASE_URL` zurueck
- `backend/app/version.py`: VERSION auf `0.33.0-rc`
- `requirements.txt`: PyYAML fuer den config.yml-Export

### Fixed
- `backend/test_m30.py` rief `/agent/sftp-auth` statt `/api/agent/sftp-auth` auf (Testsuite brach ab)

### Notes
- M33 schliesst die groesste Luecke fuer den Pilotbetrieb: Ohne Remote-API konnte Wings keinen Server booten
- Bewusst nicht enthalten: S3-Presigned-Uploads, Mounts, Rate-Limit auf `/sftp/auth`


## [0.32.0-rc] - 2026-03-16

### Added (M32 – Pilotbetrieb & v1.0-Rollout)
- `docs/pilot-rollout-plan.md` – vollständiger Pilot-Rollout-Plan:
  - Pilotziel, Pilotumfang (was aktiv / was nicht)
  - Beteiligte Rollen (Pilot-Admin, Nutzer, Reviewer, Dev-Bereitschaft)
  - Pilotumgebung mit Infrastruktur-Diagramm und Mindest-Sizing
  - Go/No-Go-Checkliste vor Pilotstart (Infrastruktur, Backend, Agent, Readiness)
  - 12 verbindliche Pilot-Kernflows mit Akzeptanzkriterien
  - Pilot-Protokoll-Vorlage für Funde (Blocker/Major/Minor/Nice-to-have)
  - Feedback-Priorisierungsmatrix und Release-Konsequenzen
  - Rollback-Anleitung für den Pilot
  - Scope-Freeze-Definition (erlaubt / nicht erlaubt bis v1.0)
- `docs/release-plan.md` – Versions-Roadmap und Go-Live-Kriterien:
  - Versions-Roadmap: v0.32.0-rc → Pilot-Build → v1.0.0
  - Scope-Freeze: nur Bugfixes / Security Fixes / Ops-Fixes vor v1.0
  - Vollständige Go-Live-Kriterien (Pilot-Abschluss, Qualität, Upgrade/Recovery, Doku)
  - Rollback- und Recovery-Anleitung (fehlgeschlagenes Release, fehlgeschlagene Migration)
  - Release-Notes-Template für v1.0.0
  - SemVer-Strategie und Build-Metadaten
  - Post-v1.0-Roadmap (P1/P2-Features)

### Changed
- `backend/app/version.py`: VERSION aktualisiert auf `0.32.0-rc`, neues `RELEASE_PHASE`-Feld (`pilot`)
- `backend/app/__init__.py`: `/ops/info` Endpunkt gibt nun `release_phase` zurück
- `backend/app/version.py`: `get_version_info()` enthält `release_phase`
- `frontend/src/services/api.ts`: `SystemVersionInfo`-Interface um `release_phase` erweitert
- `frontend/src/pages/AdminSystemPage.tsx`: Release-Phase wird in der System-Info-Seite angezeigt

### Notes
- M32 ist primär ein Dokumentations- und Planungs-Meilenstein
- Minimale Code-Ergänzungen: Versionsanhebung und `release_phase`-Feld für operative Klarheit
- Scope ist ab jetzt eingefroren; nur Bugfixes bis v1.0.0 erlaubt
- Aktuelle Version wird als `v0.32.0-rc` getaggt vor Pilotbeginn

## [0.31.0] - 2026-03-16

### Added (M31 – Final Gap Check gegen Reference-Projekt)
- `docs/reference-gap-analysis.md` – vollständige Vergleichsmatrix Reference vs. Astra in 7 Domänen (User & Access, Workload, Files/Backups/Databases, Fleet/Infra, Automation, Templates, Extensibility)
- `docs/v1-scope.md` – verbindliches Scope-Dokument: Was ist v1.0, was bewusst nicht, Known Limitations, Roadmap, Pilot-Empfehlung
- Terminologie-Mapping dokumentiert (Node→Agent, Allocation→Endpoint, Egg→Blueprint, Schedule→Routine, Subuser→Collaborator, Server→Instance)
- Technische Gleichwertigkeitsbewertung (übertroffen / gleichwertig / schwächer) für alle relevanten Bereiche
- Priorisierte Lückenliste (P0/P1/P2) – keine P0-Lücken identifiziert
- Bewusste Astra-Abweichungen dokumentiert (Fleet Monitoring, Maintenance Mode, Job-Dashboard, Upgrade-Framework, TypeScript Frontend)

### Analysis Results (M31)
- **Keine P0-Lücken**: Alle Kernfunktionen sind implementiert
- **P1** (kurz nach v1.0): Blueprint Import/Export, API-Key-Scoping, OAuth/SSO, File-Upload HTTP, Mehrere Docker-Images pro Blueprint
- **P2** (bewusst später): Plugin-System, Blueprint-Vererbung, Mount System, i18n, Prometheus-Integration
- **Empfehlung**: Astra v1.0 ist freigabereif für Pilotbetrieb mit dokumentierten Einschränkungen

## [0.30.0] - 2026-03-16

### Added (M30 – Echte SFTP-/SSH-Key-Authentifizierung)
- Permission `file.sftp` im Collaborator-Permission-Katalog (`permissions.py`) – steuert SFTP-Zugang fuer Collaborators
- `backend/app/domain/ssh_keys/auth_service.py` – zentraler SFTP-Auth-Service:
  - `authorize_ssh_key_access(instance_uuid, username, public_key, fingerprint)` – vollstaendige Auth-Entscheidung
  - `find_key_by_fingerprint(user_id, fingerprint)` / `find_key_by_public_key(user_id, public_key)` – Key-Matching
  - `find_user_key(user_id, public_key, fingerprint)` – kombiniertes Key-Lookup (public_key bevorzugt, FP serverseitig berechnet)
  - Unterscheidung: `ok`, `user_unknown`, `instance_not_found`, `key_unknown`, `permission_denied`, `instance_suspended`, `malformed_request`
- Agent-API-Endpunkt `POST /agent/sftp-auth`:
  - Validiert Request (username, instance_uuid, public_key/fingerprint)
  - Ruft `authorize_ssh_key_access()` auf
  - Antwortet mit `allowed: true/false` und Permissions oder Ablehnungsgrund
  - Gibt keine sensiblen Daten (Key-Klartext, Passwort-Hash) zurueck
- Activity-Events `ssh_key:auth_success` und `ssh_key:auth_failed` (Events-Katalog + Webhook-Katalog)
- Fehler-Events loggen nur Fingerprint (kein Public-Key-Klartext)
- Suspension-Guard aus M29 aktiv in SFTP-Auth (suspendierte Instances werden blockiert)
- Frontend `SshKeysPage.tsx`: Info-Box aktualisiert – Keys werden jetzt fuer SFTP genutzt, Owner/Collaborator-Regeln erklaert
- Dokumentation `docs/ssh-sftp-auth.md`: Key-Typen, Berechtigungsmodell, API-Format, Reason-Codes, Sicherheitshinweise
- Testsuite `backend/test_m30.py` (Key-Matching, Auth-Service alle Deny/Allow-Pfade, Agent-API, Security, Events, Regression M10–M29)

### Notes
- Kein vollstaendiger SSH-Server in Astra – Astra ist rein die Kontrollinstanz fuer Auth-Entscheidungen
- Private Keys werden **nie** gespeichert, verarbeitet oder geloggt
- Fingerprints werden serverseitig berechnet (dem Agent wird kein Fingerprint blind vertraut)
- Owner haben automatisch SFTP-Zugriff; Collaborators benoetigen `file.sftp`

## [0.29.0] - 2026-03-16

### Added (M29 – Suspension / Unsuspend & Administrative Instance Locks)
- `Instance`-Modell um Suspension-Felder erweitert: `suspended_reason` (String 500), `suspended_at` (DateTime), `suspended_by_user_id` (FK users)
- SQLAlchemy-Relationships: `owner` mit `foreign_keys=[owner_id]` und `suspended_by` mit `foreign_keys=[suspended_by_user_id]` (Ambiguity-Fix)
- `to_dict()` gibt `suspended_reason`, `suspended_at`, `suspended_by_user_id` zurueck
- Alembic-Migration `k1f2g3h4i5j6_milestone29_suspension` fuer die drei neuen Spalten
- Service-Funktionen: `suspend_instance()`, `unsuspend_instance()`, `is_instance_suspended()` (idempotent)
- Activity-Events: `instance:suspended`, `instance:unsuspended`
- Webhook-Katalog um Suspension-Events erweitert
- Zentraler Guard `_require_not_suspended()` in `client/routes.py` schuetzt 13+ operative Endpunkte (Power, Reinstall, Build, Variables, Sync, WebSocket, File-Write/-Delete/-Mkdir/-Rename/-Compress/-Decompress, Backup-Create/-Restore/-Delete, DB-Create/-RotatePassword/-Delete, Routine-Execute) mit HTTP 409
- Admin-API: `POST /api/admin/instances/<uuid>/suspend` und `/unsuspend` (require_admin)
- Frontend: TypeScript `Instance`-Interface um `suspended_reason`, `suspended_at`, `suspended_by_user_id` erweitert
- Frontend: `api.suspendInstance(uuid, reason?)` und `api.unsuspendInstance(uuid)` in `api.ts`
- Frontend: Suspend/Unsuspend `ConfirmButton` in `AdminInstancesPage` (status-abhaengig)
- Frontend: Suspension-Banner in `InstanceDetailPage` (orange Warnung mit Grund und Hinweis)
- Vollstaendige Testsuite `backend/test_m29.py` (Service, Admin-API, Access-Blocking 13 Endpunkte, Events, Regression M10–M28)

### Notes
- Suspension ist rein administrativ; der Container-Status (`container_state`) bleibt unveraendert
- Operative Aktionen werden mit 409 blockiert solange `status == "suspended"`

## [0.28.0] - 2026-03-16

### Added (M28 – SSH Keys & SFTP Access Management)
- `UserSshKey`-Domain-Modell mit Feldern `id`, `user_id`, `name`, `fingerprint`, `public_key`, `created_at`, `updated_at`
- Alembic-Migration `j0e1f2g3h4i5_milestone28_ssh_keys` mit Foreign Key auf `users` und Unique Constraint `(user_id, fingerprint)`
- SSH-Public-Key-Validator (`backend/app/domain/ssh_keys/validator.py`): Format-Pruefung und serverseitige SHA256-Fingerprint-Berechnung
  - Unterstuetzte Typen: `ssh-ed25519`, `ssh-rsa`, `ecdsa-sha2-nistp256/384/521`
- SSH-Key-Service mit `list_user_ssh_keys`, `create_user_ssh_key`, `update_user_ssh_key_name`, `delete_user_ssh_key`
- Client-API-Endpunkte: `GET/POST /api/client/account/ssh-keys`, `PATCH/DELETE /api/client/account/ssh-keys/<id>`
- Activity-Events: `ssh_key:created`, `ssh_key:updated`, `ssh_key:deleted`
- Webhook-Katalog um SSH-Key-Events erweitert
- Frontend: `SshKeysPage` mit Key-Liste, Hinzufuegen-Formular und Delete-Bestaetigung
- Frontend: `SshKeyEntry` / `SshKeyCreateRequest` TypeScript-Interfaces und API-Funktionen in `api.ts`
- Route `/account/ssh-keys` im AppRouter, Navigationseintrag "SSH Keys" in PageLayout
- Vollstaendige Testsuite `backend/test_m28.py` (Modell, Validierung, Fingerprint, Service, API, Events, Regression)

### Notes
- SFTP-Key-Authentifizierung (echte schluesselbasierte SSH-Logins) wird in M29 aktiviert
- Fingerprints werden ausschliesslich serverseitig berechnet (OpenSSH SHA256-Format)

## [0.27.0-rc1] - 2026-03-14

### Added
- RC-Checkliste, manuelle Abnahmedoku, Known-Limitations-Doku
- Umfassende Security-/Serialization-/Failure-Tests (test_m27.py)

### Improved
- Fehlerbehandlung bei Runner-/Queue-Ausfall gehaertet
- Security-Checks: Secrets leaken nicht in Responses
- Logging-Konsistenz verbessert

## [0.26.0] - 2026-03-14

### Added
- Zentrale UI-Komponentenbibliothek (StatusBadge, LoadingState, ErrorState, EmptyState, ConfirmButton, Toast, PageLayout)
- Gemeinsame Styles und Konventionen
- PageLayout mit Navigation (Core/Operations/Integrations)
- UI-Konventionen-Dokumentation

### Improved
- DashboardPage komplett auf neue Komponenten migriert
- InstanceDetailPage mit PageLayout und StatusBadge
- Konsistentere Farben und Status-Darstellungen

## [0.25.0] - 2026-03-14

### Added
- Agent Maintenance-Modus (maintenance_mode, maintenance_reason, maintenance_started_at)
- Maintenance-Service (enable/disable, idempotent)
- Deployment-Guard: Maintenance-Agents blockieren neue Instances (409)
- Activity-/Webhook-Events (agent:maintenance_enabled/disabled)
- Admin-API: POST/DELETE/PATCH /api/admin/agents/{id}/maintenance
- Fleet-Monitoring zeigt Maintenance-Status
- Frontend: Maintenance-Toggle in Fleet Monitoring

## [0.24.0] - 2026-03-14

### Added
- Zentrale Versionsquelle (`backend/app/version.py`)
- Build-/Release-Metadaten (SHA, Datum, Ref via Umgebungsvariablen)
- DB-Migrationsstatus-Pruefung (Alembic Head vs. applied)
- Upgrade-Preflight-Check (Config, DB, Migrationen, Redis)
- Ops-Endpunkte: `/ops/version`, `/ops/upgrade-status`, `/ops/preflight`
- Admin-API: `/api/admin/system/version`, `/api/admin/system/upgrade-status`, `/api/admin/system/preflight`
- Frontend: System-Info-Seite (`/admin/system`)
- CLI-Befehle: `version`, `preflight`, `upgrade-status`
- Upgrade-/Rollback-Dokumentation (`docs/upgrade-guide.md`)

## [0.23.0] - 2026-03-14

### Added
- Job-/Queue-Infrastruktur (`backend/app/infrastructure/jobs/`)
- Job-Tracking-Modell (`JobRecord`) mit Status-Verfolgung
- Queue-Backends: SyncQueue (Dev), ThreadQueue, RedisQueue (Prod)
- Webhook-Dispatch ueber Job-Queue (statt ad-hoc Threading)
- Routine-Ausfuehrung non-blocking via Jobs
- Admin-API fuer Jobs: `/api/admin/jobs`, `/api/admin/jobs/summary`
- Frontend: Jobs-Dashboard (`/admin/jobs`)
- Worker-Entrypoint: `python cli.py worker`
- 5 Job-Typen: webhook_dispatch, routine_execute, routine_action, agent_health_check, instance_sync

## [0.22.0] - 2026-03-14

### Added
- Agent Fleet Monitoring mit Kapazitaetsmodell
- Health-Status pro Agent (healthy, stale, degraded, unreachable)
- Kapazitaets-/Auslastungsberechnung (Memory, Disk, CPU)
- Overallocation-Unterstuetzung pro Agent
- Admin-API: `/api/admin/agents/monitoring`, `/api/admin/fleet/summary`
- Frontend: Fleet-Monitoring-Dashboard (`/admin/agents/monitoring`)

## [0.21.0] - 2026-03-14

### Added
- Deployment & Operations Readiness
- Strukturiertes Logging, ProxyFix, Security Headers
- Rate Limiting, Bootstrap-CLI, Ops-Endpunkte

## [0.20.0] - 2026-03-14

### Added
- Agent Health-Tracking (`last_seen_at`, `is_stale()`)
- Production Hardening (Lifecycle, Runtime)

## [0.19.0] - 2026-03-14

### Added
- Auth: JWT, Sessions, API Keys, MFA

## [0.18.0] - 2026-03-14

### Added
- Database Provisioning

## [0.17.0] - 2026-03-14

### Added
- Routines & Actions

## [0.16.0] - 2026-03-14

### Added
- Instance Lifecycle (Reinstall, Build Config, Sync)

## [0.15.0] - 2026-03-14

### Added
- Container State Management

## [0.14.0] - 2026-03-14

### Added
- Collaborators & Permissions

## [0.13.0] - 2026-03-14

### Added
- Backups

## [0.12.0] - 2026-03-14

### Added
- Files & Console

## [0.11.0] - 2026-03-14

### Added
- Wings-Integration

## [0.10.0] - 2026-03-14

### Added
- Webhooks & Activity Logging
