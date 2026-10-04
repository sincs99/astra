# Known Limitations (RC1)

## Bewusst akzeptierte Einschraenkungen

### Runner / Wings-Integration
- **Stub-Adapter** laeuft in Dev/Test als Default. Wings-Adapter fuer Produktion vorhanden, aber erfordert echte Wings-Instanz.
- Seit M33 stellt Astra die Wings Remote-API (`/api/remote`) bereit; S3-Presigned-Uploads und Mounts sind nicht enthalten (siehe `docs/wings-remote-api.md`).
- Die Remote-API wurde gegen den Vertrag des Referenz-Panels gebaut und per Tests abgesichert, aber noch nicht gegen einen laufenden Wings-Daemon abgenommen (Teil des Pilot-Go/No-Go).
- Konsolen-Websocket funktioniert nur mit echtem Wings-Daemon (im Stub simuliert).
- Dateioperationen im Stub-Modus liefern simulierte Daten.

### Queue / Background Jobs
- **SyncQueue** (synchron) ist Default in Dev/Test. Fuer Produktion muss Redis konfiguriert und ein Worker gestartet werden.
- Webhook-Retry-Delays (5/15/30s) laufen im SyncQueue-Modus blockierend.
- Job-Cleanup ist nicht automatisch: alte Job-Eintraege (`completed`/`failed`) bleiben in der DB, bis jemand `python cli.py cleanup-jobs [--days 30] [--dry-run]` ausfuehrt (z.B. per Cron).

### Datenbank
- **SQLite** wird in Dev/Test verwendet. Fuer Produktion PostgreSQL empfohlen.
- Database-Provisioning (M18) erstellt Metadaten, verbindet sich aber nicht mit echten Datenbankservern.

### Auth / MFA
- MFA-Verifizierung ist implementiert, aber kein Recovery-Code-Flow fuer verlorene Authenticator-Apps.
- API-Key-Rotation erfordert manuelles Loeschen und Neuerstellen.

### Agent Maintenance
- Kein automatisches Drain: Bestehende Instances laufen weiter auf Maintenance-Agents.
- Der Admin-Transfer zwischen Agents loescht die Instance auf dem alten Node und legt sie auf dem Ziel-Node neu an. **Dateien werden dabei nicht uebertragen** (Datenverlust, wenn vorher keine Sicherung gezogen wurde).

### Abrechnung und Shop (Phase 4)
- **Keine Rechnungen, keine Umsatzsteuer:** Astra erstellt keine Rechnungen und weist keine USt aus. Preise sind Betraege in Cent ohne Netto/Brutto-Trennung. Rechnungsstellung muss ausserhalb geregelt werden.
- **Erstattungen manuell:** Astra erstattet nie automatisch; die Erstattung läuft im Stripe-Dashboard oder per Überweisung. Seit M59 reagiert Astra auf Stripe-Ereignisse dazu (`charge.refunded`, `charge.dispute.created/closed`): volle Erstattung der letzten Zahlung sperrt den Server und löscht ihn nach der Karenzzeit, Teilerstattungen und ältere Zahlungen lösen nur Alert und Event aus, Streitfälle sperren bis zum Ausgang. Beweise und Entscheidungen im Streitfall bleiben manuell, bei manueller Zahlung (`mark-paid`) und Überweisung gibt es keine Erstattungslogik. Löscht ein Kunde seinen Server selbst oder kündigt, gibt es keinen anteiligen Rest.
- **Keine Mehrwaehrung:** Jedes Produkt hat eine Waehrung, Astra rechnet nicht um und berichtet nicht ueber Waehrungen hinweg. Fuer Stripe nur Waehrungen mit Nachkommastellen (kein JPY, KRW usw.).
- **Keine Abonnements:** Stripe wird nur als Einmalzahlung (`mode=payment`) genutzt. Der Kunde verlaengert jede Laufzeit selbst; der Tick erinnert per Mail (`BILLING_REMINDER_DAYS`), sperrt bei Ablauf und loescht nach `BILLING_GRACE_DAYS`. Nur kostenlose Pakete verlaengern sich automatisch.
- **Stripe nur mit gemockten Aufrufen getestet:** Es gab nie einen echten Stripe-Aufruf. Vor dem Livegang einmal im Test-Modus mit Stripe CLI durchspielen (siehe `docs/orders-api.md`).
- **Wartezeit bei fehlendem Platz:** Ist nach einer Zahlung kein Node mit Platz frei, bleibt die Bestellung `awaiting_provisioning`. Der Billing-Tick stellt sie automatisch bereit, sobald Platz da ist (aelteste Zahlung zuerst, Laufzeit beginnt dann). Der Admin wird nicht aktiv benachrichtigt, sieht lange Wartezeiten aber im Preflight-Check `billing_waiting_orders` und in `GET /api/admin/billing/status` (`awaiting_provisioning`, Warnschwelle `BILLING_WAIT_WARN_HOURS`, Standard 24); sonst gibt es nur das Event `order:provision_failed` beim ersten Versuch. Der Kunde bekommt erst bei der Bereitstellung eine Mail.
- **Bestell-Mails:** Mails gibt es bei Zahlungseingang (Server bereit bzw. Hinweis auf Wartezeit), Verlängerung, Erinnerung, Überfälligkeit und Löschung; keine bei Anlegen einer Bestellung und keine bei kostenlosen Paketen. Es sind einfache Textmails ohne Rechnung. Ohne `MAIL_SERVER` werden Mails nur ins Log geschrieben.
- **Kapazitaet nach Zuweisung:** Die Kapazitaetspruefung rechnet mit den zugewiesenen Ressourcen der Instances (inkl. Overallocation des Agents), nicht mit der tatsaechlichen Auslastung. Die Zeilensperre gegen parallele Erstellungen wirkt nur auf PostgreSQL.
- **Missbrauchsschutz:** Registrierung hat Rate Limiting und optionale E-Mail-Verifizierung, aber keine Bot-Erkennung (CAPTCHA). Gratis-Pakete sind nur ueber `max_instances_per_user` begrenzt.
- **Tick-Betrieb:** Der Billing-Tick laeuft als Schleife im Compose-Service `billing`. Faellt er aus, werden weder Ablaeufe durchgesetzt noch Erinnerungen verschickt. Seit M53 erkennt das Panel das (`GET /api/admin/billing/status`, Preflight-Check `billing_tick`, Warnung nach `BILLING_TICK_MAX_AGE_MINUTES`, Standard 15). Seit M58 meldet Astra Ausfall, Fehler im Tick und lange wartende Bestellungen aktiv per Mail und/oder Webhook (`ADMIN_ALERT_EMAIL`, `ADMIN_ALERT_WEBHOOK_URL`, Container `alerts`). Ohne konfigurierten Kanal (Standard) bleibt es bei Status und Preflight. Die Meldung ist best effort: fällt der Mail-/Webhook-Dienst selbst aus, kommt nichts an; die Entprellung merkt sich nur den Zustand, nicht ob eine Nachricht zugestellt wurde.

### UI / Frontend
- Responsive Design: Kundenseiten (Dashboard, Server, Bestellungen, Konto, Shop) sind mobil nutzbar (Hamburger-Menue, Bestellungen als Karten); Admin-Tabellen scrollen auf kleinen Bildschirmen horizontal.
- File-Upload nur fuer Textdateien bis 1 MB (kein Multipart-Endpoint im Backend).
- Nicht alle Admin-Seiten verwenden bereits die neuen `PageLayout`/`StatusBadge`-Komponenten (schrittweise Migration).
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
- CSRF-Schutz ist ueber SameSite Cookies + JWT geloest, kein dedizierter CSRF-Token.
- Passwortwechsel und -reset machen neu ausgestellte JWTs sofort ungueltig (Claim `pwf`, Fingerabdruck des Passwort-Hashes); das Gerät, das das Passwort ändert, bekommt ein frisches Token. Noch vor M57 ausgestellte Tokens ohne diesen Claim gelten bis zu ihrem Ablauf (24 Stunden). Sonst gibt es weiterhin kein einzelnes Abmelden (kein Logout-Blocklisting) und API-Keys bleiben vom Passwortwechsel unberührt.
