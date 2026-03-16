# Release Candidate Checklist (M27)

## Kritische End-to-End-Flows

Die folgenden 12 Kernflows muessen vor einem Release funktionieren.

### 1. Agent anlegen
- POST /api/admin/agents mit name + fqdn
- Agent erscheint in Liste
- to_dict enthaelt alle Felder inkl. maintenance_mode, capacity

### 2. Blueprint anlegen
- POST /api/admin/blueprints mit name
- Blueprint erscheint in Liste

### 3. Instance erstellen
- POST /api/admin/instances mit name, owner_id, agent_id, blueprint_id
- Instance erhaelt UUID und Status "provisioning"
- Runner-Hook wird aufgerufen (Stub: sofort ok)
- Endpoint wird zugewiesen

### 4. Install/Ready-Flow
- POST /api/agent/instances/{uuid}/install mit successful=true
- Status wechselt zu ready (null)
- installed_at wird gesetzt
- Activity-Event wird geloggt

### 5. Console verbinden
- GET /api/client/instances/{uuid}/websocket liefert Token + Socket-URL
- Console-Komponente kann sich verbinden (Wings oder Stub)

### 6. Dateien lesen/schreiben/loeschen
- GET /api/client/instances/{uuid}/files
- GET /api/client/instances/{uuid}/files/content
- POST /api/client/instances/{uuid}/files/write
- POST /api/client/instances/{uuid}/files/delete

### 7. Backup erstellen / wiederherstellen / loeschen
- POST /api/client/instances/{uuid}/backups
- POST /api/client/instances/{uuid}/backups/{uuid}/restore
- DELETE /api/client/instances/{uuid}/backups/{uuid}

### 8. Collaborator + Rechte
- POST /api/client/instances/{uuid}/collaborators
- PATCH /api/client/instances/{uuid}/collaborators/{id}
- DELETE /api/client/instances/{uuid}/collaborators/{id}
- Rechtepruefung funktioniert korrekt

### 9. Database erstellen / rotieren / loeschen
- POST /api/client/instances/{uuid}/databases
- POST .../databases/{id}/rotate-password
- DELETE .../databases/{id}

### 10. Routine starten / Job-Verarbeitung
- POST /api/client/instances/{uuid}/routines/{id}/execute
- Routine wird als Job enqueued (SyncQueue: sofort)
- Actions werden als Folge-Jobs verarbeitet
- Job-Status ist nachvollziehbar in /admin/jobs

### 11. Webhook ausloesen / Retry
- Event dispatchen (z.B. instance:created)
- Webhook-Job wird erstellt
- Bei Fehlschlag: Retry-Versuche mit Delay
- Delivery-Tracking in DB

### 12. Agent Maintenance
- POST /api/admin/agents/{id}/maintenance
- Neues Deployment auf Maintenance-Agent -> 409
- DELETE /api/admin/agents/{id}/maintenance
- Deployment wieder moeglich

## Blocker-Kriterien

Ein Flow gilt als **Blocker**, wenn:
- Die API einen unkontrollierten Fehler (500) zurueckgibt
- Daten inkonsistent in der DB landen
- Secrets in Responses oder Logs auftauchen
- Auth-/Rechte-Pruefungen umgangen werden koennen
- Der Frontend-Build fehlschlaegt

## Akzeptable Known Limitations

Siehe [known-limitations.md](known-limitations.md)
