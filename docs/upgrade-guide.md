# Upgrade Guide (M24)

## Uebersicht

Dieses Dokument beschreibt den Upgrade-Prozess fuer Astra.

## Voraussetzungen

- Zugriff auf den Server / die Container-Umgebung
- Backup der Datenbank
- Aktuelle Version bekannt (via `python cli.py version`)

## Upgrade-Ablauf

### 1. Preflight-Check (vor dem Upgrade)

```bash
cd backend
python cli.py preflight
```

Prueft:
- App-Konfiguration korrekt
- Datenbank erreichbar
- Migrationen aktuell
- Redis erreichbar (falls konfiguriert)

### 2. Code deployen

```bash
# Neuen Code auschecken / Image pullen
git pull origin main
# oder Docker-Image aktualisieren
```

### 3. Dependencies installieren

```bash
cd backend
pip install -r requirements.txt

cd frontend
npm install
npm run build
```

### 4. Migrationen ausfuehren

```bash
cd backend
flask db upgrade
```

### 5. Post-Upgrade-Check

```bash
python cli.py preflight
python cli.py upgrade-status
```

Oder via API:
- `GET /ops/upgrade-status`
- `GET /ops/preflight`

### 6. Anwendung neu starten

```bash
# Systemd / Supervisor / Docker restart
systemctl restart astra-backend
# oder
docker compose restart backend
```

## Upgrade-Status pruefen

### CLI
```bash
python cli.py version           # Zeigt aktuelle Version
python cli.py upgrade-status    # Zeigt Migration-Status
python cli.py preflight         # Umfassender Preflight-Check
```

### API
- `GET /ops/version` - Version und Build-Info
- `GET /ops/upgrade-status` - Migration und Upgrade-Status
- `GET /ops/preflight` - Preflight-Check (200=ok, 503=nicht bereit)
- `GET /api/admin/system/version` - Version (Admin-API)
- `GET /api/admin/system/upgrade-status` - Upgrade-Status (Admin-API)
- `GET /api/admin/system/preflight` - Preflight (Admin-API)

### Frontend
- `/admin/system` - System-Info-Seite mit Version, Migration und Preflight

## Rollback

### Grundprinzip

1. **Code zuruecksetzen** auf die vorherige Version
2. **Migrationen rueckgaengig machen** (wenn noetig):
   ```bash
   flask db downgrade <revision>
   ```
3. **Anwendung neu starten**

### Wichtig

- Immer **vor** einem Upgrade ein DB-Backup erstellen
- Migrationen die Daten loeschen koennen nicht einfach rueckgaengig gemacht werden
- Im Zweifel: DB-Backup wiederherstellen
- Alembic-Revision fuer Downgrade findet sich in `backend/migrations/versions/`

## Versionsformat

Astra verwendet semantische Versionierung:
- **Major** (X.0.0): Breaking Changes
- **Minor** (0.X.0): Neue Features (abwaertskompatibel)
- **Patch** (0.0.X): Bugfixes

Die zentrale Version wird in `backend/app/version.py` gepflegt.

## Build-Metadaten

Optional koennen via Umgebungsvariablen Build-Infos gesetzt werden:
- `BUILD_SHA` - Git Commit SHA
- `BUILD_DATE` - Build-Zeitstempel
- `BUILD_REF` - Git Tag oder Branch

Beispiel im Dockerfile:
```dockerfile
ARG BUILD_SHA
ARG BUILD_DATE
ENV BUILD_SHA=$BUILD_SHA
ENV BUILD_DATE=$BUILD_DATE
```
