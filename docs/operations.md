# Astra – Betriebs- und Deployment-Dokumentation

## Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Voraussetzungen](#voraussetzungen)
3. [Lokale Entwicklung](#lokale-entwicklung)
4. [Produktions-Deployment](#produktions-deployment)
5. [Konfiguration (ENV-Variablen)](#konfiguration)
6. [Datenbank-Migrationen](#datenbank-migrationen)
7. [Erster Admin-Setup (Bootstrap)](#erster-admin-setup)
8. [Reverse Proxy](#reverse-proxy)
9. [Backup & Restore](#backup--restore)
10. [Upgrade-Workflow](#upgrade-workflow)
11. [Monitoring & Health Checks](#monitoring--health-checks)
12. [Troubleshooting](#troubleshooting)

---

## Überblick

Astra ist ein Server-Management-Panel bestehend aus:
- **Backend**: Flask + SQLAlchemy (Python)
- **Frontend**: React + Vite (TypeScript)
- **Datenbank**: PostgreSQL (Produktion) / SQLite (Entwicklung)
- **Cache**: Redis (optional)

---

## Voraussetzungen

### Produktion (Docker)
- Docker >= 24.0
- Docker Compose >= 2.20
- Mindestens 2 GB RAM

### Lokale Entwicklung
- Python >= 3.12
- Node.js >= 22
- PostgreSQL >= 16 (oder SQLite für einfache Entwicklung)
- Redis >= 7 (optional)

---

## Lokale Entwicklung

### Backend starten

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
cp .env.example .env      # Anpassen!

# Datenbank initialisieren
flask db upgrade

# Ersten Admin erstellen
python cli.py bootstrap

# Server starten
flask run --port 5000
```

### Frontend starten

```bash
cd frontend
npm install
npm run dev               # Startet auf Port 3000
```

### Mit Docker Compose

```bash
docker compose up
# Backend: http://localhost:5000
# Frontend: http://localhost:3000
```

---

## Produktions-Deployment

### 1. Umgebungsvariablen vorbereiten

```bash
cp backend/.env.example .env
```

**Pflichtfelder für Produktion:**

```env
APP_ENV=production
SECRET_KEY=<sicherer-zufallswert>
JWT_SECRET_KEY=<sicherer-zufallswert>
DATABASE_URL=postgresql://user:pass@host:5432/astra
POSTGRES_PASSWORD=<sicheres-passwort>
BASE_URL=https://astra.example.com
CORS_ORIGINS=https://astra.example.com
```

Secrets generieren:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Container starten

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 3. Migrationen und Bootstrap

```bash
# Migrationen laufen automatisch bei AUTO_MIGRATE=true
# Oder manuell:
docker compose exec backend ./entrypoint.sh migrate

# Ersten Admin erstellen:
docker compose exec backend ./entrypoint.sh seed
```

### 4. Konfiguration prüfen

```bash
docker compose exec backend python cli.py check-config
```

---

## Konfiguration

Alle Umgebungsvariablen sind in `backend/.env.example` dokumentiert.

### Kritische Variablen

| Variable | Beschreibung | Default | Prod-Pflicht |
|----------|-------------|---------|:---:|
| `APP_ENV` | Umgebung (development/testing/production) | development | ✅ |
| `SECRET_KEY` | Flask Secret Key | dev-secret-key | ✅ |
| `JWT_SECRET_KEY` | JWT Signing Key | dev-jwt-secret-key | ✅ |
| `DATABASE_URL` | Datenbank-Verbindung | sqlite:///astra.db | ✅ |

### Runner / Wings

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `RUNNER_ADAPTER` | "stub" oder "wings" | stub |
| `RUNNER_TIMEOUT_CONNECT` | Verbindungstimeout (Sek.) | 5 |
| `RUNNER_TIMEOUT_READ` | Lese-Timeout (Sek.) | 30 |

### Auth / Sicherheit

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `JWT_ACCESS_TOKEN_EXPIRES_HOURS` | Token-Gültigkeit | 24 |
| `MFA_ISSUER_NAME` | TOTP Issuer | Astra |
| `RATELIMIT_ENABLED` | Rate Limiting aktiv | true |
| `RATELIMIT_AUTH_PER_MINUTE` | Max Login-Versuche/Min | 20 |

### Reverse Proxy

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `PROXY_FIX_ENABLED` | ProxyFix aktivieren | false (prod: true) |
| `PROXY_FIX_X_FOR` | Anzahl vertrauenswürdiger Proxies | 1 |
| `SESSION_COOKIE_SECURE` | Secure-Flag für Cookies | false (prod: true) |

---

## Datenbank-Migrationen

### Standardablauf

```bash
# Status prüfen
flask db current

# Migrationen anwenden
flask db upgrade

# Eine Migration zurückrollen
flask db downgrade -1
```

### Neue Migration erstellen (Entwicklung)

```bash
flask db migrate -m "Beschreibung der Änderung"
flask db upgrade
```

### Fehlgeschlagene Migration

1. Status prüfen: `flask db current`
2. Fehler analysieren
3. Falls nötig: `flask db downgrade -1`
4. Migration korrigieren und erneut: `flask db upgrade`

### Automatische Migrationen im Container

Mit `AUTO_MIGRATE=true` werden Migrationen automatisch beim Start ausgeführt.
Bei Fehler bricht der Container ab (Exit-Code != 0).

---

## Erster Admin-Setup

### CLI-Tool

```bash
python cli.py bootstrap \
    --username admin \
    --email admin@astra.local \
    --password sicheres-passwort
```

### Docker

```bash
docker compose exec backend python cli.py bootstrap \
    --username admin \
    --email admin@example.com \
    --password sicheres-passwort
```

### Umgebungsvariablen

```bash
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=sicheres-passwort

docker compose exec backend ./entrypoint.sh seed
```

**WICHTIG:** Passwort nach dem ersten Login ändern!

---

## Reverse Proxy

### Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name astra.example.com;

    ssl_certificate /etc/ssl/certs/astra.crt;
    ssl_certificate_key /etc/ssl/private/astra.key;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }
}
```

### Caddy

```
astra.example.com {
    handle /api/* {
        reverse_proxy backend:5000
    }
    handle /ws/* {
        reverse_proxy backend:5000
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

### Traefik

Labels im `docker-compose.prod.yml` ergänzen:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.astra.rule=Host(`astra.example.com`)"
  - "traefik.http.routers.astra.tls.certresolver=letsencrypt"
```

### Backend-Konfiguration für Proxy

```env
PROXY_FIX_ENABLED=true
PROXY_FIX_X_FOR=1
PROXY_FIX_X_PROTO=1
SESSION_COOKIE_SECURE=true
BASE_URL=https://astra.example.com
```

---

## Backup & Restore

### Backup erstellen

```bash
./scripts/backup.sh [BACKUP_VERZEICHNIS]
```

Sichert:
- PostgreSQL-Datenbank (pg_dump)
- `.env` Konfigurationsdateien
- Uploads (falls vorhanden)
- Docker-Compose-Dateien

### Backup wiederherstellen

```bash
./scripts/restore.sh ./backups/astra_backup_20260313_120000.tar.gz
```

### Automatische Bereinigung

Backups älter als 30 Tage werden automatisch gelöscht.
Änderbar über `BACKUP_RETENTION_DAYS`.

### Manuelles Datenbank-Backup

```bash
# Lokal
pg_dump -U astra -d astra --format=custom -f backup.dump

# Docker
docker compose exec postgres pg_dump -U astra -d astra --format=custom > backup.dump
```

---

## Upgrade-Workflow

### Standard-Upgrade

```bash
# 1. Backup erstellen
./scripts/backup.sh

# 2. Neue Version holen
git pull origin main
# oder: docker pull astra-backend:latest

# 3. Container neu bauen
docker compose -f docker-compose.prod.yml build

# 4. Container neu starten (Migrationen laufen automatisch)
docker compose -f docker-compose.prod.yml up -d

# 5. Health-Check
curl https://astra.example.com/health/ready
```

### Rollback

```bash
# 1. Container stoppen
docker compose -f docker-compose.prod.yml down

# 2. Alte Version wiederherstellen
git checkout <vorherige-version>

# 3. Datenbank wiederherstellen (falls nötig)
./scripts/restore.sh ./backups/astra_backup_YYYYMMDD_HHMMSS.tar.gz

# 4. Migration rückgängig machen (falls nötig)
docker compose exec backend flask db downgrade -1

# 5. Container neu starten
docker compose -f docker-compose.prod.yml up -d
```

---

## Monitoring & Health Checks

### Endpunkte

| Endpunkt | Zweck | Auth |
|----------|-------|:----:|
| `GET /health` | Liveness-Check | Nein |
| `GET /health/ready` | Readiness-Check (inkl. DB) | Nein |
| `GET /ops/info` | Betriebsinformationen | Nein |
| `GET /api/admin/health/detailed` | Detaillierter Status | Ja |

### Liveness vs. Readiness

- **Liveness** (`/health`): App läuft → HTTP 200
- **Readiness** (`/health/ready`): App + DB bereit → HTTP 200, oder HTTP 503 bei Problemen

### Kubernetes/Orchestrierung

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 5000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 5000
  initialDelaySeconds: 5
  periodSeconds: 10
```

---

## Troubleshooting

### App startet nicht

1. Konfiguration prüfen: `python cli.py check-config`
2. Logs prüfen: `docker compose logs backend`
3. DB-Verbindung testen: `docker compose exec backend flask db current`

### Migration fehlgeschlagen

1. Fehler in Logs lesen
2. `flask db current` → aktuelle Version
3. `flask db downgrade -1` → zurückrollen
4. Migration korrigieren, erneut `flask db upgrade`

### Rate Limit erreicht

- Standard: 20 Login-Versuche pro Minute pro IP
- Änderbar: `RATELIMIT_AUTH_PER_MINUTE`
- In-Memory-Store, Reset bei Neustart

### WebSocket-Verbindungsprobleme hinter Proxy

- Proxy muss WebSocket unterstützen (`Upgrade: websocket`)
- Nginx: `proxy_http_version 1.1` + `Upgrade`-Header
- Timeout erhöhen: `proxy_read_timeout 86400s`
