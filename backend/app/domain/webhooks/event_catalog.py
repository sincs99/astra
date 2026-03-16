"""Zentraler Webhook-Event-Katalog.

Definiert alle gueltigen Webhook-Eventnamen und stellt
Validierungsfunktionen bereit.  Basiert auf den bestehenden
Activity-Event-Konstanten aus app.domain.activity.events.
"""

from app.domain.activity.events import (
    INSTANCE_CREATED,
    INSTANCE_POWER,
    INSTANCE_CONTAINER_STATE_CHANGED,
    INSTANCE_INSTALL_COMPLETED,
    INSTANCE_INSTALL_FAILED,
    INSTANCE_REINSTALL_STARTED,
    INSTANCE_REINSTALL_COMPLETED,
    INSTANCE_REINSTALL_FAILED,
    INSTANCE_SYNCED,
    INSTANCE_SYNC_FAILED,
    BACKUP_CREATED,
    BACKUP_RESTORED,
    BACKUP_DELETED,
    FILE_WRITTEN,
    FILE_DELETED,
    COLLABORATOR_ADDED,
    COLLABORATOR_UPDATED,
    COLLABORATOR_REMOVED,
    ROUTINE_CREATED,
    ROUTINE_EXECUTED,
    DATABASE_CREATED,
    DATABASE_DELETED,
    DATABASE_PASSWORD_ROTATED,
    AGENT_MAINTENANCE_ENABLED,
    AGENT_MAINTENANCE_DISABLED,
    SSH_KEY_CREATED,
    SSH_KEY_DELETED,
    INSTANCE_SUSPENDED,
    INSTANCE_UNSUSPENDED,
    SSH_KEY_AUTH_SUCCESS,
    SSH_KEY_AUTH_FAILED,
)

# ── Offizieller Event-Katalog fuer Webhooks ──────────────
# Nur fachlich relevante Events – keine internen technischen Events.

WEBHOOK_EVENTS: dict[str, str] = {
    INSTANCE_CREATED: "Eine neue Instance wurde erstellt",
    INSTANCE_POWER: "Eine Power-Aktion wurde auf einer Instance ausgefuehrt",
    INSTANCE_CONTAINER_STATE_CHANGED: "Der Container-Status einer Instance hat sich geaendert",
    INSTANCE_INSTALL_COMPLETED: "Die Installation einer Instance wurde erfolgreich abgeschlossen",
    INSTANCE_INSTALL_FAILED: "Die Installation einer Instance ist fehlgeschlagen",
    INSTANCE_REINSTALL_STARTED: "Eine Reinstallation wurde gestartet",
    INSTANCE_REINSTALL_COMPLETED: "Die Reinstallation einer Instance wurde erfolgreich abgeschlossen",
    INSTANCE_REINSTALL_FAILED: "Die Reinstallation einer Instance ist fehlgeschlagen",
    INSTANCE_SYNCED: "Die Konfiguration einer Instance wurde synchronisiert",
    INSTANCE_SYNC_FAILED: "Die Synchronisation einer Instance-Konfiguration ist fehlgeschlagen",
    BACKUP_CREATED: "Ein Backup wurde erstellt",
    BACKUP_RESTORED: "Ein Backup wurde wiederhergestellt",
    BACKUP_DELETED: "Ein Backup wurde geloescht",
    FILE_WRITTEN: "Eine Datei wurde geschrieben",
    FILE_DELETED: "Eine Datei wurde geloescht",
    COLLABORATOR_ADDED: "Ein Collaborator wurde hinzugefuegt",
    COLLABORATOR_UPDATED: "Die Berechtigungen eines Collaborators wurden geaendert",
    COLLABORATOR_REMOVED: "Ein Collaborator wurde entfernt",
    ROUTINE_CREATED: "Eine Routine wurde erstellt",
    ROUTINE_EXECUTED: "Eine Routine wurde ausgefuehrt",
    DATABASE_CREATED: "Eine Datenbank wurde erstellt",
    DATABASE_DELETED: "Eine Datenbank wurde geloescht",
    DATABASE_PASSWORD_ROTATED: "Das Passwort einer Datenbank wurde rotiert",
    AGENT_MAINTENANCE_ENABLED: "Ein Agent wurde in den Maintenance-Modus versetzt",
    AGENT_MAINTENANCE_DISABLED: "Ein Agent wurde aus dem Maintenance-Modus genommen",
    SSH_KEY_CREATED: "Ein SSH-Key wurde zum Account hinzugefuegt",
    SSH_KEY_DELETED: "Ein SSH-Key wurde vom Account entfernt",
    INSTANCE_SUSPENDED: "Eine Instance wurde administrativ suspendiert",
    INSTANCE_UNSUSPENDED: "Die Suspension einer Instance wurde aufgehoben",
    SSH_KEY_AUTH_SUCCESS: "SFTP-Key-Authentifizierung erfolgreich",
    SSH_KEY_AUTH_FAILED: "SFTP-Key-Authentifizierung abgelehnt",
}

VALID_WEBHOOK_EVENTS: set[str] = set(WEBHOOK_EVENTS.keys())


def is_valid_webhook_event(event: str) -> bool:
    """Prueft, ob ein Event-Name im Webhook-Katalog enthalten ist."""
    return event in VALID_WEBHOOK_EVENTS


def validate_webhook_events(events: list[str]) -> tuple[bool, list[str]]:
    """Validiert eine Liste von Event-Namen.

    Returns:
        (True, [])  – wenn alle gueltig
        (False, [ungueltige...]) – wenn mindestens eines ungueltig
    """
    invalid = [e for e in events if not is_valid_webhook_event(e)]
    return (len(invalid) == 0, invalid)


def get_event_catalog() -> list[dict]:
    """Gibt den vollstaendigen Event-Katalog als Liste zurueck (fuer API)."""
    return [
        {"event": event, "description": desc}
        for event, desc in WEBHOOK_EVENTS.items()
    ]
