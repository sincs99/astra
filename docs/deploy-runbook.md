# Deploy-Runbook: Astra auf einem eigenen Server (Centauri / Fire)

> Ziel: Panel **und** erster Wings-Node auf einer Maschine, TLS automatisch über Caddy,
> so gebaut, dass der spätere Umzug auf einen gemieteten Server nur ein DNS-Wechsel ist.
> Geschätzte Dauer beim ersten Mal: 60 bis 90 Minuten.

---

## 0. Was du brauchst

| Punkt | Warum |
|---|---|
| Linux-Server (Debian 12 / Ubuntu 22.04+), 4 vCPU, 8 GB RAM, 40 GB frei | Panel ~1 GB, Rest für Gameserver |
| Öffentliche IPv4 oder Portweiterleitung vom Router | Kunden und Wings müssen das Panel erreichen |
| Eine Domain mit zwei A-Records: `panel.deinedomain.de` und `node1.deinedomain.de` | TLS und späterer Umzug ohne IP-Änderung |
| Optional: Weiterleitungs-Domains (z.B. `www.deinedomain.de`, Zweitdomain `deinedomain.gg`) mit A-Records auf denselben Server | Besucher landen per 301 auf dem Panel, siehe Abschnitt 3 |
| Offene eingehende Ports: 80, 443 (Caddy), 2022 (SFTP), 25565–25600 (Gameserver) | Siehe Abschnitt 2 |
| Root-Zugang per SSH | Docker, Wings, systemd |

Hinter einem Heimrouter: Ports 80, 443, 2022 und den Gameserver-Bereich auf den Server weiterleiten, DynDNS für die Domain nutzen. Läuft unverändert, nur die Uptime hängt an deiner Leitung.

---

## 1. Server vorbereiten

```bash
apt update && apt upgrade -y
apt install -y git curl ufw
timedatectl set-timezone Europe/Zurich
```

Docker:

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version   # muss v2.x melden
```

---

## 2. Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 2022/tcp              # SFTP (Wings)
ufw allow 25565:25600/tcp       # Gameserver-Ports (Endpoints)
ufw allow 25565:25600/udp       # falls Spiele UDP brauchen
ufw enable
```

Port 8080 (Wings-API) bleibt **geschlossen**: Caddy spricht Wings lokal über `host.docker.internal:8080` an, von außen läuft alles über `https://node1.deinedomain.de`.

---

## 3. Astra holen und konfigurieren

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/sincs99/astra.git
cd astra
cp .env.prod.example .env
```

In `.env` setzen:

```env
PANEL_DOMAIN=panel.deinedomain.de
NODE_DOMAIN=node1.deinedomain.de
REDIRECT_DOMAINS=                       # optional, siehe unten
ACME_EMAIL=du@deinedomain.de
SECRET_KEY=<python3 -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<ebenso>
POSTGRES_PASSWORD=<ebenso>
REDIS_PASSWORD=<ebenso>
ADMIN_USERNAME=admin
ADMIN_EMAIL=du@deinedomain.de
ADMIN_PASSWORD=<starkes Passwort, nach dem ersten Login ändern>
```

`REGISTRATION_ENABLED` bleibt vorerst `false`. Mail kann leer bleiben, dann werden Mails nur geloggt.

---

### Weiterleitungs-Domains (optional)

Wenn das Panel unter einer Marke läuft (z. B. `panel.astrahost.ch`) und weitere Adressen auf dasselbe Panel führen sollen, trägst du sie kommagetrennt in `REDIRECT_DOMAINS` ein, zum Beispiel `www.astrahost.ch,astrahost.gg,www.astrahost.gg`. `scripts/deploy.sh` erzeugt daraus `deploy/sites/redirect.caddy`; Caddy holt für jede Domain ein Zertifikat und leitet per **301** auf `https://PANEL_DOMAIN` weiter, Pfad und Query bleiben erhalten (`https://astrahost.gg/konto?x=1` → `https://panel.astrahost.ch/konto?x=1`). Leer = keine Weiterleitung. `deploy.sh` bricht ab, wenn ein Eintrag kein Domainname ist oder `PANEL_DOMAIN`/`NODE_DOMAIN` enthält.

DNS-Einträge (alle auf die IP des Servers, vor dem Start setzen, sonst scheitert die Zertifikatsausstellung):

| Name | Typ | Ziel | Zweck |
|---|---|---|---|
| `panel.astrahost.ch` | A (und AAAA) | Server-IP | Panel (`PANEL_DOMAIN`) |
| `node1.astrahost.ch` | A | Server-IP | Wings-Node (`NODE_DOMAIN`) |
| `www.astrahost.ch` | A oder CNAME auf `panel.astrahost.ch` | Server-IP | Weiterleitung |
| `astrahost.gg` | A | Server-IP | Weiterleitung (Zweitdomain) |
| `www.astrahost.gg` | A oder CNAME auf `astrahost.gg` | Server-IP | Weiterleitung |

Prüfen nach dem Start: `REDIRECT_DOMAINS="www.astrahost.ch,astrahost.gg" ./scripts/smoke-test.sh https://panel.astrahost.ch` (erwartet je Domain 301 mit passender `Location`).

---

## 4. Panel starten

```bash
./scripts/deploy.sh --bootstrap
```

Das Skript baut die Images, startet Caddy, Postgres, Redis, Backend, Worker, Billing-Tick und Frontend, wartet bis die Migrationen durch sind und legt den Admin an. Caddy holt beim ersten Aufruf das Let's-Encrypt-Zertifikat, das dauert bis zu einer Minute.

Prüfen:

```bash
./scripts/smoke-test.sh https://panel.deinedomain.de admin '<ADMIN_PASSWORD>'
```

Alle Zeilen müssen `OK` sein. Danach im Browser `https://panel.deinedomain.de` öffnen, einloggen, Passwort ändern.

Logs bei Problemen:

```bash
docker compose logs -f backend caddy
```

---

## 5. Agent (Node) im Panel anlegen

Im Panel unter **Admin → Agents → Neuer Agent**:

| Feld | Wert | Warum |
|---|---|---|
| Name | `node1` | frei |
| FQDN | `node1.deinedomain.de` | muss zum DNS und zu `NODE_DOMAIN` passen |
| Schema | `https` | Caddy terminiert TLS |
| Connect-Port | `443` | Port, über den das Panel Wings erreicht (Caddy) |
| Listen-Port | `8080` | Port, auf dem Wings lokal lauscht |
| SFTP-Port | `2022` | |
| Datenverzeichnis | `/var/lib/astra/volumes` | Standard für neue Nodes. Nodes mit `/var/lib/pterodactyl/volumes` bzw. `/var/lib/pelican/volumes` behalten ihre alten Namen (siehe unten) |
| Hinter Reverse Proxy | **an** | Wings ohne eigenes SSL, Caddy davor |

**Namen auf dem Node (White-Label, M78):** Für neue Nodes setzt der Konfig-Export eigene Namen: `system.root_directory: /var/lib/astra`, Daten `/var/lib/astra/volumes`, Archive `/var/lib/astra/archives`, Backups `/var/lib/astra/backups`, Logs `/var/log/astra`, temporär `/tmp/astra`, Systembenutzer `astra`, Docker-Netz `astra_nw`; `install-wings.sh` legt die Konfiguration unter `/etc/astra/config.yml` ab und startet Wings mit `wings --config /etc/astra/config.yml`. **Bestehende Nodes laufen unverändert weiter:** ein Agent, dessen Datenverzeichnis unter `/var/lib/pterodactyl` (oder `/var/lib/pelican`) liegt, bekommt im Export weiterhin die alten Pfade, den alten Benutzer und das alte Netz, damit Backups und Archive nicht auseinanderlaufen. Nur neue Installationen bekommen die `astra`-Namen. Wer einen bestehenden Node umstellen will, ändert das Datenverzeichnis des Agents bewusst (Daten vorher verschieben) und führt `install-wings.sh` erneut aus. Bekannte Einschränkung: der Konsolen-Prompt `container@pterodactyl~` stammt aus den yolks-Images und lässt sich nur mit eigenen Images ändern.

Beim Anlegen erzeugt Astra die Node-Credentials (Token-ID sichtbar, Secret nur in der config.yml).
Alle Felder lassen sich später über *Bearbeiten* ändern.

Dann **Endpoints** anlegen: Agent `node1`, IP `0.0.0.0`, Port-Bereich `25565-25600`
(ein Endpoint = ein Gameserver-Port; der Bereich wird in einem Schritt angelegt, vorhandene
Ports werden übersprungen). Per API: `POST /api/admin/agents/1/endpoints/bulk` mit
`{"ip": "0.0.0.0", "port_start": 25565, "port_end": 25600}`.

Für die Skripte in Abschnitt 6 brauchst du einen Admin-Token:

```bash
TOKEN=$(curl -s -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<PW>"}' https://panel.deinedomain.de/api/auth/login \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

---

## 6. Wings auf demselben Server installieren

```bash
cd /opt/astra
sudo ./scripts/install-wings.sh --panel https://panel.deinedomain.de --agent-id 1 --token "$TOKEN"
```

Das Skript installiert Wings, holt die `config.yml` direkt aus dem Panel (Node-Token, `remote`, Ports), legt den systemd-Dienst an und startet ihn. Für Pelican-Wings `--pelican` anhängen.

Das Skript ändert nichts still am System: **Docker** installiert es nur mit `--install-docker` (sonst bricht es mit einem Hinweis ab, wenn Docker fehlt), die **GRUB-Option `swapaccount=1`** setzt es nur mit `--grub-swapaccount` (nur auf Systemen mit cgroup v1 nötig, auf Ubuntu 22.04+ nicht; wirkt nach einem Reboot). `--no-docker` ist veraltet und ohne Wirkung. 
**Panel und Wings auf demselben Host:** Docker Compose legt für das Panel ein eigenes Netz an (`astra_default`, meist `172.18.0.0/16`), und `172.18.0.0/16` ist zugleich der Standard von Wings. Dann bricht Wings mit „Pool overlaps with other one on this address space“ ab. Astra vermeidet das: der Konfig-Export setzt für Wings ein eigenes Docker-Netz (`docker.network.interfaces.v4` auf `172.30.0.0/16`, Gateway `172.30.0.1`; änderbar über `WINGS_DOCKER_SUBNET` in der `.env` des Panels). Das Installationsskript vergleicht das Subnetz aus der `config.yml` mit den vorhandenen Docker-Netzen (`docker network ls/inspect`) und warnt bei einer Überlappung. Ist Wings schon mit dem alten Netz gescheitert: Skript erneut ausführen (holt die neue `config.yml`) und das angelegte, leere Netz `pterodactyl_nw` mit `docker network rm pterodactyl_nw` entfernen.

Auf einem frischen Server also: `sudo ./scripts/install-wings.sh --install-docker --panel ... --agent-id 1 --token "$TOKEN"`.

Prüfen:

```bash
journalctl -u wings -n 20 --no-pager      # keine 401/403 gegen das Panel
./scripts/smoke-test.sh https://panel.deinedomain.de admin '<PW>'   # Agent-Zeilen OK
curl -s https://node1.deinedomain.de/api/system    # 401 = Caddy→Wings funktioniert (Auth fehlt absichtlich)
```

Im Panel unter **Admin → Fleet Monitoring** muss `node1` jetzt `healthy` sein und `daemon_version`
die Wings-Version zeigen (z. B. `v1.13.3`). Steht dort `stub`, läuft das Backend mit
`RUNNER_ADAPTER=stub` (Standard im Entwicklungs-Compose): Der Agent wirkt dann gesund, Wings wird
aber nie angesprochen. In `.env` muss `RUNNER_ADAPTER=wings` stehen (so in `.env.prod.example`).

---

## 7. Blueprint und erster Server

Blueprints (Server-Vorlagen) kommen am schnellsten per Egg-Import. Im Repo liegt ein fertiges
Paper-Egg (`blueprints/minecraft-paper.json`, Pterodactyl-Format PTDL_v2). Das Install-Script lädt die Jar über die PaperMC-Fill-API (v3), prüft, dass wirklich ein Jar (ZIP) mit passender Prüfsumme ankommt, und bricht sonst mit Fehler ab (der Install meldet dann nicht `ready`). Es schreibt **kein** `eula.txt`: die Minecraft-EULA muss der Kunde selbst akzeptieren (siehe Ablauf unten):

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  --data @blueprints/minecraft-paper.json \
  https://panel.deinedomain.de/api/admin/blueprints/import
```

Alternativ im Panel unter **Admin → Blueprints → Import** das JSON einfügen, oder jedes andere
Egg aus [pterodactyl/eggs](https://github.com/pterodactyl/eggs) bzw. [pelican-eggs](https://github.com/pelican-eggs)
auf demselben Weg importieren. Image, Startup, Install-Script, Startup-Erkennung, Stop-Befehl,
Variablen und `server.properties`-Platzhalter werden übernommen.

Wer den Blueprint von Hand anlegen will, braucht mindestens: Docker-Image
`ghcr.io/pterodactyl/yolks:java_25` (für Paper 26.x, für Versionen bis 1.21 `java_21`), Startup-Befehl mit `{{SERVER_JARFILE}}`, Install-Container
`ghcr.io/pterodactyl/installers:debian`, Stop-Befehl `stop`, Startup-Erkennung `)! For help, type `
und ein Install-Script, das die Paper-Jar nach `/mnt/server` lädt (ohne `eula.txt`).
Details zu den Feldern: `docs/wings-remote-api.md`.

Dann unter **Admin → Instances** eine Instanz anlegen: Blueprint Paper, Agent node1, 2048 MB RAM, 5120 MB Disk, Endpoint 25565. Ablauf, den du beobachten kannst:

1. Instanz steht auf `provisioning`, Wings holt `GET /api/remote/servers/{uuid}/install`.
2. Install-Container läuft, lädt Paper, meldet `POST .../install` → Status `ready`.
3. Start über die Konsole. Beim **ersten Start** beendet sich Paper mit „You need to agree to the EULA“, weil `eula.txt` mit `eula=false` entsteht. Der Kunde setzt im Dateimanager (**Dateien**) in `eula.txt` den Wert `eula=true` (oder in der Konsole `echo eula=true > eula.txt`, falls die Konsole Shell-Befehle erlaubt) und startet den Server erneut. Danach geht der Container-Status `starting` → nach der Zeile `)! For help, type ` → `running`.
4. Mit dem Minecraft-Client auf die Adresse verbinden, die die Instanz-Detailseite unter
   *Verbindung* anzeigt (`node1.deinedomain.de:25565`, Kopier-Button).

### Spiele mit mehreren Ports

Manche Spiele brauchen mehr als einen Port, zum Beispiel V Rising (Spiel 9876 und Query 9877, beide UDP). Eine Instanz kann deshalb mehrere Endpoints haben; Wings veröffentlicht alle als Port-Mappings des Containers.

1. Endpoints für beide Ports auf dem Agent anlegen (Abschnitt 5, z. B. Bereich `9876-9877`).
2. Instanz mit dem ersten Endpoint anlegen. Das ist der **primäre** Endpoint: seine IP und sein Port werden als `SERVER_IP` und `SERVER_PORT` an den Server übergeben und erscheinen unter *Verbindung*.
3. Weitere Endpoints zuweisen (Admin-API; die Antwort ist die Instanz mit der Liste `endpoints: [{id, ip, port, is_primary}]`, primärer zuerst):
   - `POST /api/admin/instances/<uuid>/endpoints` mit `{"endpoint_id": 13}` weist einen freien, nicht gesperrten Endpoint desselben Agents zu (409, wenn er zu einem anderen Agent gehört, gesperrt oder schon vergeben ist)
   - `DELETE /api/admin/instances/<uuid>/endpoints/<endpoint_id>` gibt einen Endpoint wieder frei (er wird nicht gelöscht; der primäre Endpoint lässt sich nicht entfernen, erst den primären wechseln)
   - `PATCH /api/admin/instances/<uuid>/endpoints/<endpoint_id>/primary` macht einen zugewiesenen Endpoint zum primären (`SERVER_PORT` und *Verbindung* wechseln)
4. **Egg-Variablen setzen:** Astra übergibt dem Server nur `SERVER_IP` und `SERVER_PORT` (wie das Referenz-Panel). Variablen wie `QUERY_PORT` werden nicht automatisch gesetzt: beim Instance die Variable auf **denselben Port** wie den zweiten Endpoint stellen (V Rising: `QUERY_PORT=9877`). Die Mappings reichen für das Port-Publishing, das Egg muss den Port nur selbst kennen.
5. **Server neu starten.** Astra synchronisiert die Konfiguration nach jeder Änderung sofort zu Wings (Antwortfeld `sync`), Wings veröffentlicht neue Ports aber erst beim Erstellen des Containers: Portänderungen wirken erst nach einem Neustart (Antwortfeld `restart_required`). Auch die Firewall muss die Ports (und bei UDP-Spielen das Protokoll UDP) freigeben.

---

## 8. Abnahme-Checkliste (Phase 2 fertig, wenn alles abgehakt)

- [ ] `smoke-test.sh` komplett OK, inklusive Agent-Zeilen
- [ ] Fleet Monitoring: Agent `healthy`
- [ ] Instanz erstellt → `ready` ohne Eingriff
- [ ] Konsole zeigt Live-Ausgabe, Start/Stop/Restart funktionieren
- [ ] Spieler kann joinen
- [ ] Datei-Browser listet `/mnt/server`, Datei bearbeiten funktioniert
- [ ] SFTP-Login mit `admin.<kurz-uuid>` auf Port 2022 (Passwort oder SSH-Key)
- [ ] Backup erstellen → nach wenigen Sekunden `is_successful = true` (Remote-Callback)
- [ ] Server-Neustart (`reboot`): alle Container kommen wieder, Wings meldet sich, Instanzen laufen
- [ ] `./scripts/backup.sh` erzeugt ein Archiv; Restore einmal auf einer Testinstanz geprüft

---

## 9. Betrieb

| Aufgabe | Befehl |
|---|---|
| Update einspielen | `cd /opt/astra && git pull && ./scripts/deploy.sh` |
| Status | `./scripts/deploy.sh --status` |
| Logs | `docker compose logs -f backend` / `journalctl -u wings -f` |
| Backup (täglich per Cron) | `0 3 * * * cd /opt/astra && ./scripts/backup.sh >> /var/log/astra-backup.log 2>&1` |
| Alte Job-Einträge aufräumen (wöchentlich per Cron) | `0 4 * * 0 cd /opt/astra && docker compose exec -T backend python cli.py cleanup-jobs --days 30 >> /var/log/astra-cleanup.log 2>&1` (löscht nur `completed`/`failed` älter als 30 Tage; `--dry-run` zählt nur) |
| Node-Credentials rotieren | Panel → Agent → *Credentials rotieren*, dann `install-wings.sh` erneut ausführen |
| Billing-Tick manuell | `docker compose exec backend python cli.py billing-tick` (läuft sonst automatisch alle 5 Minuten im Container `billing`) |
| Läuft der Billing-Tick? | `curl -s -H "Authorization: Bearer $TOKEN" https://panel.deinedomain.de/api/admin/billing/status` → `healthy` muss `true` sein, sobald es Bestellungen gibt. Auch im Preflight (`python cli.py preflight`, Check `billing_tick`) und im Smoke-Test. Schwelle: `BILLING_TICK_MAX_AGE_MINUTES` (Standard 15) |
| Markenname festlegen (vor dem ersten Kunden) | `.env`: `SITE_NAME=Astrahost` (Mail-Betreffe, Absendername, Rechnungskopf, Admin-Alerts) und `MFA_ISSUER_NAME=Astrahost` (Name im Authenticator-Eintrag). **`MFA_ISSUER_NAME` vor dem ersten Kunden setzen, danach nicht mehr ändern**, sonst passen bestehende Authenticator-Einträge nicht mehr zum Namen. `SITE_NAME` darf später geändert werden, alte Rechnungen behalten ihren Namen |
| Steuer konfigurieren (vor dem Echtbetrieb) | `.env`: `VAT_RATE` (0 = Kleinunternehmer, sonst z. B. 19; Preise sind Bruttopreise), `INVOICE_SELLER` (Name und Anschrift), `INVOICE_SELLER_VAT_ID`, `RECEIPT_FOOTER`, dann `./scripts/deploy.sh`. Der Satz wird beim Ausstellen in die Rechnung geschrieben, spätere Änderungen betreffen nur neue Rechnungen. Rechnungen über 250 € brutto und B2B sind nicht abgedeckt. **Mit dem Steuerberater abstimmen**; Details `docs/orders-api.md` → Rechnungen |
| Rechnungen für die Buchhaltung exportieren | `curl -s -H "Authorization: Bearer $TOKEN" "https://panel.deinedomain.de/api/admin/invoices?from=2026-10-01&to=2026-10-31&format=csv" -o rechnungen-2026-10.csv` (Semikolon, UTF-8 mit BOM, öffnet in Excel) |
| CAPTCHA aktivieren (optional) | Konto bei Cloudflare Turnstile oder hCaptcha anlegen, `CAPTCHA_PROVIDER`, `CAPTCHA_SITE_KEY`, `CAPTCHA_SECRET` in `.env`, `./scripts/deploy.sh`. **Vorher die Datenschutzerklärung ergänzen** (externer Dienst, Widget lädt Skripte des Anbieters), Details in `docs/operations.md` → Registrierungsschutz |
| Admin-Benachrichtigung testen | `docker compose exec backend python cli.py alert-test` schickt eine Testnachricht an `ADMIN_ALERT_EMAIL` und `ADMIN_ALERT_WEBHOOK_URL` (Exit 1, wenn kein Kanal gesetzt). Der Container `alerts` prüft alle 5 Minuten Tick-Ausfall, Tick-Fehler und zu lange wartende Bestellungen; Zahlungs-Mismatch meldet der Webhook direkt |

---

## 9a. Zahlungen (Phase 4)

Standard ist `PAYMENT_PROVIDER=manual`: Kunden bestellen, überweisen, der Admin klickt unter
**Admin → Bestellungen** auf *Als bezahlt markieren*. Dafür ist kein Zahlungskonto nötig.

Online-Zahlung per Stripe:

1. Stripe-Konto anlegen, im Dashboard zuerst den **Test-Modus** verwenden.
2. In `.env`: `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_…`, danach Webhook im Stripe-Dashboard
   anlegen: URL `https://panel.deinedomain.de/api/payments/stripe`, Ereignisse
   `checkout.session.completed`, `checkout.session.async_payment_succeeded` sowie (seit M59, für Erstattungen und
   Zahlungsstreitigkeiten) `charge.refunded`, `charge.dispute.created` und `charge.dispute.closed`. Ohne die drei
   letzten bleibt ein erstatteter Server aktiv. Das dort angezeigte
   Signing Secret als `STRIPE_WEBHOOK_SECRET=whsec_…` eintragen.
3. `./scripts/deploy.sh` (Backend-Image wird neu gebaut, das Stripe-Paket ist Teil davon).
4. Mit einer Testbestellung und der Stripe-Testkarte `4242 4242 4242 4242` durchspielen:
   Kunde klickt *Jetzt bezahlen*, kommt nach `/orders?paid=…` zurück, der Webhook stellt den Server bereit.
   Lokal lässt sich der Webhook mit der Stripe CLI nachstellen (`stripe listen --forward-to …`).
5. Erst nach erfolgreichem Testlauf auf die Live-Schlüssel wechseln.

Erstattungen und Streitfälle (M59): Eine volle Erstattung der letzten Zahlung setzt die Bestellung auf
`refunded`, sperrt den Server und löscht ihn nach `BILLING_GRACE_DAYS`; der Kunde bekommt eine Mail. Teilerstattungen
und ein offener Dispute sperren nur bzw. melden nur, der Admin entscheidet. Alles davon kommt als Admin-Alert (M58)
und als Activity-Event `order:refunded` / `order:disputed` an. Erstattungen selbst löst Astra nie aus, das bleibt
im Stripe-Dashboard.

Betrieb: Bestellungen mit Status `mismatch` oder Activity-Events `order:payment_unapplied` bedeuten,
dass Geld eingegangen ist, aber nichts freigeschaltet wurde (Betrag oder Währung passten nicht, oder die
Bestellung war schon storniert). Diese Fälle im Stripe-Dashboard prüfen und ggf. erstatten. Die
Zahlungsereignisse samt Klartext-Grund liefert das Panel unter
`GET /api/admin/payment-events?status=mismatch` bzw. `?status=unapplied` (Admin-Login, Filter auch
`order_uuid` und `limit`):

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://panel.deinedomain.de/api/admin/payment-events?status=mismatch"
```

Abgelaufene Bestellungen sperrt der Billing-Tick, nach `BILLING_GRACE_DAYS` löscht er den Server;
`BILLING_REMINDER_DAYS` Tage vorher geht eine Erinnerung per Mail (nur mit konfiguriertem `MAIL_SERVER`).
Fällt der Container `billing` aus, passiert nichts davon mehr. Das Panel merkt das selbst: `GET /api/admin/billing/status`
liefert `healthy=false`, sobald Bestellungen auf den Tick warten und der letzte Lauf älter als
`BILLING_TICK_MAX_AGE_MINUTES` ist; der Preflight und `scripts/smoke-test.sh` prüfen dasselbe. Eine aktive
Aktive Benachrichtigung (seit M58): In `.env` `ADMIN_ALERT_EMAIL` (braucht `MAIL_SERVER`) und/oder
`ADMIN_ALERT_WEBHOOK_URL` setzen. Für Discord: Server-Einstellungen → Integrationen → Webhooks → neue URL kopieren;
für Slack eine Incoming-Webhook-URL. Danach `./scripts/deploy.sh` (startet den Container `alerts` mit) und
`docker compose exec backend python cli.py alert-test`. Eine anhaltende Störung wird höchstens alle
`ADMIN_ALERT_COOLDOWN_MINUTES` (Standard 360) wiederholt, die Entwarnung kommt einmal. Zusätzlich lohnt ein
externer Monitor (z.B. Uptime Kuma mit Keyword `"healthy": true` auf `/api/admin/billing/status`), falls das
Panel selbst ausfällt.

Details zu Endpunkten, Status und Stripe-Einrichtung: `docs/orders-api.md`.

---

## 9b. Betrieb in der Schweiz (M74)

Für eine Einzelfirma in der Schweiz in der `.env`:

```
INVOICE_COUNTRY=CH
VAT_RATE=0                       # 8.1 bei MWST-Pflicht
INVOICE_SELLER="Max Muster\nBahnhofstrasse 1\n8000 Zuerich"
INVOICE_SELLER_VAT_ID=CHE-123.456.789 MWST   # nur wenn MWST-pflichtig
```

Produkte legst du im Admin mit der Währung `CHF` an (Preise sind Bruttopreise). Auf der Rechnung steht dann „MWST“ statt „Umsatzsteuer“, „MWST-Nr.“ statt „USt-IdNr.“ und ohne MWST-Pflicht der Hinweis „Nicht mehrwertsteuerpflichtig (Art. 10 Abs. 2 lit. a MWSTG)“ (englisch: „Not subject to Swiss VAT …“). Beträge erscheinen in Mails und Belegen als `CHF 1'234.56` (englisch `CHF 1,234.56`); der CSV-Export bleibt bei reinen Zahlen. Das Land wird mit jeder Rechnung gespeichert: ein späterer Wechsel von `INVOICE_COUNTRY` ändert alte Belege nicht.

- **MWST-Pflicht** beginnt ab CHF 100'000 Umsatz pro Jahr (weltweit, ohne Befreiung); dann `VAT_RATE=8.1` setzen und die MWST-Nr. eintragen. Satz und Pflicht vorher mit Treuhänder oder ESTV klären.
- **Stripe** unterstützt CHF; das Stripe-Konto muss dafür eingerichtet sein, die Webhooks sind unverändert.
- **Aufbewahrung:** Rechnungen sind 10 Jahre aufzubewahren. Den Export `GET /api/admin/invoices?format=csv` einmal im Monat sichern (siehe Abschnitt 9) und zusammen mit den Datenbank-Backups ablegen.
- Nicht enthalten: QR-Rechnung und E-Rechnung (siehe `docs/known-limitations.md`).

---

## 10. Umzug auf einen gemieteten Server

Weil alles über Domains läuft, ist der Umzug ein Restore:

1. Neuen Server nach Abschnitt 1–3 vorbereiten, `.env` kopieren.
2. Auf dem alten Server `./scripts/backup.sh`, Archiv kopieren, auf dem neuen `./scripts/restore.sh <archiv>`.
3. `./scripts/deploy.sh` (ohne `--bootstrap`).
4. Gameserver: Instanz-Daten liegen unter dem Datenverzeichnis von Wings. Entweder mitkopieren (rsync) oder im Panel einen zweiten Agent anlegen und die Instanzen per **Transfer** verschieben.
5. DNS-A-Records von `panel.` und `node1.` auf die neue IP. Caddy holt neue Zertifikate selbst.

Panel und Node können ab dann auch getrennt laufen: kleiner VPS für das Panel, dicker Root-Server als Node. Dafür `NODE_DOMAIN` auf dem Panel leer lassen und auf dem Node Wings mit eigenem Let's-Encrypt-Zertifikat betreiben (`behind_proxy` aus, Caddy nur noch für das Panel).

---

## 11. Fehlersuche

| Symptom | Prüfen |
|---|---|
| `curl https://panel…/health` schlägt fehl | `docker compose logs caddy`: DNS zeigt auf den Server? Ports 80/443 offen? |
| Wings-Log `401`/`403` | Token in `config.yml` ≠ Agent im Panel → `install-wings.sh` erneut ausführen |
| Agent bleibt `unreachable` | Wings erreicht `remote` nicht: `curl https://panel…/api/remote/servers` vom Node aus muss 401 liefern |
| Agent `healthy`, aber kein Container entsteht | Fleet Monitoring zeigt `daemon_version: stub` → Backend läuft mit `RUNNER_ADAPTER=stub`, in `.env` auf `wings` stellen und Backend neu starten |
| Instanz hängt in `provisioning` | `journalctl -u wings`: Install-Container-Fehler, Docker-Image-Pull, Netzwerk |
| Backend-Container: `exec: "./entrypoint.sh": permission denied` | Checkout ohne Ausführrecht (ältere Klone, Windows): `git pull`, oder `chmod +x backend/entrypoint.sh`; das Dev-Compose startet das Script seit M78 über `bash` |
| Server bleibt `starting` | Startup-Erkennung im Blueprint passt nicht zur Konsolenausgabe |
| Konsole lädt nicht | Browser erreicht `wss://node1…/api/servers/<uuid>/ws`? Caddy-Site `deploy/sites/node.caddy` vorhanden? |
| Spieler können nicht joinen | Firewall-Port, Endpoint-Port = Port in `server.properties` (Platzhalter im Blueprint) |

Weitere Details zur Wings-Anbindung: `docs/wings-remote-api.md`.
