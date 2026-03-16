# Known Limitations (RC1)

## Bewusst akzeptierte Einschraenkungen

### Runner / Wings-Integration
- **Stub-Adapter** laeuft in Dev/Test als Default. Wings-Adapter fuer Produktion vorhanden, aber erfordert echte Wings-Instanz.
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
- Responsive Design ist grundlegend, aber nicht Mobile-optimiert.
- Nicht alle Admin-Seiten verwenden bereits die neuen `PageLayout`/`StatusBadge`-Komponenten (schrittweise Migration).
- Keine Echtzeit-Updates via WebSocket fuer Admin-Ansichten (Polling oder manuelle Aktualisierung).

### Monitoring / Observability
- Fleet Monitoring basiert auf DB-Werten, nicht auf Live-Metriken.
- Keine Prometheus-/Grafana-Integration.
- Application Insights / APM nicht integriert.

### Deployment
- Docker/Compose ist vorbereitet, aber Kubernetes-Manifeste fehlen.
- SSL/TLS-Terminierung wird von externem Reverse Proxy erwartet.

### Sicherheit
- Rate Limiting ist In-Memory (reicht fuer Single-Instance, nicht fuer Cluster).
- CSRF-Schutz ist ueber SameSite Cookies + JWT geloest, kein dedizierter CSRF-Token.
