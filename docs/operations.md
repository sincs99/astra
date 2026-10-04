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

> Vollständige Schritt-für-Schritt-Anleitung inkl. Wings-Node, Firewall und Abnahme:
> **`docs/deploy-runbook.md`**. Hier die Kurzfassung.

Der Produktions-Stack (`docker-compose.prod.yml`) besteht aus Caddy (TLS via Let's Encrypt,
einziger öffentlicher Eingang auf 80/443), Frontend (Nginx), Backend (Gunicorn), Worker
(Job-Queue), PostgreSQL und Redis. Optional proxyt Caddy auch den Wings-Node (`NODE_DOMAIN`).

### 1. Umgebungsvariablen vorbereiten

```bash
cp .env.prod.example .env
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
./scripts/deploy.sh --bootstrap     # erster Start inkl. Admin
./scripts/deploy.sh                 # jedes Update
```

Manuell entspricht das `docker compose up -d` (mit `COMPOSE_FILE=docker-compose.prod.yml` in der `.env`).

### 3. Migrationen und Bootstrap

```bash
# Migrationen laufen automatisch bei AUTO_MIGRATE=true (python cli.py db-init:
# frische DB -> Schema anlegen + stamp head, bestehende DB -> upgrade)
# Oder manuell:
docker compose exec backend ./entrypoint.sh migrate

# Ersten Admin erstellen (macht deploy.sh --bootstrap bereits):
docker compose exec backend ./entrypoint.sh seed
```

### 4. Konfiguration prüfen

```bash
docker compose exec backend python cli.py check-config
./scripts/smoke-test.sh https://<PANEL_DOMAIN> admin '<passwort>'
```

Alte Job-Eintraege (`completed`/`failed`) wachsen unbegrenzt. Gelegentlich aufraeumen, z.B. woechentlich per Cron:

```bash
docker compose exec backend python cli.py cleanup-jobs --days 30   # --dry-run zeigt nur die Zahl
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
| `RUNNER_ADAPTER` | "stub" oder "wings". Der Stub schließt Installation, Neuinstallation und Transfer **sofort** ab (Status ready), Wings meldet das Ergebnis asynchron über die Remote-API | stub |
| `RUNNER_TIMEOUT_CONNECT` | Verbindungstimeout (Sek.) | 5 |
| `RUNNER_TIMEOUT_READ` | Lese-Timeout (Sek.) | 30 |

Wings ruft das Panel unter `BASE_URL` + `/api/remote/...` auf (Node-Token-Auth).
`BASE_URL` muss deshalb vom Node aus erreichbar sein. Die `config.yml` fuer einen
Node liefert `GET /api/admin/agents/{id}/configuration` bzw. der Button *config.yml*
in der Agents-Ansicht. Details: `docs/wings-remote-api.md`.

### Auth / Sicherheit

| Variable | Beschreibung | Default |
|----------|-------------|---------|
| `JWT_ACCESS_TOKEN_EXPIRES_HOURS` | Token-Gültigkeit | 24 |
| `MFA_ISSUER_NAME` | TOTP Issuer | Astra |
| `RATELIMIT_ENABLED` | Rate Limiting aktiv | true |
| `PAYMENT_PROVIDER` | Zahlungsweg: `manual` oder `stripe` (siehe orders-api.md) | manual |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe-Zugang (nur Umgebung, nie ins Repository) | – |
| `BILLING_REMINDER_DAYS` | Tage vor Laufzeitende für die Erinnerungsmail, 0 = aus (Billing-Tick) | 3 |
| `BILLING_TICK_MAX_AGE_MINUTES` | Warnung (Preflight, `/api/admin/billing/status`), wenn der Billing-Tick so lange nicht gelaufen ist | 15 |
| `BILLING_WAIT_WARN_HOURS` | Warnung (Preflight, `/api/admin/billing/status`), wenn eine bezahlte Bestellung so lange auf einen freien Node wartet | 24 |
| `ADMIN_ALERT_EMAIL` | Adresse(n), kommagetrennt, für Admin-Alerts (leer = aus; braucht `MAIL_SERVER`) | – |
| `ADMIN_ALERT_WEBHOOK_URL` | Webhook für Admin-Alerts, JSON mit `content` (Discord) und `text` (Slack); enthält oft ein Geheimnis (leer = aus) | – |
| `ADMIN_ALERT_COOLDOWN_MINUTES` | Eine anhaltende Störung wird frühestens nach so vielen Minuten erneut gemeldet | 360 |
| `ADMIN_ALERT_RECOVERY` | Einmalige Entwarnung, wenn die Störung behoben ist | true |
| `INVOICE_NUMBER_FORMAT` | Format der Belegnummer (`{year}`, `{seq}`), nach dem Start nicht mehr ändern | `AST-{year}-{seq:05d}` |
| `INVOICE_SELLER` / `RECEIPT_FOOTER` | Anbieter-Kopf (Name, Anschrift) und Fußzeile der Rechnungen (`\n` = Zeilenumbruch) | – |
| `VAT_RATE` | Umsatzsteuersatz in Prozent auf Rechnungen (Preise sind Brutto), `0` = Kleinunternehmer | 0 |
| `INVOICE_SELLER_VAT_ID` | USt-IdNr. des Anbieters (optional, wird gedruckt) | – |
| `INVOICE_SMALL_BUSINESS_NOTE` | Hinweistext bei Satz 0 | Gemäß § 19 UStG wird keine Umsatzsteuer berechnet. |
| `BILLING_GRACE_DAYS` | Tage von überfälliger Zahlung bis zur Löschung der Instance (Billing-Tick) | 7 |
| `REGISTRATION_ENABLED` | Selbstregistrierung erlauben | false |
| `EMAIL_VERIFICATION_REQUIRED` | Login erst nach bestaetigter E-Mail (braucht funktionierendes SMTP) | false |
| `EMAIL_VERIFICATION_TTL_HOURS` | Gueltigkeit des Bestaetigungs-Links | 48 |
| `PASSWORD_RESET_TTL_MINUTES` | Gueltigkeit des Reset-Links | 60 |
| `FRONTEND_URL` | Basis-URL fuer Links in Mails | http://localhost:3000 |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USE_TLS` | SMTP-Server (leer = kein Versand, nur Log) | – / 587 / true |
| `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` | SMTP-Zugang und Absender | – / – / astra@localhost |
| `RATELIMIT_AUTH_PER_MINUTE` | Max Anfragen/Min je IP für die übrigen Auth-Routen (Passwort ändern, E-Mail bestätigen, Reset bestätigen) | 20 |
| `RATELIMIT_REGISTER_PER_HOUR` | Registrierungen je IP und Stunde | 5 |
| `RATELIMIT_LOGIN_PER_MINUTE` | Login-Versuche je IP und Minute | 10 |
| `RATELIMIT_LOGIN_FAILURES_PER_HOUR` | Fehlversuche je Konto und Stunde, danach gesperrt | 20 |
| `RATELIMIT_PASSWORD_RESET_PER_HOUR` | Passwort-Reset-Anfragen je IP und Stunde | 3 |
| `CAPTCHA_PROVIDER` | `none`, `turnstile` oder `hcaptcha` (Registrierung und Passwort-Reset-Anfrage) | none |
| `CAPTCHA_SITE_KEY` / `CAPTCHA_SECRET` | Schlüssel des Anbieters (Site-Key öffentlich, Secret nur im Backend) | – |

### Registrierungsschutz (M71)

Die Selbstregistrierung (`REGISTRATION_ENABLED=true`) ist gegen Bots in drei Schichten geschützt:

1. **Rate-Limits** (`RATELIMIT_ENABLED=true`, in Produktion Standard; Redis wird mitgenutzt, sonst zählt jeder Prozess für sich):
   Registrierung 5 pro Stunde je IP, Login 10 pro Minute je IP, Passwort-Reset-Anfrage 3 pro Stunde je IP. Zusätzlich sperrt der Login ein
   **Konto** nach 20 Fehlversuchen in einer Stunde (auch für das richtige Passwort; erfolgreiche Logins zählen nicht). Vorsicht: wer einen
   Benutzernamen kennt, kann ihn so für eine Stunde sperren; der Preis dafür ist der Schutz vor Passwort-Raten, die Sperre läuft von selbst ab und
   steht im Activity-Log (`auth:login_blocked`). Antwort 429 `{error, code: "rate_limited", retry_after_seconds}` mit `Retry-After`-Header.
   Die IP kommt aus `request.remote_addr`; hinter Proxys setzt ProxyFix (`PROXY_FIX_ENABLED`, `PROXY_FIX_X_FOR` = Anzahl der Proxys, im Compose-Stack 2:
   Caddy und Frontend-Nginx) die echte Adresse aus `X-Forwarded-For`. Mehr Hops anzugeben als Proxys vorhanden sind, macht die IP fälschbar; ohne ProxyFix
   wird `X-Forwarded-For` ignoriert. Ist ProxyFix hinter einem Proxy nicht aktiv, sieht das Backend nur dessen Adresse und alle Kunden teilen sich ein Limit.
2. **CAPTCHA** (`CAPTCHA_PROVIDER=turnstile` oder `hcaptcha`, Standard `none`): `GET /api/auth/captcha` liefert `{provider, site_key}`, das Frontend zeigt das Widget
   und sendet `captcha_token` bei `POST /api/auth/register` und `POST /api/auth/password-reset/request`. Der Server prüft per siteverify (Timeout 5 Sekunden):
   fehlend oder ungültig `400 {code: "captcha_failed"}`, Dienst nicht erreichbar oder Secret fehlt `503 {code: "captcha_unavailable"}` (Registrierung und Reset
   sind dann nicht nutzbar, Login bleibt unberührt). Der Produktions-Check warnt bei gesetztem Anbieter ohne Keys.
   **Datenschutz:** das Widget lädt Skripte vom Anbieter (Cloudflare bzw. Intuition Machines) und überträgt dabei Daten des Besuchers; das gehört in die
   Datenschutzerklärung (und ggf. in die Einwilligung), bevor `CAPTCHA_PROVIDER` aktiviert wird.
3. **Honigtopf:** ein verstecktes Formularfeld `website` im Registrierungs-Body. Ist es ausgefüllt, antwortet die API `400 {code: "invalid_request"}`, legt kein Konto an und
   fragt auch den CAPTCHA-Dienst nicht. Das Frontend darf das Feld nie befüllen (unsichtbar, `tabindex=-1`, `autocomplete=off`).

Mit `RATELIMIT_ENABLED=false` (nur Tests) gibt es weder Limits noch Kontosperre.

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
- Zähler liegt in Redis (`REDIS_URL`), gilt also für alle Worker; ohne erreichbares Redis In-Memory pro Prozess

### WebSocket-Verbindungsprobleme hinter Proxy

- Proxy muss WebSocket unterstützen (`Upgrade: websocket`)
- Nginx: `proxy_http_version 1.1` + `Upgrade`-Header
- Timeout erhöhen: `proxy_read_timeout 86400s`
