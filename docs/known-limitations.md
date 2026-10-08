# Known Limitations (RC1)

## Bewusst akzeptierte Einschraenkungen

### Runner / Wings-Integration
- **Stub-Adapter** laeuft in Dev/Test als Default. Wings-Adapter fuer Produktion vorhanden, aber erfordert echte Wings-Instanz.
- Seit M33 stellt Astra die Wings Remote-API (`/api/remote`) bereit; S3-Presigned-Uploads und Mounts sind nicht enthalten (siehe `docs/wings-remote-api.md`).
- Die Remote-API wurde gegen den Vertrag des Referenz-Panels gebaut und per Tests abgesichert, aber noch nicht gegen einen laufenden Wings-Daemon abgenommen (Teil des Pilot-Go/No-Go).
- Konsolen-Websocket funktioniert nur mit echtem Wings-Daemon (im Stub simuliert).
- Der Konsolen-Prompt `container@pterodactyl~` kommt aus den yolks-Images und bleibt, solange keine eigenen Images verwendet werden. Pfade, Benutzer und Docker-Netz auf dem Node heißen seit M78 `astra`; bestehende Nodes mit Pterodactyl-Pfaden behalten ihre Namen.
- Dateioperationen im Stub-Modus liefern simulierte Daten.

### Queue / Background Jobs
- **SyncQueue** (synchron) ist Default in Dev/Test. Fuer Produktion muss Redis konfiguriert und ein Worker gestartet werden.
- Webhook-Retry-Delays (5/15/30s) laufen im SyncQueue-Modus blockierend.
- Job-Cleanup ist nicht automatisch: alte Job-Eintraege (`completed`/`failed`) bleiben in der DB, bis jemand `python cli.py cleanup-jobs [--days 30] [--dry-run]` ausfuehrt (z.B. per Cron).

### Datenbank
- **SQLite** wird in Dev/Test verwendet. Fuer Produktion PostgreSQL empfohlen.
- Database-Provisioning (M18) erstellt Metadaten, verbindet sich aber nicht mit echten Datenbankservern.

### Auth / MFA
- MFA mit TOTP und seit M60 mit 10 einmaligen Recovery-Codes (nur Hashes gespeichert, Neu-Erzeugen mit Passwort, siehe `docs/mfa-recovery-codes.md`). Es gibt keinen Reset per E-Mail: wer weder Authenticator noch Codes hat, braucht einen Admin. MFA deaktivieren verlangt kein Passwort.
- API-Key-Rotation erfordert manuelles Loeschen und Neuerstellen.

### Agent Maintenance
- Kein automatisches Drain: Bestehende Instances laufen weiter auf Maintenance-Agents.
- Der Admin-Transfer zwischen Agents loescht die Instance auf dem alten Node und legt sie auf dem Ziel-Node neu an. **Dateien werden dabei nicht uebertragen** (Datenverlust, wenn vorher keine Sicherung gezogen wurde).

### Abrechnung und Shop (Phase 4)
- **Rechnungen nur als Grundlage:** Seit M70 stellt Astra Kleinbetragsrechnungen (§ 33 UStDV, bis 250 € brutto) mit fortlaufender Nummer, USt-Ausweis (`VAT_RATE`, Standard 0 = Kleinunternehmer-Hinweis) und Gutschriften bei Erstattungen aus; Export für die Buchhaltung unter `GET /api/admin/invoices`. Nicht abgedeckt: Rechnungen über 250 € (zusätzliche Pflichtangaben), B2B/Reverse-Charge, OSS, PDF und GoBD-konforme Aufbewahrung, Teil-Gutschriften nach Streitfällen (bei verlorenem Streit entsteht seit M73 eine Gutschrift über den Streitbetrag, höchstens bis zum Rechnungsbetrag). Preise sind Bruttopreise ohne Netto/Brutto-Trennung im Produkt. **Vor dem Echtbetrieb steuerlich prüfen lassen** (siehe `docs/orders-api.md`). Belege vor M70 haben keine Steuerangaben.
- **Schweiz (M74):** `INVOICE_COUNTRY=CH` liefert MWST-Beschriftung, Hinweis nach Art. 10 Abs. 2 lit. a MWSTG und das CHF-Format. Nicht abgedeckt: QR-Rechnung, E-Rechnung, MWST-Abrechnung mit mehreren Sätzen oder Auslandsumsätzen, Prüfung der MWST-Nr. (wird nur angezeigt). Die Zahlungen laufen weiter über Stripe; steuerliche Einstufung vorher mit Treuhänder klären.
- **Erstattungen manuell:** Astra erstattet nie automatisch; die Erstattung läuft im Stripe-Dashboard oder per Überweisung. Seit M59 reagiert Astra auf Stripe-Ereignisse dazu (`charge.refunded`, `charge.dispute.created/closed`): volle Erstattung der letzten Zahlung sperrt den Server und löscht ihn nach der Karenzzeit, Teilerstattungen und ältere Zahlungen lösen nur Alert und Event aus, Streitfälle sperren bis zum Ausgang. Beweise und Entscheidungen im Streitfall bleiben manuell, bei manueller Zahlung (`mark-paid`) und Überweisung gibt es keine Erstattungslogik. Löscht ein Kunde seinen Server selbst oder kündigt, gibt es keinen anteiligen Rest.
- **Keine Mehrwaehrung:** Jedes Produkt hat eine Waehrung, Astra rechnet nicht um und berichtet nicht ueber Waehrungen hinweg. Fuer Stripe nur Waehrungen mit Nachkommastellen (kein JPY, KRW usw.).
- **Keine Abonnements:** Stripe wird nur als Einmalzahlung (`mode=payment`) genutzt. Der Kunde verlaengert jede Laufzeit selbst; der Tick erinnert per Mail (`BILLING_REMINDER_DAYS`), sperrt bei Ablauf und loescht nach `BILLING_GRACE_DAYS`. Nur kostenlose Pakete verlaengern sich automatisch.
- **Stripe nur mit gemockten Aufrufen getestet:** Es gab nie einen echten Stripe-Aufruf. Vor dem Livegang einmal im Test-Modus mit Stripe CLI durchspielen (siehe `docs/orders-api.md`).
- **Wartezeit bei fehlendem Platz:** Ist nach einer Zahlung kein Node mit Platz frei, bleibt die Bestellung `awaiting_provisioning`. Der Billing-Tick stellt sie automatisch bereit, sobald Platz da ist (aelteste Zahlung zuerst, Laufzeit beginnt dann). Der Admin wird nicht aktiv benachrichtigt, sieht lange Wartezeiten aber im Preflight-Check `billing_waiting_orders` und in `GET /api/admin/billing/status` (`awaiting_provisioning`, Warnschwelle `BILLING_WAIT_WARN_HOURS`, Standard 24); sonst gibt es nur das Event `order:provision_failed` beim ersten Versuch. Der Kunde bekommt erst bei der Bereitstellung eine Mail.
- **Fehlertexte der API:** Kundenseitige Fehler (`/api/auth`, `/api/client`) gibt es auf Deutsch und Englisch mit stabilem `code` (M72). Ohne Katalogeintrag (z. B. Meldungen des Wings-Daemons, Admin-Sperrgruende) bleibt der Originaltext; Admin-Routen und Webhooks bleiben deutsch.
- **Sprachen:** Mails und Belege gibt es auf Deutsch und Englisch (`users.locale`, M67); Admin-Alerts, API-Fehlermeldungen und Activity-Texte bleiben deutsch, weitere Sprachen brauchen Einträge in `backend/app/i18n/messages.py`. Der Beleg wird in der aktuellen Sprache des Kunden gerendert, nicht in der zum Zahlungszeitpunkt.
- **Bestell-Mails:** Mails gibt es bei Zahlungseingang (Server bereit bzw. Hinweis auf Wartezeit), Verlängerung, Erinnerung, Überfälligkeit und Löschung; keine bei Anlegen einer Bestellung und keine bei kostenlosen Paketen. Es sind einfache Textmails ohne Rechnung. Ohne `MAIL_SERVER` werden Mails nur ins Log geschrieben.
- **Kapazitaet nach Zuweisung:** Die Kapazitaetspruefung rechnet mit den zugewiesenen Ressourcen der Instances (inkl. Overallocation des Agents), nicht mit der tatsaechlichen Auslastung. Die Zeilensperre gegen parallele Erstellungen wirkt nur auf PostgreSQL.
- **Missbrauchsschutz:** Registrierung hat Rate Limits je IP, Honigtopf-Feld, optionale E-Mail-Verifizierung und seit M71 optional ein CAPTCHA (Turnstile oder hCaptcha, Standard aus; Datenschutzhinweis siehe `docs/operations.md`). Der Login sperrt ein Konto nach 20 Fehlversuchen pro Stunde: Fremde koennen so einen bekannten Benutzernamen eine Stunde lang aussperren. Hinter Proxys haengt die IP-Erkennung an `PROXY_FIX_X_FOR`. Gratis-Pakete sind nur ueber `max_instances_per_user` begrenzt.
- **Tick-Betrieb:** Der Billing-Tick laeuft als Schleife im Compose-Service `billing`. Faellt er aus, werden weder Ablaeufe durchgesetzt noch Erinnerungen verschickt. Seit M53 erkennt das Panel das (`GET /api/admin/billing/status`, Preflight-Check `billing_tick`, Warnung nach `BILLING_TICK_MAX_AGE_MINUTES`, Standard 15). Seit M58 meldet Astra Ausfall, Fehler im Tick und lange wartende Bestellungen aktiv per Mail und/oder Webhook (`ADMIN_ALERT_EMAIL`, `ADMIN_ALERT_WEBHOOK_URL`, Container `alerts`). Ohne konfigurierten Kanal (Standard) bleibt es bei Status und Preflight. Die Meldung ist best effort: fällt der Mail-/Webhook-Dienst selbst aus, kommt nichts an; die Entprellung merkt sich nur den Zustand, nicht ob eine Nachricht zugestellt wurde.

### UI / Frontend
- Responsive Design: Kundenseiten (Dashboard, Server, Bestellungen, Konto, Shop) sind mobil nutzbar (Hamburger-Menue, Bestellungen als Karten); Admin-Tabellen scrollen auf kleinen Bildschirmen horizontal.
- File-Upload nur fuer Textdateien bis 1 MB (kein Multipart-Endpoint im Backend).
- Alle Seiten mit Navigation nutzen `PageLayout` (Tab-Titel, Skip-Link) und `StatusBadge`; Tabellen scrollen auf kleinen Bildschirmen horizontal in einem per Tastatur fokussierbaren Bereich (`ScrollRegion`). Nur die Bestellungen des Kunden werden mobil als Karten dargestellt.
- Sprachen: Deutsch (Standard) und Englisch fuer die Kundenseiten ausser der Server-Detailseite; Admin-Bereich, Rechtstexte und Backend-Meldungen bleiben deutsch.
- Keine Echtzeit-Updates via WebSocket fuer Admin-Ansichten; Jobs, Fleet Monitoring, Dashboard und Admin-Instances pollen alle 15s (abschaltbar), andere Seiten nur manuell.

### Monitoring / Observability
- Fleet Monitoring basiert auf DB-Werten, nicht auf Live-Metriken.
- Keine Prometheus-/Grafana-Integration.
- Application Insights / APM nicht integriert.

### Deployment
- Docker/Compose ist vorbereitet, aber Kubernetes-Manifeste fehlen.
- SSL/TLS-Terminierung wird von externem Reverse Proxy erwartet.

### Sicherheit
- `/api/admin` ist durch einen Admin-Guard geschuetzt (M35), Agents sprechen nur noch ueber `/api/remote` mit Node-Token. Die Legacy-Routen unter `/api/agent` wurden mit M40 entfernt.
- Rate Limiting nutzt Redis (`REDIS_URL`); ist Redis nicht erreichbar, faellt es auf einen In-Memory-Zaehler pro Prozess zurueck.
- **Logout:** `POST /api/auth/logout` sperrt das verwendete Access-Token bis zu seinem Ablauf (Tabelle `revoked_tokens`, Prüfung bei jedem Request per Primärschlüssel-Lookup; kein Redis-Cache, damit ein Redis-Neustart Abmeldungen nicht aufhebt). Andere Geräte bleiben angemeldet (dafür gibt es den Passwortwechsel, M57). Tokens ohne `jti` (vor M61 ausgestellt: alle neuen haben eins) und API-Keys lassen sich nicht sperren. Abgelaufene Einträge räumt `cleanup-jobs` bzw. der nächste Logout auf.
- CSRF-Schutz ist ueber SameSite Cookies + JWT geloest, kein dedizierter CSRF-Token.
- Passwortwechsel und -reset machen neu ausgestellte JWTs sofort ungueltig (Claim `pwf`, Fingerabdruck des Passwort-Hashes); das Gerät, das das Passwort ändert, bekommt ein frisches Token. Noch vor M57 ausgestellte Tokens ohne diesen Claim gelten bis zu ihrem Ablauf (24 Stunden). API-Keys bleiben vom Passwortwechsel unberührt.
