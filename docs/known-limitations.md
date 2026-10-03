# Known Limitations (RC1)

## Bewusst akzeptierte Einschraenkungen

### Runner / Wings-Integration
- **Stub-Adapter** laeuft in Dev/Test als Default. Wings-Adapter fuer Produktion vorhanden, aber erfordert echte Wings-Instanz.
- Seit M33 stellt Astra die Wings Remote-API (`/api/remote`) bereit; S3-Presigned-Uploads und Mounts sind nicht enthalten (siehe `docs/wings-remote-api.md`).
- Die Remote-API wurde gegen den Vertrag des Referenz-Panels gebaut und per Tests abgesichert, aber noch nicht gegen einen laufenden Wings-Daemon abgenommen (Teil des Pilot-Go/No-Go).
- Konsolen-Websocket funktioniert nur mit echtem Wings-Daemon (im Stub simuliert).
- Dateioperationen im Stub-Modus liefern simulierte Daten.

### Queue / Background Jobs
- **SyncQueue** (synchron) ist Default in Dev/Test. Fuer Produktion muss Redis konfiguriert und ein Worker gestartet werden.
- Webhook-Retry-Delays (5/15/30s) laufen im SyncQueue-Modus blockierend.
- Kein automatisches Job-Cleanup (alte Jobs bleiben in DB).

### Datenbank
- **SQLite** wird in Dev/Test verwendet. Fuer Produktion PostgreSQL empfohlen.
- Database-Provisioning (M18) erstellt Metadaten, verbindet sich aber nicht mit echten Datenbankservern.

### Auth / MFA
- MFA-Verifizierung ist implementiert, aber kein Recovery-Code-Flow fuer verlorene Authenticator-Apps.
- API-Key-Rotation erfordert manuelles Loeschen und Neuerstellen.

### Agent Maintenance
- Kein automatisches Drain: Bestehende Instances laufen weiter auf Maintenance-Agents.
- Kein Transfer-Mechanismus zwischen Agents.

### UI / Frontend
- Responsive Design ist grundlegend (Tabellen scrollen horizontal), Navigation ist mobil als Hamburger-Menue umgesetzt, Tabellen und Formulare sind aber nicht vollstaendig Mobile-optimiert.
- File-Upload nur fuer Textdateien bis 1 MB (kein Multipart-Endpoint im Backend).
- Nicht alle Admin-Seiten verwenden bereits die neuen `PageLayout`/`StatusBadge`-Komponenten (schrittweise Migration).
- Keine Echtzeit-Updates via WebSocket fuer Admin-Ansichten; Jobs, Fleet Monitoring, Dashboard und Admin-Instances pollen alle 15s (abschaltbar), andere Seiten nur manuell.

### Monitoring / Observability
- Fleet Monitoring basiert auf DB-Werten, nicht auf Live-Metriken.
- Keine Prometheus-/Grafana-Integration.
- Application Insights / APM nicht integriert.

### Deployment
- Docker/Compose ist vorbereitet, aber Kubernetes-Manifeste fehlen.
- SSL/TLS-Terminierung wird von externem Reverse Proxy erwartet.

### Sicherheit
- `/api/admin` (Admin-Guard, M35) und `/api/agent` (Node-Token, M36) sind geschuetzt. Die Legacy-Routen unter `/api/agent` werden von Wings nicht benutzt (Wings nutzt `/api/remote`) und koennen langfristig entfallen.
- Rate Limiting nutzt Redis (`REDIS_URL`); ist Redis nicht erreichbar, faellt es auf einen In-Memory-Zaehler pro Prozess zurueck.
- CSRF-Schutz ist ueber SameSite Cookies + JWT geloest, kein dedizierter CSRF-Token.
