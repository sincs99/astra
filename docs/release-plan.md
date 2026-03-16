# Astra – Release-Plan: RC → Pilot → v1.0.0

> Stand: 2026-03-16 · Ergebnis von M32

---

## 1. Versions-Roadmap

```
v0.30.0  (aktuell)  ──── Milestone 30 abgeschlossen (SSH/SFTP-Auth)
v0.31.0             ──── M31: Gap-Analyse, Scope-Definition
v0.32.0-rc          ──── M32: Pilot-Plan, Release-Plan (dieses Dokument)
                         │
                         ▼  Scope-Freeze
v1.0.0-pilot        ──── Pilot-Build (internes Deployment)
                         │
                         ▼  Pilot (2–4 Wochen)
                         │  Nur Bugfixes / Security Fixes erlaubt
                         ▼
v1.0.0              ──── Go-Live-Entscheidung + Release-Tag
```

### Aktueller Stand

- **Version**: `0.32.0-rc` (nach M32)
- **Milestone-Abdeckung**: M10–M32 vollständig
- **RC-Status**: RC1 wurde mit M27 abgeschlossen, M28–M32 brachten vollständige Feature-Parity + Gap-Analyse
- **Nächster Schritt**: Pilot-Build und Pilotbetrieb starten

---

## 2. Was ändert sich noch vor v1.0

### Erlaubt (Bugfix-Window)

Zwischen Pilot-Start und `v1.0.0` sind ausschliesslich folgende Änderungen erlaubt:

| Typ | Kriterium |
|---|---|
| **Bugfix** | Direkt reproduzierbarer Fehler; beschränkt auf betroffene Stelle |
| **Security Fix** | Jede Auth-, Datenleck- oder Injektionslücke ist sofort P0 |
| **Ops-Fix** | Migration schlägt fehl, Container startet nicht, Health liefert falsch |
| **UX-Klarstellung** | Fehlermeldung unklar, Label falsch – kein Layout-Umbau |
| **Dokumentation** | Pilot-Protokoll, Ops-Guide, Release-Notes |

### Nicht erlaubt

- Neue Domänenmodule
- API-Breaking-Changes (neue Pflichtfelder, geänderte Response-Struktur)
- Schema-Migrationen ohne direkten Bugfix-Bezug
- Neue Frontendseiten oder Flows
- P1/P2-Features (Blueprint-Import, OAuth, Plugin-System usw.)

---

## 3. Go-Live-Kriterien für v1.0.0

Eine `v1.0.0`-Freigabe erfordert, dass **alle** der folgenden Punkte erfüllt sind:

### Pilot-Abschluss

- [ ] Alle 12 Pilot-Kernflows als **Pass** dokumentiert (siehe [pilot-rollout-plan.md](pilot-rollout-plan.md))
- [ ] Pilot läuft mindestens **5 Werktage ohne Blocker-Fund**
- [ ] Alle gefundenen Blocker sind behoben und re-getestet

### Qualität & Stabilität

- [ ] Keine offenen **Blocker** (Datenverlust, Auth-Bypass, Absturz)
- [ ] Keine offenen **Security-Blocker** (Secrets leaken, ungeschützte Admin-Endpunkte)
- [ ] Keine offenen **Datenverlust- oder Permission-Blocker**
- [ ] Alle Milestone-Tests (M10–M32) grün
- [ ] Frontend-Build (Vite) grün

### Upgrade & Recovery

- [ ] **Backup/Restore** für Astra selbst erfolgreich getestet (DB-Dump + Restore in neue Umgebung)
- [ ] **Upgrade-Test** erfolgreich: alte Version → neue Version → Preflight grün
- [ ] **Rollback-Test** erfolgreich: Downgrade ohne Datenverlust möglich

### Dokumentation

- [ ] `docs/known-limitations.md` aktuell
- [ ] `docs/v1-scope.md` aktuell
- [ ] `docs/operations.md` vollständig für Produktionsbetrieb
- [ ] Release-Notes für v1.0.0 finalisiert (dieser Plan, Abschnitt 5)

---

## 4. Rollback & Recovery

### Fehlgeschlagenes Release

Wenn nach Go-Live ein kritischer Fehler auftritt, der ein Rollback erzwingt:

```bash
# Sofortmassnahme: Astra stoppen
docker compose -f docker-compose.prod.yml down

# Backup einspielen (von direkt vor dem Release)
./scripts/restore.sh ./backups/astra_backup_<pre-release-timestamp>.tar.gz

# Code zurücksetzen
git checkout v0.32.0-rc   # oder letzter stabiler Tag vor v1.0.0
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Migration zurückrollen (falls neue Migrationen enthalten waren)
docker compose exec backend flask db downgrade -1

# Gesundheitscheck
curl https://astra.example.com/health/ready
```

### Fehlgeschlagene Migration

```bash
# Status ermitteln
docker compose exec backend flask db current

# Fehlerhafte Migration rückgängig machen
docker compose exec backend flask db downgrade -1

# Falls DB inkonsistent: aus Backup wiederherstellen
./scripts/restore.sh ./backups/astra_backup_YYYYMMDD.tar.gz
```

### Welche Daten müssen vor jedem Release gesichert sein

Vor **jedem** Release-Deployment sicherstellen:

```bash
# Vollständiges Backup (DB + Konfiguration)
./scripts/backup.sh ./backups/

# Manuell: nur Datenbank
docker compose exec postgres pg_dump -U astra astra --format=custom \
    > ./backups/astra_db_$(date +%Y%m%d_%H%M%S).dump
```

Backup enthält zwingend:
- PostgreSQL-Dump (`pg_dump` Custom-Format)
- `.env` Konfigurationsdatei
- Aktuelle Alembic-Revision (`flask db current` als Text)

---

## 5. Release-Notes v1.0.0

> Template – wird vor Go-Live finalisiert.

```markdown
# Astra v1.0.0 – Release Notes

**Release-Datum**: TBD
**Pilot-Zeitraum**: TBD
**Upgrade von**: 0.32.0-rc

## Highlights

Astra v1.0.0 ist der erste produktionsreife Release des Astra Server Management Panels.
v1.0.0 umfasst alle Kernfunktionen für den vollständigen Instance-Lifecycle-Betrieb,
Fleet-Management, SSH-/SFTP-Authentifizierung, Webhooks, Audit-Log und Background-Jobs.

## Was ist neu (gegenüber RC)

- [Pilot-Bugfixes werden hier eingetragen]

## Bekannte Einschränkungen

Siehe docs/known-limitations.md

## Post-v1.0-Roadmap (P1)

- Blueprint Import/Export-Format
- API-Key Permission-Scoping
- OAuth / SSO
- HTTP File Upload
- Mehrere Docker-Images pro Blueprint

## Upgrade-Anleitung

Siehe docs/upgrade-guide.md

## Rollback-Anleitung

Siehe docs/upgrade-guide.md#rollback
```

---

## 6. Versionierungs-Entscheidungen

### Semantische Versionierung

Astra folgt Semantic Versioning (SemVer):

| Version | Bedeutung |
|---|---|
| `1.x.0` | Neue Features, abwärtskompatibel |
| `1.0.x` | Bugfixes, kein API-Breaking-Change |
| `2.0.0` | Breaking Change (erfordert explizite Migration) |

### Branch-/Tag-Strategie

```
main        ← aktiver Entwicklungsstand
tags:
  v0.32.0-rc  ← aktueller RC
  v1.0.0      ← erster stabiler Release (nach Pilot)
  v1.0.x      ← Bugfix-Releases
```

### Build-Metadaten

Vor dem Release in der CI/CD-Pipeline setzen:

```bash
# Beispiel: Docker-Build mit Metadaten
docker build \
  --build-arg BUILD_SHA=$(git rev-parse HEAD) \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg BUILD_REF=v1.0.0 \
  -t astra-backend:1.0.0 .
```

Abrufbar über:
- `GET /ops/version` → `{ version, build_sha, build_date, build_ref }`
- `GET /api/admin/system/version` (authentifiziert)

---

## 7. Post-v1.0 – Nächste Schritte

Nach erfolgreichem v1.0.0-Release:

### Sofort (Patch-Phase)

- Pilotbetrieb weiterführen und Feedback einsammeln
- Minor-Bugs aus dem Pilot-Protokoll abarbeiten
- Known Limitations-Dokument aktualisieren

### Kurzfristig (v1.1)

- Blueprint Import/Export (P1)
- API-Key Permission-Scoping (P1)
- HTTP File Upload (P1)

### Mittelfristig (v1.2+)

- OAuth / SSO-Integration (P1)
- Mehrere Docker-Images pro Blueprint (P1)
- Backup Ignore-Patterns (P2)

### Langfristig / Nach Evaluation

- Plugin-System (P2)
- Multi-Language / i18n (P2)
- Kubernetes-Manifeste (P2)

Vollständige Roadmap: [v1-scope.md](v1-scope.md)
