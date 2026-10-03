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

Das Skript baut die Images, startet Caddy, Postgres, Redis, Backend, Worker und Frontend, wartet bis die Migrationen durch sind und legt den Admin an. Caddy holt beim ersten Aufruf das Let's-Encrypt-Zertifikat, das dauert bis zu einer Minute.

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
| Wings-Port | `8080` | Wings lauscht lokal auf 8080 |
| SFTP-Port | `2022` | |
| Datenverzeichnis | `/var/lib/pterodactyl/volumes` | Pelican: `/var/lib/pelican/volumes` |
| Hinter Reverse Proxy | **an** | Wings ohne eigenes SSL, Caddy davor |

Danach den Agent per API auf Port 443 für die Panel→Wings-Verbindung umstellen (das Formular setzt Connect- und Listen-Port gleich):

```bash
TOKEN=$(curl -s -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<PW>"}' https://panel.deinedomain.de/api/auth/login \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"daemon_connect": 443, "daemon_listen": 8080, "behind_proxy": true, "scheme": "https"}' \
  https://panel.deinedomain.de/api/admin/agents/1
```

Dann **Endpoints** anlegen: Agent `node1`, IP `0.0.0.0`, Ports 25565, 25566, 25567 … (ein Endpoint = ein Gameserver-Port).

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

Blueprint (Vorlage) anlegen unter **Admin → Blueprints**. Für Minecraft Paper:

| Feld | Wert |
|---|---|
| Name | Minecraft Paper |
| Docker-Image | `ghcr.io/pterodactyl/yolks:java_21` |
| Startup-Befehl | `java -Xms128M -XX:MaxRAMPercentage=95.0 -Dterminal.jline=false -Dterminal.ansi=true -jar {{SERVER_JARFILE}}` |
| Install-Container | `ghcr.io/pterodactyl/installers:debian` |
| Stop-Befehl | `stop` |
| Startup-Erkennung | `)! For help, type ` |
| Variable | Name `Server Jar`, ENV `SERVER_JARFILE`, Standard `server.jar` |
| Variable | Name `Minecraft Version`, ENV `MINECRAFT_VERSION`, Standard `latest` |
| Variable | Name `Build`, ENV `BUILD_NUMBER`, Standard `latest` |
| Install-Script | siehe unten |

Install-Script (Paper-Download, entspricht dem offiziellen Egg):

```bash
#!/bin/bash
apt update && apt install -y curl jq
cd /mnt/server
PROJECT=paper
if [ -z "$MINECRAFT_VERSION" ] || [ "$MINECRAFT_VERSION" = "latest" ]; then
  MINECRAFT_VERSION=$(curl -s https://api.papermc.io/v2/projects/$PROJECT | jq -r '.versions[-1]')
fi
if [ -z "$BUILD_NUMBER" ] || [ "$BUILD_NUMBER" = "latest" ]; then
  BUILD_NUMBER=$(curl -s https://api.papermc.io/v2/projects/$PROJECT/versions/$MINECRAFT_VERSION | jq -r '.builds[-1]')
fi
JAR_NAME=$PROJECT-$MINECRAFT_VERSION-$BUILD_NUMBER.jar
curl -o "${SERVER_JARFILE:-server.jar}" "https://api.papermc.io/v2/projects/$PROJECT/versions/$MINECRAFT_VERSION/builds/$BUILD_NUMBER/downloads/$JAR_NAME"
echo "eula=true" > eula.txt
[ -f server.properties ] || curl -o server.properties https://raw.githubusercontent.com/parkervcp/eggs/master/minecraft/java/server.properties
echo "Installation abgeschlossen"
```

Sobald der Egg-Import (`POST /api/admin/blueprints/import`, in Arbeit) auf dem Branch ist, geht das in einem Schritt mit `blueprints/minecraft-paper.json`.

Dann unter **Admin → Instances** eine Instanz anlegen: Blueprint Paper, Agent node1, 2048 MB RAM, 5120 MB Disk, Endpoint 25565. Ablauf, den du beobachten kannst:

1. Instanz steht auf `provisioning`, Wings holt `GET /api/remote/servers/{uuid}/install`.
2. Install-Container läuft, lädt Paper, meldet `POST .../install` → Status `ready`.
3. Start über die Konsole, Container-Status `starting` → nach der Zeile `)! For help, type ` → `running`.
4. Mit dem Minecraft-Client auf `node1.deinedomain.de:25565` verbinden.

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
| Node-Credentials rotieren | Panel → Agent → *Credentials rotieren*, dann `install-wings.sh` erneut ausführen |

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
