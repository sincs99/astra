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
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Im Entwicklungs-Compose läuft das Backend mit `RUNNER_ADAPTER=stub` und `AUTO_MIGRATE=true`, es wird also kein echter Gameserver gestartet.

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
