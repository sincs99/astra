# Wings Remote-API (M33)

> Stand: Astra v0.33.0-rc. Dieses Dokument beschreibt, wie ein unveränderter
> Wings-Daemon (Pterodactyl oder Pelican) an Astra angebunden wird und welche
> Endpunkte Astra dafür bereitstellt.

---

## Warum eine Remote-API?

Die Kommunikation zwischen Panel und Wings läuft in **beide Richtungen**:

| Richtung | Wer ruft wen | Beispiele |
|---|---|---|
| Panel → Wings | Astra ruft `https://node:8080/api/...` | Server anlegen, Power-Aktionen, Dateien, Backups starten |
| Wings → Panel | Wings ruft `https://panel/api/remote/...` | Server-Konfiguration laden, Install-Script holen, Status melden, SFTP-Login prüfen |

Bis v0.32 war nur die erste Richtung implementiert (`WingsRunnerAdapter`). Wings
konnte deshalb keinen Server booten: Nach `POST /api/servers` holt Wings die
eigentliche Konfiguration selbst vom Panel. Seit M33 stellt Astra diese Seite unter
`/api/remote` bereit. Die Pfade entsprechen `routes/api-remote.php` im Referenz-Panel,
Wings muss nicht angepasst werden.

---

## Authentifizierung (Node-Token)

Jeder Agent besitzt zwei Credentials, die beim Anlegen automatisch erzeugt werden:

- `daemon_token_id` (16 Zeichen) – öffentlich, identifiziert den Node
- `daemon_token` (64 Zeichen) – Secret, wird nur in der `config.yml` ausgeliefert

Wings sendet bei jedem Request:

```
Authorization: Bearer {daemon_token_id}.{daemon_token}
```

Antworten der Auth-Schicht:

| Status | Bedeutung |
|---|---|
| 401 | Kein oder leerer `Authorization`-Header |
| 400 | Header nicht im Format `id.token` |
| 403 | Unbekannte `token_id`, falscher Token oder Agent deaktiviert |

Jeder erfolgreiche Request aktualisiert `last_seen_at` des Agents (Fleet Monitoring).

Credentials neu erzeugen: `POST /api/admin/agents/{id}/rotate-credentials`.
Danach muss die `config.yml` auf dem Node neu ausgerollt und Wings neu gestartet werden.

---

## Endpunkte

| Methode | Pfad | Zweck | Antwort |
|---|---|---|---|
| GET | `/api/remote/servers?page=&per_page=` | Alle Server des Nodes beim Wings-Boot | `{data: [{uuid, settings, process_configuration}], meta: {current_page, last_page, …}}` |
| POST | `/api/remote/servers/reset` | Wings-Neustart: `provisioning`/`reinstalling`/`restoring` → ready | 204 |
| GET | `/api/remote/servers/{uuid}` | Konfiguration eines Servers | `{settings, process_configuration}` |
| GET | `/api/remote/servers/{uuid}/install` | Install-Daten | `{container_image, entrypoint, script}` |
| POST | `/api/remote/servers/{uuid}/install` | Install-Ergebnis `{successful, reinstall}` | 204 |
| POST | `/api/remote/servers/{uuid}/container/status` | `{data: {new_state}}` → `container_state` | `{}` |
| GET/POST | `/api/remote/servers/{uuid}/transfer/success` | Transfer abgeschlossen | 204 (409 wenn kein Transfer läuft) |
| GET/POST | `/api/remote/servers/{uuid}/transfer/failure` | Transfer fehlgeschlagen | 204 (409 wenn kein Transfer läuft) |
| POST | `/api/remote/sftp/auth` | SFTP-Login prüfen | `{user, server, permissions}` oder 403 |
| POST | `/api/remote/activity` | Activity-Events von Wings | 204 |
| GET | `/api/remote/backups/{uuid}?size=` | S3-Multipart-URLs | 400 (kein S3-Adapter) |
| POST | `/api/remote/backups/{uuid}` | Backup-Ergebnis `{successful, checksum, checksum_type, size}` | 204 |
| POST | `/api/remote/backups/{uuid}/restore` | Restore-Ergebnis `{successful}` | 204 |

Alle Server-Endpunkte akzeptieren die volle UUID oder die Kurzform (erste 8 Zeichen)
und liefern 404, wenn der Server nicht zum anfragenden Agent gehört.

### settings (Server-Konfiguration)

Erzeugt von `build_server_config()` in `backend/app/infrastructure/runner/config_builder.py`:

```json
{
  "id": 12,
  "uuid": "…",
  "meta": {"name": "…", "description": ""},
  "suspended": false,
  "environment": {"STARTUP": "…", "SERVER_MEMORY": "2048", "SERVER_IP": "0.0.0.0", "SERVER_PORT": "25565", "P_SERVER_UUID": "…"},
  "invocation": "java -Xms128M -Xmx{{SERVER_MEMORY}}M -jar server.jar",
  "skip_egg_scripts": false,
  "build": {"memory_limit": 2048, "swap": 0, "io_weight": 500, "cpu_limit": 100, "threads": null, "disk_space": 10240, "oom_killer": true},
  "container": {"image": "ghcr.io/pterodactyl/yolks:java_21", "requires_rebuild": false},
  "allocations": {"force_outgoing_ip": false, "default": {"ip": "0.0.0.0", "port": 25565}, "mappings": {"0.0.0.0": [25565]}},
  "egg": {"id": "3", "file_denylist": [], "features": []}
}
```

### process_configuration

Kommt aus den neuen Blueprint-Feldern (M33):

| Blueprint-Feld | Wings-Feld | Beispiel |
|---|---|---|
| `config_startup` | `startup.done` / `startup.strip_ansi` | `{"done": [")! For help, type "]}` |
| `config_stop` | `stop` | `"stop"` → `{"type": "command", "value": "stop"}`; `"^SIGTERM"` → `{"type": "signal", "value": "SIGTERM"}` |
| `config_files` | `configs[]` | `{"server.properties": {"parser": "properties", "find": {"server-port": "{{server.build.default.port}}"}}}` |
| `file_denylist` | `settings.egg.file_denylist` | `["*.jar"]` |
| `install_container` | `container_image` (Install) | `ghcr.io/pterodactyl/installers:debian` |
| `install_entrypoint` | `entrypoint` (Install) | `bash` |

Platzhalter in `config_files` werden wie im Referenz-Panel ersetzt:
`{{server.X.Y}}` aus den settings, `{{env.NAME}}` aus `settings.environment`,
`{{config.X}}` bleibt stehen und wird von Wings aufgelöst. Die Legacy-Pfade aus
Pterodactyl-Eggs (`{{server.build.default.port}}`, `{{server.build.env.NAME}}`) werden
auf `allocations.default.*` bzw. `environment.*` abgebildet, bestehende Eggs lassen
sich also 1:1 übernehmen.

Ohne `config_startup.done` bleibt ein Server in Wings dauerhaft auf `starting`.
Für Minecraft-Server ist `)! For help, type ` der übliche Wert.

### SFTP-Login

Wings sendet `{"type": "password"|"public_key", "username": "<user>.<serverid>", "password": "<passwort oder public key>"}`.
Der Benutzername wird am **letzten** Punkt getrennt, `serverid` ist UUID oder Kurz-UUID.

- Passwort: `User.check_password()`
- Public Key: `authorize_ssh_key_access()` aus M30 (Key-Matching, `file.sftp`, Suspension)
- Owner und Admins erhalten alle Rechte, Collaborators brauchen `file.sftp` plus
  die jeweiligen `file.*`-Rechte. Mapping auf Wings: `file.read` → `file.read`, `file.read-content`;
  `file.update` → `file.update`, `file.create`; `file.delete` → `file.delete`.
- Suspendierte Instanzen werden mit 403 abgelehnt.

Der bisherige Astra-interne Endpunkt `POST /api/agent/sftp-auth` bleibt bestehen und verlangt seit M36 ebenfalls den Node-Token.

### Backups und Restore sind asynchron

Wings antwortet auf Backup-/Restore-Aufträge mit `202 Accepted`. Astra markiert ein
Backup deshalb erst nach dem Callback `POST /api/remote/backups/{uuid}` als
erfolgreich; bis dahin ist `is_successful = false`. Ein Restore hält die Instanz im
Status `restoring`, bis `POST /api/remote/backups/{uuid}/restore` eintrifft.
Der Stub-Adapter meldet weiterhin synchron (`completed: true`).

---

## Node einrichten (Wings auf einem Server)

1. **Agent anlegen** unter *Admin → Agents*. Pflicht: Name und FQDN (DNS-Name des Nodes).
   Optional: Scheme (`https`), `behind_proxy`, Ports (`daemon_listen` 8080, `daemon_sftp` 2022),
   Datenverzeichnis (`daemon_base`, Standard `/var/lib/pterodactyl/volumes`, bei Pelican
   `/var/lib/pelican/volumes`).
2. **config.yml holen**: Button *config.yml* beim Agent oder
   `GET /api/admin/agents/{id}/configuration` (`yaml`-Feld). Das Feld `remote` ist die
   `BASE_URL` des Panels. Sie muss vom Node aus erreichbar sein.
3. **Wings installieren** (Node):
   ```bash
   curl -L -o /usr/local/bin/wings "https://github.com/pterodactyl/wings/releases/latest/download/wings_linux_amd64"
   chmod u+x /usr/local/bin/wings
   mkdir -p /etc/pterodactyl
   # Inhalt aus Schritt 2 nach /etc/pterodactyl/config.yml
   ```
   Docker muss installiert sein. TLS: entweder Let's-Encrypt-Zertifikat unter dem in der
   config.yml angegebenen Pfad oder `behind_proxy = true` mit TLS-terminierendem Reverse Proxy.
4. **Endpoints anlegen** (IP:Port-Allokationen) für den Agent. Die Ports müssen auf dem
   Node offen sein.
5. **Wings starten** (`systemctl enable --now wings`). Wings ruft sofort
   `GET /api/remote/servers` auf; der Agent erscheint im Fleet Monitoring als `healthy`.
6. **Blueprint prüfen**: Image, Startup-Befehl, Install-Script, `config_startup.done`,
   `config_stop`. Dann eine Instanz anlegen; Wings holt Install-Daten, führt das Script im
   Install-Container aus und meldet das Ergebnis per Install-Callback.

Firewall auf dem Node: eingehend 8080/tcp (Wings-API), 2022/tcp (SFTP) und der
Port-Bereich der Endpoints. Das Panel muss den Node auf 8080 erreichen, der Node das
Panel auf 443.

---

## Fehlersuche

| Symptom | Ursache | Lösung |
|---|---|---|
| Wings-Log: `401 Unauthorized` / `403` beim Start | Token in `config.yml` passt nicht zum Agent | config.yml neu holen, ggf. Credentials rotieren |
| Wings-Log: `404` auf `/api/remote/servers/...` | Instanz gehört zu einem anderen Agent | Instanz prüfen, Transfer |
| Server bleibt auf `starting` | `config_startup.done` fehlt oder passt nicht zur Konsolenausgabe | Blueprint anpassen, Instanz syncen |
| Backup bleibt `is_successful=false` | Callback nicht angekommen | `remote` in config.yml und Erreichbarkeit des Panels prüfen |
| SFTP-Login schlägt fehl | Benutzername ohne `.serverid`, falsches Passwort, kein `file.sftp` | Format `user.<kurz-uuid>` verwenden |

---

## Nicht enthalten (bewusst)

- S3-Backups über Presigned-URLs (`GET /api/remote/backups/{uuid}` antwortet 400).
- Rate-Limiting für `/api/remote/sftp/auth` (alle Anfragen kommen von Node-IPs;
  ein IP-basiertes Limit würde legitime Key-Versuche blockieren).
- Mounts (`allowed_mounts` in der config.yml ist leer).

## Eggs importieren (M37)

Pterodactyl- und Pelican-Eggs lassen sich 1:1 als Blueprint übernehmen:

```bash
# per CLI (JSON oder YAML)
python cli.py import-blueprint ../blueprints/minecraft-paper.json

# per API (Admin-Token nötig)
curl -X POST https://panel.example/api/admin/blueprints/import \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data @blueprints/minecraft-paper.json
```

Erkannt werden `meta.version` `PTDL_*`/`PLCN_*` sowie das native Astra-Format (`"format": "astra"`).
Die Pterodactyl-Platzhalter wie `{{server.build.default.port}}` bleiben erhalten, der Config-Builder
versteht sie. Das mitgelieferte Beispiel `blueprints/minecraft-paper.json` ist ein reduziertes eigenes Egg;
die Minecraft-EULA muss der Serverbesitzer selbst in `eula.txt` akzeptieren.
