# Changelog

Alle relevanten Aenderungen an Astra werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added (Phase 2 – Produktions-Deployment)
- `POST /api/client/orders/{uuid}/checkout`: 409-Antworten tragen `code` (`manual`, `invalid_status`), `PaymentError.code`
- `docker-compose.prod.yml`: Container `billing` fuehrt `cli.py billing-tick` alle `BILLING_TICK_INTERVAL` Sekunden (Standard 300) aus; `BILLING_GRACE_DAYS` in `.env.prod.example`
- `POST/PATCH /api/admin/agents`: Kapazitaetsfelder `memory_total`, `disk_total`, `cpu_total` und `*_overalloc` pflegbar (Ganzzahl >= 0, 0 = kein Limit)
- `docker-compose.prod.yml`: Caddy als TLS-Terminierung (Let's Encrypt, einziger oeffentlicher Eingang 80/443),
  Worker-Container fuer die Redis-Job-Queue, Healthchecks fuer Backend/Redis, Redis mit Passwort und AOF,
  gemeinsamer Backend-Env-Block (`x-backend-env`), kein direktes Port-Mapping fuer Frontend/Backend mehr
- `deploy/Caddyfile` + `deploy/node.caddy.template`: optionaler Reverse Proxy fuer den Wings-Node auf
  demselben Host (`NODE_DOMAIN` -> `host.docker.internal:8080`, Websockets inklusive)
- `.env.prod.example` im Root (Domains, Secrets, Admin, Mail, Queue), `COMPOSE_FILE` vorbelegt
- `scripts/deploy.sh` (Build, Start, Warten auf Readiness, `--bootstrap`, `--status`),
  `scripts/install-wings.sh` (Docker + Wings + config.yml aus dem Panel + systemd, `--pelican`),
  `scripts/smoke-test.sh` (Health, TLS, Admin-Guard, Remote-API-Auth je Agent)
- `docs/deploy-runbook.md`: Runbook fuer Panel + Wings auf einem Server, Abnahme-Checkliste, Umzug

### Changed
- `frontend/nginx.conf`: `X-Forwarded-Proto` wird vom vorgelagerten Proxy durchgereicht (statt `$scheme`),
  damit das Backend hinter Caddy `https` erkennt; Backend nutzt `PROXY_FIX_X_FOR/X_PROTO=2`
- `cli.py db-init` (neu) ersetzt `flask db upgrade` im Entrypoint: frische Datenbank -> `create_all()` +
  `stamp head`, bestehende Datenbank -> `upgrade`. Die Migrationen legen die Basistabellen nicht selbst an,
  ein `flask db upgrade` auf leerer DB brach bisher mit "relation instances does not exist" ab
- `requirements.txt`: SQLAlchemy auf 2.0.54 gepinnt

### Fixed (gegen echtes PostgreSQL 16 und SQLite verifiziert)
- PostgreSQL-URLs werden auf den psycopg2-Treiber normalisiert (`postgresql://` -> `postgresql+psycopg2://`).
  Mit SQLAlchemy >= 2.1 waere sonst psycopg v3 der Default und der Start schlug mit
  `ModuleNotFoundError: psycopg` fehl
- Migration `k1f2g3h4i5j6` (M29 Suspension) brach auf SQLite im Batch-Modus mit "Constraint must have a name"
  ab; jetzt `ALTER TABLE ADD COLUMN` ohne Neuaufbau (FK-Constraint nur auf PostgreSQL)
- Migration `l2g3h4i5j6k7` (M33) nutzt fuer `agents.uuid` einen Unique-Index statt einer Batch-Constraint
  (gleicher SQLite-Fehler)
- Downgrades von M29/M33/M38 tolerieren jetzt Datenbanken, deren Schema per `db-init`/`create_all()`
  entstand (andere Constraint-Namen als im Migrationspfad). Up-/Downgrade-Roundtrip von Head bis M28 und
  zurueck auf PostgreSQL 16 und SQLite verifiziert, jeweils fuer Migrations- und create_all-Datenbanken

### Security (M35 – Admin-Guard)
- Der gesamte `/api/admin`-Blueprint verlangt jetzt einen angemeldeten Admin (`before_request`, JWT, API-Key oder in Dev/Test `X-User-Id`). Ausnahme: `GET /api/admin/health`. Ohne Login 401, ohne Admin-Recht 403
- Schalter `ADMIN_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus, damit die Legacy-Tests M10–M32 ohne Auth weiterlaufen
- `backend/test_m35.py` (20 Tests, prueft u.a. jede registrierte Admin-Route per Routentabelle)

### Added (M52 – Automatische Bereitstellung wartender Bestellungen)
- Der Billing-Tick stellt bezahlte Bestellungen ohne Instance (`awaiting_provisioning`) automatisch bereit, sobald ein Node Platz hat (aelteste Zahlung zuerst; eine zu grosse Bestellung blockiert kleinere nicht). Erfolgreiche Bereitstellung: Status `active`, Event `order:provisioned`, Mail "Astra: Dein Server ist bereit" mit Verbindungsadresse; erfolglose Versuche sind still (kein Event und keine Mail pro Tick). Tick-Zusammenfassung enthaelt `provisioned`, `checked` zaehlt wartende Bestellungen mit
- **Die Laufzeit beginnt mit der Bereitstellung statt mit der Zahlung** (`fulfill_order(now=...)`): wer auf einen freien Node warten muss, verliert keine Zeit. Zahlungsreferenz und `paid_at` bleiben unveraendert, die Zahlung wird nie doppelt verbucht; die manuelle Bereitstellung per `mark-paid` funktioniert weiter. Gilt auch fuer Stripe-Zahlungen ohne Platz
- `backend/test_m52.py` (36 Tests: kein Spam, Reihenfolge, Teilkapazitaet, Fehlerisolation, Admin und Stripe, Gegenprobe ohne Wiederholung schlaegt fehl); Doku in `docs/orders-api.md` und `docs/known-limitations.md`

### Changed (M51 – Stub-Runner und Monitoring-Lebenszeichen)
- Der **Stub-Runner schliesst die Installation synchron ab**: `create_instance` liefert `data={"completed": True}`, der Service ruft dann den Install-Callback selbst auf (Status ready, `installed_at`, Event `instance:install_completed`). Gilt fuer Erstellung, Reinstall und Transfer (`instance.transfer.completed`). Vorher blieben Instanzen ohne Wings dauerhaft auf `provisioning`, seit M40 die Simulations-Knoepfe weg sind. Nur genau `completed is True` zaehlt; ein Fehler gewinnt immer; der **Wings-Adapter entfernt `completed`** aus Antworten, dort bleibt es beim asynchronen Callback ueber `/api/remote`
- Monitoring: Ein erfolgreicher Erreichbarkeits-Check (`daemon_reachable = true`) gilt als Lebenszeichen und setzt `last_seen_at` (hoechstens einmal pro Minute, nur aktive Agents). Dadurch widersprechen sich `daemon_reachable = true` und Health `unreachable` nicht mehr; Liste, Detail und Fleet-Summary zaehlen gleich. Mit dem Stub sind Agents im Monitoring sofort `healthy`
- **Aenderung fuer Tests/Entwicklung:** Instanzen sind nach Stub-Erstellung sofort ready (ein spaeterer Install-Callback ist idempotent). Tests, die den Zwischenzustand `provisioning`/`reinstalling` pruefen, nutzen einen asynchronen Runner (`test_m16`); Health-Klassifikationstests nutzen nicht erreichbare Daemons (`test_m22`)
- `backend/test_m51.py` (31 Tests), `test_m41.py` (42, Abschnitt "Lebenszeichen"); Doku in `docs/fleet-monitoring.md` und `docs/operations.md`

### Changed (M50 – Umlaute in Kundenmeldungen)
- Meldungen, die Kunden sehen (Auth, Client, Billing und die Services dahinter, inklusive Mails), tragen jetzt echte Umlaute: "Ungültige Anmeldedaten", "Instance gelöscht", "Bitte bezahle per Überweisung", Mailbetreffe wie "Astra: Zahlung überfällig – dein Server wurde gesperrt" (79 Texte in 12 Dateien). **Keine Änderung an Fehlercodes (`code`), Statuswerten oder Ereignisnamen.** Admin-Routen sowie Docstrings, Kommentare und Log-Ausgaben bleiben unverändert
- Neues Werkzeug `backend/tools/umlauts.py` mit festem Wörterbuch ganzer Wörter (Wörter wie "neue", "zuerst", "aktuell", "Blueprint", "queue" bleiben unberührt): `python tools/umlauts.py` zeigt noch vorhandene ASCII-Schreibweisen, `--write` korrigiert sie. Es arbeitet über den Syntaxbaum und fasst nur Meldungstexte an
- Die clientseitige Korrektur im Frontend (`lib/umlauts.ts`) wird dadurch für diese Meldungen zum No-op und kann bleiben
- Mails mit Umlauten werden per SMTP korrekt als UTF-8 kodiert (Betreff und Text, geprüft)
- `backend/test_m50.py` (34 Tests): Werkzeug, 19 echte API-Antworten und Mails ohne ASCII-Umlautersatz, Prüfung aller Kundendateien auf Wörterbuchtreffer, SMTP-Kodierung; schlägt bei einer zurückgedrehten Meldung fehl. `test_m46.py` und `test_m48.py` an die neuen Schreibweisen angepasst

### Docs (Phase-4-Abschluss)
- `docs/orders-api.md`: Meilenstein-Uebersicht, Abschnitte "Webhook-Signatur" (Header, HMAC-Schema, Proxy-Hinweis, Secret-Rotation, Selbsttest) und "Fehlersuche (Stripe)", Endpunkttabelle aktualisiert
- `docs/phase4-plan.md`: Umsetzungsstand je Schritt (M42 bis M49), Ausgangslage mit Status, Abweichungen vom Datenmodell, offene Punkte vor einem Betrieb mit Geld
- `docs/known-limitations.md`: neuer Abschnitt "Abrechnung und Shop" (keine Rechnungen/USt, keine automatischen Erstattungen, keine Mehrwaehrung, keine Abonnements, Stripe nur gemockt getestet, keine automatische Wiederholung der Bereitstellung, Bestell-Mails, Kapazitaet nach Zuweisung, kein CAPTCHA, Tick-Betrieb); korrigiert: der Admin-Transfer loescht auf dem alten Node und legt neu an, **Dateien werden nicht uebertragen**; JWTs bleiben nach Passwortwechsel gueltig

### Changed (M49 – Zeitstempel einheitlich UTC)
- Alle Zeitstempel in API-Antworten haben jetzt einen Zeitzonen-Suffix (`2026-10-03T12:00:00+00:00`). Bisher lieferten naive DB-Werte (SQLite/PostgreSQL) Strings ohne Suffix, die Browser als Ortszeit lesen. Neuer Helfer `iso_utc()` in `backend/app/utils/timeutil.py` (naiv gilt als UTC, aware wird nach UTC umgerechnet, `None` bleibt `None`), eingesetzt in allen `to_dict()`-Methoden (64 Stellen in 18 Dateien) und in den Bestell-Ereignisdaten
- **Aenderung fuer Clients:** die Werte aendern sich nur um den Suffix, nicht in der Zeit selbst. Die Idempotenz-Referenz `free-auto:<ende>` bleibt unveraendert
- `backend/test_m49.py` (23 Tests): Helfer, Stichprobe je Modell und ein Crawler, der alle GET-Routen aufruft und jeden zeitstempelartigen String auf Suffix prueft (47 Routen, 83 Zeitstempel); schlaegt ohne die Aenderung fehl

### Changed (M48 Vertrag – Checkout-Fehlercodes)
- `POST /api/client/orders/{uuid}/checkout`: Fehler tragen einen stabilen `code` (`manual`, `invalid_status`, `nothing_to_pay`, `unsupported_currency`, `provider_unavailable`, `provider_error`); `checkout_url` wird nur ausgeliefert, wenn sie mit `https://` beginnt (sonst 502). `test_m48.py` (64)

### Added (M48 – Zahlungsanbieter Stripe)
- `backend/app/domain/billing/payments.py`: Provider-Schnittstelle (`create_checkout`, `handle_webhook`) mit `ManualProvider` (Standard) und `StripeProvider` (Stripe Checkout `mode=payment`, Webhook mit `Webhook.construct_event`); `PAYMENT_PROVIDER=manual|stripe`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (`stripe==16.0.0` in `requirements.txt`)
- `POST /api/client/orders/{uuid}/checkout` -> `{checkout_url}` (pending_payment, active, past_due; 409 bei manual, anderem Status, Gratis-Bestellung und Waehrungen ohne Nachkommastellen; 502 bei Stripe-Fehler ohne Interna), `GET /api/client/billing-info` (oeffentlich)
- `POST /api/payments/stripe` (ohne Login, Signaturpruefung, Replay-Schutz): `checkout.session.completed`/`async_payment_succeeded` mit `payment_status=paid` verbuchen wie `mark-paid` (Referenz = PaymentIntent); Idempotenz ueber `payment_events` (Event-ID) und `payment_references`; Betrag/Waehrung-Abweichung -> `mismatch` ohne Freischaltung; Zahlung fuer stornierte/beendete Bestellung -> `unapplied`; beides mit Activity-/Webhook-Event `order:payment_unapplied`; kein Platz -> 200 und `awaiting_provisioning`; interne Fehler -> 500 (Stripe wiederholt)
- Neue Tabelle `payment_events` (Migration `q7l8m9n0o1p2`, Up/Down geprueft); Produktion meldet KRITISCH bei `PAYMENT_PROVIDER=stripe` ohne Schluessel oder unbekanntem Anbieter
- Gekuendigte Bestellungen bekommen vor Laufzeitende einmalig den Hinweis "Server wird am X geloescht" (Event `order:reminder`, `kind: deletion_notice`), normale Erinnerungen `kind: expiry_reminder`
- Doku: `docs/orders-api.md` (Einrichtung, Webhook-Regeln, Test-Modus); Tests: `backend/test_m48.py` (60, ohne Netzwerk: Checkout gemockt, Signaturen nach Stripes Verfahren), `test_m46.py` (86)

### Added (M46 Nachtrag – Erinnerung, Gratis-Verlaengerung, blueprint_name)
- Erinnerungsmail `BILLING_REMINDER_DAYS` (Standard 3, 0 = aus) vor Laufzeitende, Event `order:reminder`, hoechstens einmal pro Bestellung und Laufzeit (`orders.reminded_for_period_end`, Migration `p6k7l8m9n0o1`); nur bezahlte Bestellungen ohne Kuendigung mit Laufzeit laenger als das Fenster
- Kostenlose Bestellungen (`price_cents = 0`) werden vom Tick bei Ablauf automatisch verlaengert statt gesperrt und geloescht (der Kunde kann nichts bezahlen); gekuendigte laufen zum Laufzeitende aus. Tick-Zusammenfassung enthaelt jetzt `reminded` und `renewed`
- `Product.to_public_dict()`/`to_dict()` liefern `blueprint_name` (Listen laden den Blueprint per Join mit), `blueprint_id` bleibt intern
- Tests: `test_m46.py` (83), `test_m44.py` (87)

### Added (M46 – Billing-Tick)
- `python cli.py billing-tick` (idempotent, alle paar Minuten per Cron/Compose): `active` + Laufzeit abgelaufen -> `past_due` (Instance suspendiert mit Grund "Zahlung überfällig", synchronisiert und auf dem Node beendet, Mail); `past_due` laenger als `BILLING_GRACE_DAYS` (Standard 7) -> Instance geloescht (`force`), `expired`, Mail; Kuendigung zum Laufzeitende -> sofort geloescht; fehlende Instance -> `expired` ohne Runner-Aufruf. Ausgabe als JSON `{checked, past_due, expired, errors}`, Exit-Code 1 bei Fehlern
- Karenzzeit zaehlt ab `orders.past_due_at` (nicht ab Laufzeitende), ein Tick-Ausfall kostet Kunden keine Karenzzeit; bestehende Admin-Sperren werden nicht ueberschrieben; bei laufender Installation/Transfer wartet der Tick bis zu einen Tag; jede Bestellung wird einzeln committed, Fehler blockieren die anderen
- Verlaengerung ueber `POST /api/admin/orders/{uuid}/mark-paid` auf `active`/`past_due`: neues Ende ab `max(jetzt, altes Ende)`, `payment_reference` ist **Pflicht** (400) und macht den Aufruf idempotent (verbuchte Referenzen in `orders.payment_references`), hebt nur die Sperre "Zahlung überfällig" auf. **Aenderung gegenueber M44:** mark-paid auf eine aktive Bestellung ist ohne Referenz kein No-op mehr, sondern 400
- `delete_instance` loest verknuepfte Bestellungen von der Instance (Fremdschluessel `orders.instance_id`; ohne das scheitert das Loeschen einer bestellten Instance auf PostgreSQL) und setzt lebende Bestellungen auf `expired`
- Bestellungen liefern `past_due_at` und `scheduled_deletion_at`; neue Events `order:past_due`, `order:renewed`, `order:expired`; Config `BILLING_GRACE_DAYS`
- Migration `o5j6k7l8m9n0` (`orders.past_due_at`, `orders.payment_references` mit Backfill aus `payment_reference`), Datum/Zeit der Bestellungen jetzt durchgehend naive UTC
- `suspend_instance`/`unsuspend_instance` akzeptieren `admin_user_id=None` (System) ohne Logging-Fehler
- `backend/test_m46.py` (65 Tests, Zeit per `now=` eingefroren), `docs/orders-api.md` ergaenzt

### Added (M44 – Produkte und Bestellungen)
- Neue Tabellen `products` und `orders` (Migration `n4i5j6k7l8m9`, Upgrade/Downgrade geprueft, Schema stimmt mit `create_all` ueberein). Bestellungen halten einen Schnappschuss von Preis, Laufzeit und Ressourcen
- Admin: `GET/POST /api/admin/products`, `GET/PATCH/DELETE /api/admin/products/{id}`, `GET /api/admin/orders` (Filter `status`, `user_id`), `GET /api/admin/orders/{uuid}`, `POST /api/admin/orders/{uuid}/mark-paid` (manuelle Zahlung, stellt die Instance per automatischer Platzierung bereit; idempotent; ohne freien Node bleibt die Bestellung `awaiting_provisioning` und kann erneut bereitgestellt werden)
- Kunde: `GET /api/client/products` (oeffentlich, nur aktive Pakete ohne interne Felder), `POST /api/client/orders`, `GET /api/client/orders[/{uuid}]`, `POST /api/client/orders/{uuid}/cancel` (offen: sofort, aktiv: zum Laufzeitende)
- Regeln: max. 5 offene Bestellungen pro Kunde, `max_instances_per_user` je Paket, kostenlose Pakete nur mit Limit und sofort bereitgestellt, bestaetigte E-Mail wenn `EMAIL_VERIFICATION_REQUIRED`, Produkt mit Bestellungen und Blueprint mit Produkten nicht loeschbar (409)
- Neue Activity-/Webhook-Events `order:created`, `order:paid`, `order:provision_failed`, `order:cancelled`
- `docs/orders-api.md`, `backend/test_m44.py` (84 Tests)

### Added (M43 – Instance loeschen)
- `delete_instance(instance, actor_id, force)` im Instance-Service: Runner-Aufraeumen best effort (Backups, Datenbanken, Instance auf dem Node; Fehler werden geloggt und als `runner_cleanup: "failed"` gemeldet, das Panel loescht trotzdem), Endpoints werden freigegeben (Zeilen bleiben), Backups/Datenbanken/Collaborators/Routines inkl. Actions werden entfernt, Activity-Eintraege bleiben erhalten
- Laufende Vorgaenge (`provisioning`, `reinstalling`, `restoring`, `transferring`) -> 409, ausser Admin mit `force: true`
- `DELETE /api/admin/instances/{uuid}` (Admin-Guard, optional `{"force": true}`) und `DELETE /api/client/instances/{uuid}` (nur Owner, Body `{"confirm": "<Name>"}` case-sensitiv, suspendierte Instances -> 409, Collaborators und Fremde -> 404, `force` fuer Owner nicht moeglich)
- Neues Activity-/Webhook-Event `instance:deleted` (mit Name, UUID, Owner, Agent, `runner_cleanup`, `forced`)
- `backend/test_m43.py` (40 Tests)

### Added (M42 – Kapazitaetspruefung und Platzierung)
- `backend/app/domain/agents/placement.py`: `capacity_problem()`, `used_resources()` und `pick_agent(memory, disk, cpu)` (aktiv, nicht in Wartung, freier Endpoint, genug freie effektive Kapazitaet inkl. Overalloc; Auswahl nach geringster Auslastung nach der Platzierung, Gleichstand: weniger Instanzen, kleinere ID)
- `create_instance` bricht mit 409 ab, wenn RAM, Disk oder CPU des gewaehlten Agents nicht reichen (Meldung nennt Dimension und freien Rest); Agents mit `*_total = 0` gelten je Dimension als ohne Limit. Zeilensperre auf dem Agent serialisiert parallele Erstellungen auf PostgreSQL
- `POST /api/admin/instances`: `agent_id` ist optional, fehlt es oder ist `null`, platziert Astra automatisch (409 ohne passenden Agent, `endpoint_id` ohne `agent_id` -> 400)
- Transfer prueft die Kapazitaet des Ziel-Agents (409)
- `backend/test_m42.py` (23 Tests)

### Added (Account und SFTP-Port)
- `POST /api/auth/change-password` – `{current_password, new_password}` fuer eingeloggte Nutzer; 401 bei falschem aktuellem Passwort (und ohne Login), gleiche Regeln wie bei der Registrierung (mind. 8 Zeichen), neues Passwort muss sich unterscheiden, Activity-Events `auth:password_changed` / `auth:password_change_failed`, offene Reset-Links werden ungueltig, Rate Limiting aktiv. Bereits ausgestellte JWTs bleiben bis zum Ablauf gueltig
- `instance.connection` enthaelt jetzt `sftp_port` (Port des Agents), damit auch Nicht-Admins die SFTP-Zugangsdaten anzeigen koennen
- Tests in `test_m34.py` (30) und `test_m39.py` (29)

### Added (M41 – Wings-Erreichbarkeit und Endpoint-Pflicht)
- Fleet Monitoring (`GET /api/admin/agents/monitoring`, `/agents/{id}/monitoring`) liefert `daemon_reachable`, `daemon_version` und `daemon_error`, ermittelt per `GET /api/system` am Wings (Bearer `daemon_token`, Timeout 3 s, Ergebnis 30 s gecacht, Cache-Schluessel enthaelt URL und Token; mehrere Agents werden parallel geprueft). Mit dem Stub-Adapter immer `true`/`"stub"` (`backend/app/domain/agents/reachability.py`)
- Preflight: neuer Check `agents_reachable`, warnt bei nicht erreichbaren aktiven Agents (Agents in Wartung und inaktive Agents werden nicht geprueft), blockiert nicht
- Kein stiller Standard-Port mehr: Hat eine Instanz keinen primaeren Endpoint, setzt der Config-Builder `SERVER_PORT` und `allocations.default.port` auf `0` (wie `allocation->port ?? 0` im Referenz-Panel), `allocations.mappings` bleibt leer und es gibt eine Log-Warnung (vorher 25565)
- Bestaetigt und getestet: `create_instance` bricht ohne freien (oder nur gesperrten) Endpoint mit 409 ab und speichert nichts
- `backend/test_m41.py` (27 Tests)

### Fixed / Added (E-Mail-Links und Verifizierungs-Frontend)
- Fix: Der Link in der Passwort-Reset-Mail zeigte auf `/reset-password`, die Frontend-Route heisst `/password-reset/confirm` (Link fuehrte auf die 404-Seite); Tests pruefen jetzt beide Mail-Links gegen die Frontend-Routen
- `POST /api/auth/resend-verification` akzeptiert zusaetzlich `login` (Benutzername oder Adresse), Antwort bleibt neutral
- Frontend: neue Seite `/verify-email` (Ziel des Mail-Links), Registrierung zeigt bei aktiver Verifizierung den Hinweis "E-Mail bestaetigen" mit "Erneut senden", Login zeigt bei `email_not_verified` einen Hinweis mit Knopf zum erneuten Senden; `ApiError` traegt HTTP-Status und Fehlercode

### Removed (M40 – Legacy /api/agent)
- Der Blueprint `/api/agent` (`instances/{uuid}/install`, `instances/{uuid}/container/status`, `sftp-auth`, `health`) wurde komplett entfernt. Wings und alle Agents nutzen `/api/remote` mit Node-Token. Der Agent-Guard aus M36 samt `AGENT_GUARD_ENABLED` und `test_m36.py` entfaellt damit
- Frontend: Dev-Knopf "Simuliere Install-Callback" und `api.reportInstallResult` entfernt (er lief seit M36 in einen 403)
- Tests M15–M20, M27, M30, M33 nutzen jetzt die Remote-API ueber `backend/test_helpers.py` (`report_container_state`, `report_install`, `node_headers`); der Fingerprint-Pfad der Legacy-Route ist weiter ueber `authorize_ssh_key_access()` abgedeckt (M30 b)
- `backend/test_m40.py` (11 Tests) stellt sicher, dass `/api/agent/*` 404 liefert und `/api/remote` Token verlangt

### Security (M36 – Agent-Guard, durch M40 abgeloest)
- `/api/agent/*` verlangt jetzt den Node-Token (`Authorization: Bearer {token_id}.{token}`, gleiche Pruefung wie `/api/remote`). Ausnahme: `GET /api/agent/health`
- Ein Agent darf nur Instanzen seines eigenen Nodes melden (`install`, `container/status` -> 403, `sftp-auth` -> `allowed: false, reason: instance_not_on_node`)
- Schalter `AGENT_GUARD_ENABLED` (Standard `true`), nur in `TestingConfig` aus
- `backend/test_m36.py` (17 Tests)

### Added (M39 – Endpoint-Bulk und Verbindungsadresse)
- `POST /api/admin/agents/{id}/endpoints/bulk` – Body `{ip, port_start, port_end}` legt einen Port-Bereich an, ueberspringt vorhandene (`ip` + `port` je Agent). Antwort `{created, skipped, endpoints}` (nur neu angelegte), 201 bei neuen Endpoints, sonst 200. Grenzen: 1..65535, `port_start <= port_end`, max. 1000 Ports pro Aufruf, `ip` muss gueltig sein
- `Instance.to_dict()` liefert `connection`: `{host, ip, port, address}` (`host` = FQDN des Agents, `address` = `host:port`), `null` ohne primaeren Endpoint. Admin- und Client-Listen laden Agent und Endpoint per Join mit, keine Query pro Instanz
- `backend/test_m39.py` (27 Tests)

### Added (M38 – E-Mail-Verifizierung)
- `EMAIL_VERIFICATION_REQUIRED` (Standard `false`): Registrierung sendet einen Bestaetigungs-Link (`EMAIL_VERIFICATION_TTL_HOURS`, Standard 48), Login ist erst nach Bestaetigung moeglich (403, `code: email_not_verified`)
- `POST /api/auth/verify-email` und `POST /api/auth/resend-verification` (antwortet immer gleich); Token ist an die Adresse gebunden
- Neue Spalte `users.email_verified_at` (Migration `m3h4i5j6k7l8`): bestehende Nutzer werden mit `created_at` als bestaetigt markiert, vom Admin angelegte Nutzer und der Bootstrap-Admin ebenfalls; ein erfolgreicher Passwort-Reset bestaetigt die Adresse
- `User.to_dict()` liefert `email_verified`
- `backend/test_m38.py` (22 Tests)

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

### Changed
- Rate Limiting fuer `/api/auth/login` nutzt jetzt Redis (geteilter Zaehler ueber alle Gunicorn-Worker), mit In-Memory-Fallback wenn Redis nicht erreichbar ist (`backend/app/infrastructure/ratelimit.py`)
- `redis` zu `backend/requirements.txt` hinzugefuegt

### Added (Frontend)
- Sicherer Instance-Transfer (Admin): statt des Ein-Klick-Transfers ein Dialog (`TransferInstanceForm`) mit roter Warnung "Beim Transfer werden die Serverdaten NICHT uebertragen …", Pflicht-Checkbox "Ich habe ein aktuelles Backup" und Bestaetigung per Instanzname; Backup-Pruefung ueber `GET /admin/instances/{uuid}/backups` (`successful_count`, `last_successful_backup_at`): ohne erfolgreiches Backup ist der Transfer gesperrt, sonst wird das letzte Backup mit Datum angezeigt; ist die Abfrage nicht moeglich, gilt nur die Checkbox
- Zahlungsweg ueber `GET /client/billing-info` (einmal beim Laden von `/orders`): bei manuellem Anbieter werden keine Bezahl-Buttons gerendert, sondern direkt der Hinweis aus `src/legal/payment.ts`; 409 "manual" bleibt Fallback. Kostenlose Bestellungen zeigen weder Bezahl-Button noch Ueberweisungshinweis
- Stripe-Frontend an den Vertrag angepasst: "Verlängern und bezahlen" bei aktiven/ueberfaelligen Bestellungen, Hinweis zum manuellen Zahlungsweg aus zentraler Konstante (`src/legal/payment.ts`), Toasts "Zahlung eingegangen, Server wird bereitgestellt." / "Zahlung abgebrochen.", Nachladen nach 5 s
- Alle Backend-Zeitstempel werden als UTC gelesen (`parseUtc`, `formatDateTime`, `formatTimeAgo`, ...): Aktivitaetslog, Backups, Routinen, API-Keys, SSH-Keys, Jobs, Agents, Blueprints, Fleet Monitoring. Behebt falsche "vor X Std."-Angaben in Browsern ausserhalb von UTC; Strings mit Zeitzonen-Suffix (z.B. `+00:00`) bleiben unveraendert
- Stripe-Vorbereitung auf `/orders`: Button "Jetzt bezahlen" fuer unbezahlte Bestellungen (`POST /client/orders/{uuid}/checkout` -> Weiterleitung zur `checkout_url`, nur https); bei 409 "manual" verschwindet der Button und es erscheint der Hinweis zur Zahlung per Ueberweisung; Rueckkehr `?paid=<uuid>` (Dank-Toast, Status wird bis zur Bestaetigung nachgeladen) und `?cancelled=<uuid>` (Hinweis, Bestellung bleibt offen)
- Billing-Tick-Vertrag (M46): Admin-Bestellungen mit "Verlaengern (Zahlung erfassen)" bei active/past_due (Zahlungsreferenz Pflicht), Warnhinweise bei Kunden und Admin (`OrderNotice`): "Gesperrt seit …" und "Server wird am … geloescht" (rot) bei past_due, "Laeuft bis …, wird dann geloescht" bei gekuendigten aktiven Bestellungen; Lösch-Dialog nennt bei laufender Bestellung "… eine Erstattung erfolgt nicht"; Zeitstempel ohne Zeitzone werden als UTC gelesen (`parseUtc`, `formatDateTime`); Vitest laeuft mit fester Zeitzone UTC
- Rechtsseiten `/impressum`, `/datenschutz`, `/agb` (ohne Login erreichbar, Platzhaltertexte mit Hinweis "vom Betreiber auszufuellen", Betreiberdaten zentral in `src/legal/operator.ts`, offene Platzhalter hervorgehoben), Footer mit Rechtslinks auf allen Seiten inkl. Login/Registrierung (`SiteFooter`); Registrierung mit Pflicht-Checkbox "Ich akzeptiere die AGB und die Datenschutzerklaerung"
- Admin-Dashboard: Karte "Offene Bestellungen" (pending_payment + awaiting_provisioning, Links auf `/admin/orders?status=...`; der Statusfilter der Bestellliste wird aus der URL uebernommen)
- Login und Registrierung kehren per `?redirect=` zur urspruenglichen Seite zurueck (nur interne Pfade, Schutz vor Open Redirect, `lib/redirect.ts`); geschuetzte Routen leiten mit Rueckkehrziel zum Login. `/shop` bleibt fuer den Pilot geschuetzt. Admin-Bestellungen heben `awaiting_provisioning` hervor; Blueprint-Name auf Shop-Karten, sobald das Backend ihn liefert
- Phase 4 gegen die echten Endpunkte (M44, `docs/orders-api.md`): Admin-Produkte `/admin/products` (CRUD, Euro<->Cent, Ressourcen flach im Body, `is_active`, Gratis-Produkte brauchen `max_instances_per_user`), Kunden-Shop `/shop` (Karten, Bestellung mit optionalem Servername, Hinweise je Status), Meine Bestellungen `/orders` (Bestellungen per `uuid`, Status-Badges inkl. `awaiting_provisioning`, Verbindungsadresse, Stornieren sofort vs. Kuendigen zum Laufzeitende), Admin-Bestellungen `/admin/orders` (Statusfilter, "Als bezahlt markieren" mit optionaler Zahlungsreferenz, "Erneut bereitstellen", 409-Text). Navigation "Shop"/"Meine Bestellungen" fuer alle, "Produkte"/"Bestellungen" fuer Admins; Dashboard verweist Kunden ohne Server auf den Shop
- Instance loeschen (M43): Owner auf der Detailseite ("Instance loeschen", `DELETE /client/instances/{uuid}` mit Namensbestaetigung; gesperrte Instances nur durch Admins), Admin in der Instance-Liste (`DELETE /admin/instances/{uuid}`, "Erzwingen" bei laufenden Vorgaengen, Hinweis wenn das Aufraeumen auf dem Node fehlschlug). Bestaetigung erst nach exakter Eingabe des Namens (`DeleteInstanceForm`); nach dem Loeschen als Owner Redirect aufs Dashboard mit Toast, Admins bekommen bei `runner_cleanup: failed` einen Warn-Toast ("Aufraeumen auf dem Node fehlgeschlagen, bitte Wings pruefen"), Kunden bei gesperrter Instance den Hinweis "Gesperrt, bitte Support kontaktieren"
- Agent-Formular (Erstellen/Bearbeiten): Kapazitaet Memory/Disk/CPU gesamt und Ueberallokation je Dimension (0 = kein Limit), Validierung 0..1000 % fuer Ueberallokation
- Instance-Erstellung mit automatischer Platzierung (M42): Agent-Auswahl "Automatisch (nach Kapazitaet)" als Standard (`agent_id: null`), Endpoint-Feld nur bei gewaehltem Agent, 409-Text der Platzierung wird angezeigt
- Kapazitaet je Agent auf der Agents-Seite: Memory/Disk/CPU "belegt von effektiv" mit Balken (gemeinsame Komponente `UtilizationBar`, "kein Limit" bei Gesamtwert 0, Progressbar-Semantik)
- Wings-Status (`DaemonStatus`) auf Fleet Monitoring und Agents-Seite: Badge "Wings erreichbar"/"nicht erreichbar" (Fehler als Tooltip) und Version aus `daemon_reachable`/`daemon_version`/`daemon_error`
- Konto-Seite `/account` (Navigation "Konto"): Profil, MFA/TOTP einrichten (QR-Code clientseitig mit `qrcode`, Secret als Text, Verifikation, Recovery-Codes einmalig) und deaktivieren, API-Keys (Liste, anlegen, loeschen; Token nur einmal sichtbar), Link auf SSH-Keys, "Passwort aendern" (`POST /auth/change-password`, mit Hinweis zu bestehenden Sitzungen)
- Login: zweiter Schritt fuer MFA (`requires_mfa` -> Code/Recovery-Code); vorher konnten sich MFA-Nutzer im Frontend nicht anmelden
- Agents-Seite: Health-Badge je Agent (`GET /admin/agents/monitoring`, 15s Auto-Refresh), optional "Wings erreichbar"/Version sobald `daemon_reachable`/`daemon_version` geliefert werden
- Kunden-/Admin-Trennung im UI: Admin-Links nur fuer `is_admin`, Admin-Routen leiten Kunden zum Dashboard um (`AdminRoute`, `useCurrentUser`); Dashboard zeigt den Benutzernamen statt "User #id" und einen Kunden-Leerzustand
- Instance-Detail: Box "SFTP-Zugang" (Host, Port, Benutzername `<user>.<uuid[:8]>` mit Kopier-Buttons, Hinweis auf Panel-Passwort/SSH-Key). Port aus `connection.sftp_port`, fuer Admins sonst aus der Agent-Liste
- Endpoint-Formular: Port-Bereich (`25565-25600`) ueber `POST /admin/agents/{id}/endpoints/bulk`, Ergebnis-Toast "n angelegt, m uebersprungen"; Einzelport wie bisher (`lib/portRange.ts`)
- Blueprint-Import-UI (`BlueprintImport`) auf der Blueprint-Admin-Seite: Egg-JSON per Datei oder Textarea, Vorschau, Aufruf `POST /api/admin/blueprints/import` (Feature-Flag entfernt, immer sichtbar)
- Verbindungsadresse (`ConnectionAddress`) mit Kopier-Button auf Dashboard und Instance-Detail; erscheint, sobald die Instance-Antwort ein Feld `connection` {host, port, address} liefert
- Agents: Bearbeiten-Formular (`PATCH /admin/agents/{id}`) und getrennte Felder Connect-Port (Panel -> Wings, z.B. 443 hinter Caddy) und Listen-Port (Wings lokal, z.B. 8080) im Erstellen- und Bearbeiten-Formular; Port-Validierung 1-65535
- Self-Service (M34-Frontend): `RegisterPage` (/register), `ForgotPasswordPage` (/password-reset), `ResetPasswordPage` (/password-reset/confirm?token=), Links auf der LoginPage; Meldung "Registrierung ist deaktiviert"; clientseitige Validierung (Passwort min. 8 Zeichen)
- `PageLayout`: SPA-Navigation per `react-router` (kein Seiten-Reload), `aria-current`, Abmelden-Button
- `FileBrowser`: Upload von Textdateien (max. 1 MB, Workaround ueber Write-Endpoint) und "Neue Datei"
- Auto-Refresh (15s, abschaltbar, nur bei sichtbarem Tab) fuer Jobs-Dashboard, Fleet Monitoring, Dashboard und Admin-Instances (`hooks/useAutoRefresh.ts`, `AutoRefreshToggle`)
- 401-Handling: abgelaufene Sitzung leitet zu `/login?expired=1` mit Hinweis um
- `ErrorBoundary` gegen weisse Seite bei Render-Fehlern, `NotFoundPage` als Catch-all-Route
- Mobile-Navigation (<=760px): Hamburger-Menue mit gruppierten Links und Abmelden, schliesst bei Seitenwechsel/Escape (`hooks/useMediaQuery.ts`); Login leitet eingeloggte Nutzer zum Dashboard
- `LoginPage`: gemeinsame UI-Styles, Label-Verknuepfung, `autocomplete`, `role="alert"`

### Changed (Frontend)
- Ende-zu-Ende gegen das echte Backend geprueft (Registrierung, Passwort aendern ohne Ausloggen bei falschem Passwort, MFA mit echtem TOTP-Code, API-Keys, Bestellung/Zahlung/Verlaengerung/Kuendigung, Server loeschen, Produkte, Agents mit Kapazitaet, automatische Platzierung). Dabei behoben: unbeschriftete Checkboxen in der Dateiliste, englischer Rohstatus im Loesch-Hinweis (deutsches Label), deutsche Health-Labels, "Kapazitaet" in Backend-Fehlertexten
- Kunden-Durchsicht (verstaendliche Texte): korrekte Umlaute in allen Kundentexten; ASCII-Schreibweisen aus Backend-Meldungen werden korrigiert (`lib/umlauts.ts`, z.B. "Ungültige Anmeldedaten"); technische Statuscodes ("Request failed: 500") durch allgemeine Meldungen ersetzt; Fehlerseite ohne technischen Text (Details einklappbar); "Instance" heisst fuer Kunden "Server"; Steuerung auf der Server-Seite mit deutschen Beschriftungen (Starten, Stoppen, Neustarten, "Beenden erzwingen" mit Rueckfrage, "Neu installieren"); deutsche Statuslabels (bereit, laeuft, gestoppt, wird eingerichtet, gesperrt ...); Konsole und Fehlerfallbacks ohne Fachbegriffe (Token, WebSocket, Daemon)
- Barrierefreiheit: Link-Farbe `#1565c0`, Kontrast im Sperr-Banner und in der Konsole, Beschriftung der Benutzerauswahl bei Mitbenutzern (axe auf Dashboard, Server-Seite, Konto, Bestellungen, Shop sauber)
- API-Client: 401 von `/auth/change-password` (falsches aktuelles Passwort) loggt nicht mehr aus
- Verstaendliche Fehlermeldungen im API-Client: 403 vom Admin-Guard -> "Nur Administratoren duerfen diese Aktion ausfuehren.", nicht erreichbarer Server -> eigene Meldung (`lib/errors.ts`)
- Kunden-Dashboard: Platzhalter "Noch kein Server. Bestellung folgt in Phase 4." (Admins weiter mit Hinweis auf den Admin-Bereich), Komponententests fuer Leer-/Fehler-/Normalzustand
- Frontend-Tests mit Vitest (`npm test`, 54 Tests): Login/Registrierung/Passwort-Reset inkl. E-Mail-Verifizierung (Komponententests), SFTP-Box, Port-Bereich, Egg-Parser, Agent-Formular-Validierung, `useAutoRefresh`, API-Client (Bearer-Token, 401-Handling, Reset-Payload); Logik dafuer nach `src/lib/` ausgelagert
- Barrierefreiheit (axe-core, WCAG 2 A/AA, 13 Seiten ohne Verstoesse): Kontraste bei Grautexten, Status-Badges und Kennzahlen, Labels fuer Selects/Inputs auf Agents-, Instances-, Jobs- und Monitoring-Seite
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
