# Fleet Monitoring (M22)

## Übersicht

Das Fleet Monitoring bietet eine operative Übersicht über alle Agents.
Es zeigt Health-Status, Kapazität, Auslastung und Stale-Erkennung
auf einem zentralen Admin-Dashboard.

## Health-Status

Jeder Agent hat einen standardisierten Health-Status:

| Status        | Bedingung                                          | Farbe |
|---------------|---------------------------------------------------|-------|
| `healthy`     | Agent aktiv und innerhalb Schwellwert gesehen      | 🟢    |
| `stale`       | Agent aktiv, aber seit >10 Min. nicht gesehen      | 🟡    |
| `unreachable` | Agent aktiv, aber noch nie kontaktiert              | ⚫    |
| `degraded`    | Agent inaktiv / deaktiviert                         | 🔴    |

### Stale-Erkennung

- Schwellwert: konfigurierbar via Query-Parameter `stale_threshold` (Default: 10 Minuten)
- Basiert auf `last_seen_at` Feld im Agent-Modell
- Wird bei jedem Agent-Heartbeat via `agent.touch()` aktualisiert
- Wenn `last_seen_at` NULL ist → `unreachable`

## Kapazitätsberechnung

### Rohe Kapazität

Jeder Agent speichert seine Gesamtressourcen:
- `memory_total` – Gesamt-RAM in MB
- `disk_total` – Gesamt-Disk in MB
- `cpu_total` – Gesamt-CPU in % (z.B. 400 = 4 Kerne à 100%)

### Überallokation (Overalloc)

Pro Ressourcentyp kann ein Überallokationsfaktor in % definiert werden:
- `memory_overalloc` – z.B. 20 → 20% mehr zuweisbar
- `disk_overalloc` – z.B. 0 → keine Überallokation
- `cpu_overalloc` – z.B. 50 → 50% mehr zuweisbar

**Effektive Kapazität** = `total * (1 + overalloc/100)`

Beispiel: 8192 MB RAM mit 20% Overalloc → 9830 MB effektiv verfügbar.

### Auslastungsberechnung

Die Auslastung wird aus den zugewiesenen Instances berechnet:
- **used_memory** = Summe aller Instance-Memory-Werte auf diesem Agent
- **used_disk** = Summe aller Instance-Disk-Werte
- **used_cpu** = Summe aller Instance-CPU-Werte
- **utilization** = used / effective_capacity * 100

**Wichtig:** Diese Werte sind *zugewiesene* Ressourcen, keine Live-Messwerte.
Die tatsächliche Nutzung kann abweichen.

## Datenquellen

| Datum                  | Quelle      | Live? |
|------------------------|-------------|-------|
| Health-Status          | berechnet   | ✅ (aus DB) |
| last_seen_at           | DB          | ✅     |
| Kapazität (total)      | DB (Admin)  | ❌ (einmalig gesetzt) |
| Auslastung (used)      | berechnet   | ✅ (aus DB) |
| Instance-Count         | berechnet   | ✅ (aus DB) |
| Endpoint-Belegung      | berechnet   | ✅ (aus DB) |

## API-Endpunkte

### GET /api/admin/agents/monitoring

Liefert Monitoring-Daten für alle Agents.

**Query-Parameter:**
- `health` – Filter: `healthy`, `stale`, `degraded`, `unreachable`
- `search` – Textsuche in Name/FQDN
- `stale_threshold` – Schwellwert in Minuten (Default: 10)

### GET /api/admin/agents/{id}/monitoring

Monitoring-Daten für einen einzelnen Agent.

### GET /api/admin/fleet/summary

Globale Fleet-Kennzahlen:
- Anzahl Agents nach Status
- Gesamt-Kapazität und -Auslastung
- Anzahl Instances
- Endpoint-Übersicht

## Frontend

Die Fleet-Monitoring-Seite ist erreichbar unter `/admin/agents/monitoring`.

Features:
- Fleet-Summary-Kacheln (Agents, Instances, Memory, Disk, CPU, Endpoints)
- Sortierbare Agent-Tabelle
- Health-Status-Filter
- Textsuche nach Name/FQDN
- Kapazitätsbalken für Memory/Disk/CPU
- Stale-Hinweise und farbige Status-Badges
