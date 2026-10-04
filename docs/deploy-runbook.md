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
| Datenverzeichnis | `/var/lib/pterodactyl/volumes` | Pelican: `/var/lib/pelican/volumes` |
| Hinter Reverse Proxy | **an** | Wings ohne eigenes SSL, Caddy davor |

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

Prüfen:

```bash
journalctl -u wings -n 20 --no-pager      # keine 401/403 gegen das Panel
./scripts/smoke-test.sh https://panel.deinedomain.de admin '<PW>'   # Agent-Zeilen OK
curl -s https://node1.deinedomain.de/api/system    # 401 = Caddy→Wings funktioniert (Auth fehlt absichtlich)
```

Im Panel unter **Admin → Fleet Monitoring** muss `node1` jetzt `healthy` sein.

---

## 7. Blueprint und erster Server

Blueprints (Server-Vorlagen) kommen am schnellsten per Egg-Import. Im Repo liegt ein fertiges
Paper-Egg (`blueprints/minecraft-paper.json`, Pterodactyl-Format PTDL_v2):

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
`ghcr.io/pterodactyl/yolks:java_21`, Startup-Befehl mit `{{SERVER_JARFILE}}`, Install-Container
`ghcr.io/pterodactyl/installers:debian`, Stop-Befehl `stop`, Startup-Erkennung `)! For help, type `
und ein Install-Script, das die Paper-Jar nach `/mnt/server` lädt und `eula=true` schreibt.
Details zu den Feldern: `docs/wings-remote-api.md`.

Dann unter **Admin → Instances** eine Instanz anlegen: Blueprint Paper, Agent node1, 2048 MB RAM, 5120 MB Disk, Endpoint 25565. Ablauf, den du beobachten kannst:

1. Instanz steht auf `provisioning`, Wings holt `GET /api/remote/servers/{uuid}/install`.
2. Install-Container läuft, lädt Paper, meldet `POST .../install` → Status `ready`.
3. Start über die Konsole, Container-Status `starting` → nach der Zeile `)! For help, type ` → `running`.
4. Mit dem Minecraft-Client auf die Adresse verbinden, die die Instanz-Detailseite unter
   *Verbindung* anzeigt (`node1.deinedomain.de:25565`, Kopier-Button).

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

---

## 9a. Zahlungen (Phase 4)

Standard ist `PAYMENT_PROVIDER=manual`: Kunden bestellen, überweisen, der Admin klickt unter
**Admin → Bestellungen** auf *Als bezahlt markieren*. Dafür ist kein Zahlungskonto nötig.

Online-Zahlung per Stripe:

1. Stripe-Konto anlegen, im Dashboard zuerst den **Test-Modus** verwenden.
2. In `.env`: `PAYMENT_PROVIDER=stripe`, `STRIPE_SECRET_KEY=sk_test_…`, danach Webhook im Stripe-Dashboard
   anlegen: URL `https://panel.deinedomain.de/api/payments/stripe`, Ereignisse
   `checkout.session.completed` und `checkout.session.async_payment_succeeded`. Das dort angezeigte
   Signing Secret als `STRIPE_WEBHOOK_SECRET=whsec_…` eintragen.
3. `./scripts/deploy.sh` (Backend-Image wird neu gebaut, das Stripe-Paket ist Teil davon).
4. Mit einer Testbestellung und der Stripe-Testkarte `4242 4242 4242 4242` durchspielen:
   Kunde klickt *Jetzt bezahlen*, kommt nach `/orders?paid=…` zurück, der Webhook stellt den Server bereit.
   Lokal lässt sich der Webhook mit der Stripe CLI nachstellen (`stripe listen --forward-to …`).
5. Erst nach erfolgreichem Testlauf auf die Live-Schlüssel wechseln.

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
Benachrichtigung gibt es nicht, daher den Smoke-Test regelmäßig laufen lassen oder einen externen Monitor
(z.B. Uptime Kuma mit Keyword `"healthy": true`) auf den Endpunkt richten.

Details zu Endpunkten, Status und Stripe-Einrichtung: `docs/orders-api.md`.

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
| Instanz hängt in `provisioning` | `journalctl -u wings`: Install-Container-Fehler, Docker-Image-Pull, Netzwerk |
| Server bleibt `starting` | Startup-Erkennung im Blueprint passt nicht zur Konsolenausgabe |
| Konsole lädt nicht | Browser erreicht `wss://node1…/api/servers/<uuid>/ws`? Caddy-Site `deploy/sites/node.caddy` vorhanden? |
| Spieler können nicht joinen | Firewall-Port, Endpoint-Port = Port in `server.properties` (Platzhalter im Blueprint) |

Weitere Details zur Wings-Anbindung: `docs/wings-remote-api.md`.
