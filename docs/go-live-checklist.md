# Go-live-Checkliste: Astrahost (astrahost.ch)

Reihenfolge für den ersten echten Betrieb. Jeder Punkt verweist auf den Abschnitt im
[Deploy-Runbook](deploy-runbook.md), der die Befehle enthält. Abhaken, was erledigt ist.

## A. Vorbereiten, solange die Domain noch registriert wird

- [ ] **Betreiberdaten** in `frontend/src/legal/operator.ts`: alle Platzhalter füllen, `jurisdiction: "CH"`,
      `brand: "Astrahost"` (sobald M75 drin ist). Bankverbindung und Hinweistext in `frontend/src/legal/payment.ts`.
- [ ] **Centauri**: Ubuntu/Debian aktuell, Docker + Compose installiert, SSH-Zugang mit Schlüssel,
      `sudo` ohne Passwortabfrage für den Deploy-Nutzer (Runbook 1).
- [ ] **Router**: feste öffentliche IP oder DynDNS; Weiterleitung von 80 und 443 (Panel), 8080 und 2022 (Wings),
      plus den Spielport-Bereich, z. B. 25565–25599 (Runbook 2).
- [ ] **Mailkonto** beim Domain-Anbieter anlegen (z. B. `noreply@astrahost.ch`), SMTP-Zugangsdaten notieren.
      Nach der Registrierung SPF und DKIM beim Anbieter aktivieren.
- [ ] **Stripe**: Konto anlegen, Testmodus, Währung CHF; Secret Key und später das Webhook-Secret notieren.
      Keys nur in die `.env` auf dem Server, nie in Chats oder ins Repo.
- [ ] **Cloudflare Turnstile** (optional): Site für `astrahost.ch` anlegen, Site Key und Secret notieren.
- [ ] **Discord-Webhook** (optional): Servereinstellungen → Integrationen → Webhooks → URL notieren.
- [ ] **Pakete planen**: Name, RAM, CPU, Speicher, Preis in CHF, Laufzeit 30 Tage; welche Spiele (Blueprints)
      zuerst. Eine Preisliste reicht, angelegt wird im Admin (Runbook 7).
- [ ] **Steuer**: Nicht MWST-pflichtig unter CHF 100'000 Umsatz → `VAT_RATE=0`. Sonst `VAT_RATE=8.1` und
      MWST-Nr. in `INVOICE_SELLER_VAT_ID` (Runbook 9b). Mit Treuhänder/Steuerberater bestätigen.

## B. Sobald astrahost.ch und astrahost.gg aktiv sind

- [ ] **DNS** (A-Records auf die öffentliche IP von Centauri):
      `astrahost.ch`, `www.astrahost.ch`, `node1.astrahost.ch`, `astrahost.gg`, `www.astrahost.gg`.
      Prüfen mit `dig +short astrahost.ch` von außerhalb des Heimnetzes.
- [ ] **`.env`** aus `.env.prod.example` erstellen (Runbook 3). Mindestens:
      `PANEL_DOMAIN=astrahost.ch`, `NODE_DOMAIN=node1.astrahost.ch`, `REDIRECT_DOMAINS=www.astrahost.ch,astrahost.gg,www.astrahost.gg`,
      `ACME_EMAIL`, `SECRET_KEY`/`JWT_SECRET_KEY`/`POSTGRES_PASSWORD`/`REDIS_PASSWORD` (jeweils `openssl rand -hex 32`),
      `ADMIN_*`, `SITE_NAME=Astrahost`, `INVOICE_COUNTRY=CH`, `VAT_RATE`, `INVOICE_SELLER` (Name, Adresse, CHE-Nummer),
      `MAIL_*`, `PAYMENT_PROVIDER=stripe` + `STRIPE_*`, optional `CAPTCHA_*`, `ADMIN_ALERT_WEBHOOK_URL`.
- [ ] **Panel starten** (Runbook 4) und `./scripts/smoke-test.sh https://astrahost.ch` ausführen.
- [ ] **Stripe-Webhook** in Stripe auf `https://astrahost.ch/api/payments/stripe` anlegen, Ereignisse aus Runbook 9a,
      Webhook-Secret in die `.env`, Container neu starten.
- [ ] **Agent + Wings** (Runbook 5 und 6): Node im Admin anlegen, `install-wings.sh` ausführen, Node zeigt „gesund“.
- [ ] **Blueprint und erstes Paket** (Runbook 7): z. B. Minecraft Paper, Paket „Start“ in CHF.

## C. Abnahme vor dem ersten Kunden

- [ ] Testkunde registrieren (Captcha und E-Mail-Bestätigung durchlaufen), Paket bestellen,
      mit Stripe-Testkarte `4242 4242 4242 4242` bezahlen → Server startet, Mail „Server ist bereit“ kommt an.
- [ ] Rechnung unter Bestellungen öffnen: Astrahost als Anbieter, CHE-Nummer, MWST-Hinweis, CHF-Format.
- [ ] Konsole, Dateien, Backup auf dem Testserver ausprobieren; Server stoppen und starten.
- [ ] Erstattung im Stripe-Testmodus auslösen → Gutschrift erscheint, Server wird nach Karenzzeit gesperrt.
- [ ] Admin-Übersicht: Abrechnungs-Tick „läuft“, Node gesund, Umsatz-Kachel zeigt die Testzahlung.
- [ ] Alert testen: `docker compose exec backend python cli.py alert-test` → Nachricht im Discord-Kanal.
- [ ] Backup einrichten (`scripts/backup.sh` per Cron) und einmal `restore.sh` auf einem Testpfad probieren.
- [ ] Rechtstexte unter `/impressum`, `/datenschutz`, `/agb` lesen: keine Platzhalter mehr, Captcha-Dienst genannt,
      falls aktiv. Juristische Prüfung der Vorlagen.
- [ ] Stripe vom Test- auf den Live-Modus umstellen (neue Keys, neuer Webhook), Testkunde löschen.

## D. Erste Wochen

- [ ] Monatlich: Rechnungen unter Admin → Rechnungen als CSV exportieren und ablegen (10 Jahre Aufbewahrung).
- [ ] Wöchentlich: `cleanup-jobs` läuft per Cron (Runbook 9), Backups vorhanden, Speicherplatz auf Centauri prüfen.
- [ ] Bei Wachstum: zweiter Node (Runbook 5 für eine weitere Maschine) oder Umzug (Runbook 10).
