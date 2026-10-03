"""Service-Logik für Backups."""

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.domain.backups.models import Backup
from app.domain.instances.models import Instance
from app.domain.agents.models import Agent
from app.domain.instances.service import get_runner

logger = logging.getLogger(__name__)


class BackupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _runner_completed(data: dict | None, default: bool | None = None) -> bool:
    """Hat der Runner den Auftrag bereits synchron abgeschlossen?

    - data.completed gesetzt -> massgeblich (Stub: True, Wings: False)
    - sonst: Checksum vorhanden -> abgeschlossen (Runner ohne completed-Flag), andernfalls `default`
    """
    data = data or {}
    if "completed" in data:
        return bool(data.get("completed"))
    if default is not None:
        return default
    return bool(data.get("checksum"))


def list_backups(instance: Instance) -> list[Backup]:
    """Listet alle Backups einer Instance."""
    return (
        Backup.query.filter_by(instance_id=instance.id)
        .order_by(Backup.created_at.desc())
        .all()
    )


def create_backup(
    instance: Instance,
    name: str,
    ignored_files: str | None = None,
) -> Backup:
    """Erstellt ein Backup via Runner (Stub oder Wings)."""

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise BackupError("Agent nicht gefunden", 500)

    # 1. Backup-Record anlegen
    backup = Backup(
        instance_id=instance.id,
        name=name,
        ignored_files=ignored_files,
        disk="runner",
        is_successful=False,
    )
    db.session.add(backup)
    db.session.flush()

    # 2. Runner aufrufen
    #    Stub: liefert sofort ein fertiges Ergebnis (data.completed = True).
    #    Wings: antwortet 202 Accepted und meldet das Ergebnis spaeter per
    #           POST /api/remote/backups/{uuid} – bis dahin bleibt is_successful=False.
    try:
        runner = get_runner()
        response = runner.create_backup(agent, instance, backup)

        if response.success and _runner_completed(response.data):
            backup.is_successful = True
            backup.completed_at = datetime.now(timezone.utc)
            backup.checksum = response.data.get("checksum")
            backup.bytes = response.data.get("bytes", 0)
            logger.info("Backup '%s' für Instance %s erfolgreich", name, instance.uuid)
        elif response.success:
            logger.info("Backup '%s' für Instance %s gestartet (Abschluss per Remote-Callback)", name, instance.uuid)
        else:
            logger.warning("Backup '%s' fehlgeschlagen: %s", name, response.message)

    except Exception as e:
        logger.error("Backup-Erstellung Fehler: %s", str(e))

    db.session.commit()

    if backup.is_successful:
        from app.domain.activity.events import log_instance_event, BACKUP_CREATED
        log_instance_event(BACKUP_CREATED, instance.id, description=f"Backup '{name}' erstellt", properties={"backup_uuid": backup.uuid})

    return backup


def restore_backup(instance: Instance, backup: Backup) -> Instance:
    """Stellt ein Backup wieder her via Runner (Stub oder Wings)."""

    if not backup.is_successful:
        raise BackupError("Nur erfolgreiche Backups können wiederhergestellt werden", 400)

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise BackupError("Agent nicht gefunden", 500)

    # Instance auf restoring setzen
    instance.status = "restoring"
    db.session.commit()

    try:
        runner = get_runner()
        response = runner.restore_backup(agent, instance, backup)

        if response.success and _runner_completed(response.data, default=False):
            instance.status = None  # ready
            logger.info("Restore von Backup '%s' für Instance %s erfolgreich", backup.name, instance.uuid)
        elif response.success:
            # Wings: Restore laeuft asynchron, Abschluss per POST /api/remote/backups/{uuid}/restore
            logger.info("Restore von Backup '%s' für Instance %s gestartet", backup.name, instance.uuid)
        else:
            instance.status = "provision_failed"
            logger.warning("Restore fehlgeschlagen: %s", response.message)

    except Exception as e:
        instance.status = "provision_failed"
        logger.error("Restore Fehler: %s", str(e))

    db.session.commit()
    return instance


def delete_backup(instance: Instance, backup: Backup) -> None:
    """Löscht ein Backup via Runner (Stub oder Wings)."""

    if backup.is_locked:
        raise BackupError("Gesperrtes Backup kann nicht gelöscht werden", 403)

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise BackupError("Agent nicht gefunden", 500)

    try:
        runner = get_runner()
        runner.delete_backup(agent, instance, backup)
    except Exception as e:
        logger.error("Backup-Löschung Runner-Fehler: %s", str(e))

    db.session.delete(backup)
    db.session.commit()
    logger.info("Backup '%s' für Instance %s gelöscht", backup.name, instance.uuid)
