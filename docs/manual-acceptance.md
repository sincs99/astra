# Manuelle Abnahme (M27)

## Anleitung

Diese Datei beschreibt die Schritt-fuer-Schritt-Abnahme fuer den Release Candidate.
Jeder Punkt hat ein erwartetes Ergebnis und Platz fuer Pass/Fail/Notes.

## Voraussetzungen

1. Backend laeuft (`python run.py`)
2. Frontend laeuft (`npm run dev`)
3. Admin-User existiert (`python cli.py bootstrap`)

---

## Flow 1: Login & Dashboard

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 1.1 | `/login` aufrufen | Login-Formular sichtbar | |
| 1.2 | Credentials eingeben + Login | Weiterleitung zu Dashboard | |
| 1.3 | Dashboard pruefen | Instances-Liste oder Empty State | |
| 1.4 | Navigation sichtbar | Alle Admin-Links vorhanden | |

## Flow 2: Agent erstellen

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 2.1 | /admin/agents oeffnen | Agents-Seite mit Formular | |
| 2.2 | Name + FQDN eingeben, erstellen | Agent erscheint in Liste | |
| 2.3 | Duplikat-FQDN versuchen | Fehlermeldung 409 | |

## Flow 3: Instance erstellen

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 3.1 | /admin/instances oeffnen | Formular sichtbar | |
| 3.2 | Alle Pflichtfelder ausfuellen | Instance wird erstellt (Status: provisioning) | |
| 3.3 | Instance-Detail oeffnen | UUID, Status, Ressourcen sichtbar | |

## Flow 4: Power-Aktionen

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 4.1 | Start-Button klicken | Aktion wird ausgefuehrt, Feedback | |
| 4.2 | Stop-Button klicken | Aktion wird ausgefuehrt | |
| 4.3 | Restart-Button klicken | Aktion wird ausgefuehrt | |

## Flow 5: Backup

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 5.1 | Backup erstellen | Backup in Liste sichtbar | |
| 5.2 | Backup wiederherstellen | Erfolgsmeldung | |
| 5.3 | Backup loeschen | Backup verschwindet aus Liste | |

## Flow 6: Fleet Monitoring

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 6.1 | /admin/agents/monitoring oeffnen | Agents mit Health/Kapazitaet sichtbar | |
| 6.2 | Fleet-Summary pruefen | Zahlen konsistent | |
| 6.3 | Status-Filter testen | Filterung funktioniert | |
| 6.4 | Suche testen | Suche funktioniert | |

## Flow 7: Maintenance

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 7.1 | Maintenance aktivieren | Badge erscheint, Grund gespeichert | |
| 7.2 | Deployment versuchen | Wird blockiert (409) | |
| 7.3 | Maintenance deaktivieren | Badge verschwindet | |
| 7.4 | Deployment erneut versuchen | Funktioniert wieder | |

## Flow 8: Jobs

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 8.1 | /admin/jobs oeffnen | Job-Liste sichtbar | |
| 8.2 | Summary-Kacheln pruefen | Zahlen konsistent | |
| 8.3 | Filter testen | Filterung funktioniert | |

## Flow 9: System Info

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 9.1 | /admin/system oeffnen | Version + Build-Info sichtbar | |
| 9.2 | Migration-Status pruefen | Up-to-date oder Hinweis | |
| 9.3 | Preflight-Check pruefen | Status sichtbar | |

## Flow 10: Ops-Endpunkte

| Schritt | Aktion | Erwartet | Pass/Fail |
|---------|--------|----------|-----------|
| 10.1 | GET /health | 200, status=ok | |
| 10.2 | GET /health/ready | 200, checks vorhanden | |
| 10.3 | GET /ops/version | Version + Build-Info | |
| 10.4 | GET /ops/upgrade-status | Migration-Status | |
| 10.5 | GET /ops/preflight | Checks + compatible | |

## Abnahme-Ergebnis

| Kategorie | Ergebnis |
|-----------|----------|
| Datum | |
| Pruefer | |
| Version | |
| Gesamt | Pass / Fail |
| Blocker | |
| Anmerkungen | |
