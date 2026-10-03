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
- Kein automatisches Job-Cleanup (alte Jobs bleiben in DB).

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
- **Keine Erstattungen:** Astra erstattet nie automatisch. Erstattungen laufen manuell (Stripe-Dashboard oder Ueberweisung) und werden in Astra nicht nachvollzogen; Stripe-Ereignisse zu Erstattungen und Zahlungsstreitigkeiten (`charge.refunded`, Disputes) werden nicht ausgewertet, ein erstatteter Server bleibt aktiv. Loescht ein Kunde seinen Server selbst oder kuendigt, gibt es keinen anteiligen Rest.
- **Keine Mehrwaehrung:** Jedes Produkt hat eine Waehrung, Astra rechnet nicht um und berichtet nicht ueber Waehrungen hinweg. Fuer Stripe nur Waehrungen mit Nachkommastellen (kein JPY, KRW usw.).
- **Keine Abonnements:** Stripe wird nur als Einmalzahlung (`mode=payment`) genutzt. Der Kunde verlaengert jede Laufzeit selbst; der Tick erinnert per Mail (`BILLING_REMINDER_DAYS`), sperrt bei Ablauf und loescht nach `BILLING_GRACE_DAYS`. Nur kostenlose Pakete verlaengern sich automatisch.
- **Stripe nur mit gemockten Aufrufen getestet:** Es gab nie einen echten Stripe-Aufruf. Vor dem Livegang einmal im Test-Modus mit Stripe CLI durchspielen (siehe `docs/orders-api.md`).
- **Bereitstellung nach Zahlung ist nicht automatisch wiederholbar:** Ist nach einer Zahlung kein Node mit Platz frei, bleibt die Bestellung `awaiting_provisioning`, bis ein Admin Platz schafft und `mark-paid` erneut aufruft. Es gibt keine automatische Wiederholung und keine Benachrichtigung des Admins ausser dem Event `order:provision_failed`.
- **Bestell-Mails:** Mails gibt es nur bei Erinnerung, Ueberfaelligkeit und Loeschung. Es gibt keine Bestaetigungsmail beim Anlegen oder Bezahlen einer Bestellung. Ohne `MAIL_SERVER` werden Mails nur ins Log geschrieben.
- **Kapazitaet nach Zuweisung:** Die Kapazitaetspruefung rechnet mit den zugewiesenen Ressourcen der Instances (inkl. Overallocation des Agents), nicht mit der tatsaechlichen Auslastung. Die Zeilensperre gegen parallele Erstellungen wirkt nur auf PostgreSQL.
- **Missbrauchsschutz:** Registrierung hat Rate Limiting und optionale E-Mail-Verifizierung, aber keine Bot-Erkennung (CAPTCHA). Gratis-Pakete sind nur ueber `max_instances_per_user` begrenzt.
- **Tick-Betrieb:** Der Billing-Tick laeuft als Schleife im Compose-Service `billing`. Ohne laufenden Tick werden weder Ablaeufe durchgesetzt noch Erinnerungen verschickt; es gibt keine Ueberwachung dafuer ausser dem Container-Status und dem Exit-Code von `billing-tick`.

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
- Ausgestellte JWTs bleiben nach einem Passwortwechsel bis zu ihrem Ablauf gueltig (kein Abmelden anderer Geraete).
