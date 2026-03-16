# Agent Maintenance (M25)

## Uebersicht

Maintenance ist ein bewusst administrativer Betriebszustand fuer Agents.
Er ist getrennt vom Health-Status und wird manuell durch Admins gesteuert.

## Was Maintenance bedeutet

- Agent nimmt **keine neuen Deployments** mehr an
- Bestehende Instances **laufen weiter** (kein automatisches Drain)
- Im Fleet-Monitoring **klar sichtbar** als MAINTENANCE Badge
- **Getrennt von Health**: Ein Agent kann `healthy` UND `maintenance` sein

## Was Maintenance NICHT bedeutet

- Kein automatisches Herunterfahren von Instances
- Kein automatischer Transfer zu anderen Agents
- Kein Einfluss auf bestehende Power-Aktionen oder Backups
- Keine Aenderung am Health-Status

## Felder im Agent-Modell

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `maintenance_mode` | bool | Ist der Agent im Maintenance-Modus? |
| `maintenance_reason` | string? | Optionaler Grund ("Hardware-Upgrade", "Netzwerk-Wartung", ...) |
| `maintenance_started_at` | datetime? | Zeitpunkt der Maintenance-Aktivierung |

## API-Endpunkte

### POST /api/admin/agents/{id}/maintenance
Setzt den Agent in Maintenance.

```json
{
  "reason": "Hardware-Upgrade geplant"
}
```

### DELETE /api/admin/agents/{id}/maintenance
Nimmt den Agent aus Maintenance.

### PATCH /api/admin/agents/{id}/maintenance
Aktualisiert den Maintenance-Grund.

```json
{
  "reason": "Neuer Grund"
}
```

## Auswirkungen auf Deployment

- `create_instance()` prueft `agent.in_maintenance`
- Wenn ein Maintenance-Agent als Ziel angegeben wird: HTTP 409
- Fehlermeldung: "Agent befindet sich im Maintenance-Modus"

## Idempotenz

- Wiederholtes `POST /maintenance` ist kein Fehler (idempotent)
- Wiederholtes `DELETE /maintenance` ist kein Fehler (idempotent)
- Activity-Events werden nur bei echtem Statuswechsel erzeugt

## Activity-/Webhook-Events

| Event | Beschreibung |
|-------|-------------|
| `agent:maintenance_enabled` | Agent in Maintenance gesetzt |
| `agent:maintenance_disabled` | Agent aus Maintenance genommen |

## Frontend

- Fleet-Monitoring-Seite zeigt Maintenance-Badge pro Agent
- Toggle-Button zum Aktivieren/Deaktivieren
- Optionaler Grund wird angezeigt
- Fleet-Summary zaehlt Maintenance-Agents
