# Astra

Astra ist ein Game-Server-Panel nach dem Vorbild von Pterodactyl: Flask-Backend, React/TypeScript-Frontend, PostgreSQL und Redis. Der Ordner `reference/` enthält das Original-Pterodactyl-Panel als reine Lesevorlage und gehört nicht zur Anwendung.

Aktuelle Version: siehe [CHANGELOG.md](CHANGELOG.md).

## Struktur

| Ordner | Inhalt |
|---|---|
| `backend/` | Flask-API, Migrationen, Tests (`test_m*.py`), siehe [backend/README.md](backend/README.md) |
| `frontend/` | React/TypeScript-Oberfläche (Vite), siehe [frontend/README.md](frontend/README.md) |
| `docs/` | Betrieb, Scope, Release-Planung, bekannte Einschränkungen |
| `scripts/` | `deploy.sh`, `install-wings.sh`, `smoke-test.sh`, `backup.sh`, `restore.sh` |
| `deploy/` | Caddy-Konfiguration für den Produktions-Stack |
| `reference/` | Original-Pterodactyl-Panel (nur lesen) |

## Schnellstart (Entwicklung)

```bash
docker compose up --build
```

| Dienst | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:5000 |
| PostgreSQL | 127.0.0.1:5432 |
| Redis | 127.0.0.1:6379 |

Backend, PostgreSQL und Redis sind nur auf `127.0.0.1` gebunden (die Dev-Zugangsdaten sind öffentlich bekannt, Redis hat kein Passwort). Wer sie aus dem LAN erreichen will, setzt die Ports in einer `docker-compose.override.yml` um.

Im Entwicklungs-Compose läuft das Backend mit `RUNNER_ADAPTER=stub` und `AUTO_MIGRATE=true`, es wird also kein echter Gameserver gestartet. Ein Agent meldet dann im Fleet Monitoring `daemon_version: "stub"` und wirkt `healthy`, obwohl Wings nie angesprochen wird. Für Tests gegen ein echtes Wings: `RUNNER_ADAPTER=wings docker compose up` und im Monitoring prüfen, dass `daemon_version` die Wings-Version zeigt.

Läuft Wings auf einem anderen Rechner (Multi-Node-Test), muss das Panel unter seiner LAN-Adresse bekannt sein, sonst steht in der exportierten `config.yml` `remote: http://localhost:5000` und der Node erreicht das Panel nie; außerdem lehnt Wings die Konsole im Browser ab, wenn dessen Origin nicht zu `remote` bzw. `allowed_origins` passt. Dafür `BASE_URL` und `FRONTEND_URL` auf die Adresse setzen, unter der du das Panel im Browser öffnest (das Frontend-Nginx leitet `/api` ans Backend weiter), z. B.:

```bash
BASE_URL=http://192.168.1.7:3000 FRONTEND_URL=http://192.168.1.7:3000 RUNNER_ADAPTER=wings docker compose up
```

Danach die `config.yml` des Agents neu holen (`install-wings.sh` erneut ausführen) und Wings neu starten.

Ohne Docker: Anleitung in [backend/README.md](backend/README.md) und [frontend/README.md](frontend/README.md).

## Produktion

`docker-compose.prod.yml` ist das Compose-File für den Produktivbetrieb: Caddy (TLS automatisch), Frontend, Backend, Worker, PostgreSQL, Redis. Start mit `cp .env.prod.example .env`, Werte setzen, `./scripts/deploy.sh --bootstrap`. Ablauf, Backups und Wiederherstellung stehen in:

- [docs/deploy-runbook.md](docs/deploy-runbook.md) – Schritt für Schritt: Server, Panel, Wings-Node, erster Gameserver
- [docs/wings-remote-api.md](docs/wings-remote-api.md) – Anbindung des Wings-Daemons
- [docs/operations.md](docs/operations.md)
- [docs/upgrade-guide.md](docs/upgrade-guide.md)
- [docs/pilot-rollout-plan.md](docs/pilot-rollout-plan.md)

## Dokumentation

- [docs/v1-scope.md](docs/v1-scope.md) – Umfang von v1.0
- [docs/known-limitations.md](docs/known-limitations.md) – bekannte Einschränkungen
- [docs/release-plan.md](docs/release-plan.md) – Roadmap und Go-Live-Kriterien
- [docs/agent-maintenance.md](docs/agent-maintenance.md) – Wartung der Agents
- [docs/ssh-sftp-auth.md](docs/ssh-sftp-auth.md) – SSH-Keys und SFTP-Authentifizierung
- [docs/mfa-recovery-codes.md](docs/mfa-recovery-codes.md) – MFA-Recovery-Codes
