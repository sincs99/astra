# Background Jobs & Queue (M23)

## Uebersicht

Astra verarbeitet Hintergrundaufgaben ueber ein leichtgewichtiges Job-System.
Jobs werden in der Datenbank getrackt und ueber eine konfigurierbare Queue
ausgefuehrt.

## Architektur

```
Anfrage -> enqueue_job() -> JobRecord (DB) -> Queue-Backend -> Handler
```

### Queue-Backends

| Backend | Verwendung | Verhalten |
|---------|-----------|-----------|
| `sync`  | Dev/Test (Default) | Sofortige Ausfuehrung im selben Prozess |
| `thread`| Dev mit Non-Blocking | Ausfuehrung in Daemon-Thread |
| `redis` | Produktion | Job-ID an Redis, Worker verarbeitet |

Konfiguration via `JOB_QUEUE_BACKEND` Umgebungsvariable:
```env
JOB_QUEUE_BACKEND=sync   # Default (Dev/Test)
JOB_QUEUE_BACKEND=redis  # Produktion
```

### Graceful Fallback

Wenn Redis nicht verfuegbar ist, faellt das System automatisch auf
synchrone Ausfuehrung zurueck. Tests laufen immer ohne Redis.

## Job-Typen

| Typ | Beschreibung | Retry |
|-----|-------------|-------|
| `webhook_dispatch` | Webhook an Endpoint senden | 3x mit Delay (5/15/30s) |
| `routine_execute` | Routine-Ausfuehrung starten | 1x |
| `routine_action` | Einzelne Routine-Action | 1x |
| `agent_health_check` | Agent-Health pruefen | 3x |
| `instance_sync` | Instance mit Runner sync | 3x |

## Retry-Regeln

- Jeder Job hat `max_attempts` (konfigurierbar)
- Bei Fehler: wenn Versuche uebrig -> `retrying`, nochmal ausfuehren
- Nach letztem Fehlversuch: `failed`
- Fehler werden in `error`-Feld gespeichert (max 500 Zeichen)
- Keine Secrets in Job-Logs oder Error-Feldern

## Job-Status

| Status | Bedeutung |
|--------|-----------|
| `pending` | Job erstellt, wartet auf Ausfuehrung |
| `running` | Job wird gerade ausgefuehrt |
| `completed` | Job erfolgreich abgeschlossen |
| `failed` | Alle Versuche fehlgeschlagen |
| `retrying` | Fehlversuch, wird erneut versucht |

## Webhook-Dispatch

Ab M23 laufen Webhook-Dispatches ueber Jobs statt ad-hoc Threading:
- `dispatch_webhook_event()` API bleibt unveraendert
- Intern wird pro Webhook ein `webhook_dispatch`-Job erstellt
- Retry-Logik (3 Versuche mit Delay) laeuft im Handler
- Delivery-Tracking bleibt bestehen

## Routine-Ausfuehrung

Ab M23 laeuft die Routine-Ausfuehrung nicht mehr blockierend:
- `execute_routine()` erstellt einen `routine_execute`-Job
- Der Handler erstellt pro Action einen `routine_action`-Job
- `delay_seconds` wird ueber `scheduled_at` abgebildet
- Response enthaelt `job_uuid` fuer Nachverfolgung

## Worker starten

```bash
cd backend
python cli.py worker [--poll-interval 1]
```

Der Worker:
- Verbindet sich mit Redis
- Holt Jobs aus der Queue (`astra:jobs:pending`)
- Fuehrt sie mit App-Kontext aus
- Reagiert auf SIGINT/SIGTERM fuer Graceful Shutdown

## API-Endpunkte

### GET /api/admin/jobs
Listet Jobs mit optionalen Filtern.
- `status`: Filter nach Status
- `type`: Filter nach Job-Typ
- `page`, `per_page`: Pagination

### GET /api/admin/jobs/{id}
Details eines einzelnen Jobs.

### GET /api/admin/jobs/summary
Zusammenfassung: Anzahl nach Status und Typ.

## Frontend

Die Jobs-Seite ist erreichbar unter `/admin/jobs`.
Zeigt: Typ, Status, Versuche, Zeitstempel, Ergebnis/Fehler.
