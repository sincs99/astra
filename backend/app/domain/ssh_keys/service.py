"""Service-Logik fuer User-SSH-Keys (M28)."""

import logging

from app.extensions import db
from app.domain.ssh_keys.models import UserSshKey
from app.domain.ssh_keys.validator import SshKeyValidationError, validate_and_parse

logger = logging.getLogger(__name__)


class SshKeyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Lesen ────────────────────────────────────────────────


def list_user_ssh_keys(user_id: int) -> list[UserSshKey]:
    """Listet alle SSH-Keys eines Users."""
    return (
        UserSshKey.query.filter_by(user_id=user_id)
        .order_by(UserSshKey.created_at.desc())
        .all()
    )


def get_user_ssh_key(user_id: int, key_id: int) -> UserSshKey:
    """Holt einen SSH-Key – prueft ob er dem User gehoert."""
    key = db.session.get(UserSshKey, key_id)
    if not key or key.user_id != user_id:
        raise SshKeyError("SSH-Key nicht gefunden", 404)
    return key


# ── Erstellen ────────────────────────────────────────────


def create_user_ssh_key(user_id: int, name: str, public_key: str) -> UserSshKey:
    """Erstellt einen neuen SSH-Key fuer einen User.

    - Validiert das Key-Format
    - Berechnet den Fingerprint serverseitig
    - Verhindert Duplikate (gleicher Fingerprint pro User)
    """
    if not name or not name.strip():
        raise SshKeyError("Field 'name' is required")
    name = name.strip()
    if len(name) > 191:
        raise SshKeyError("'name' darf maximal 191 Zeichen haben")

    if not public_key or not public_key.strip():
        raise SshKeyError("Field 'public_key' is required")
    public_key = public_key.strip()

    # Validierung und Fingerprint-Berechnung
    try:
        _key_type, fingerprint = validate_and_parse(public_key)
    except SshKeyValidationError as e:
        raise SshKeyError(str(e), 400)

    # Duplikat pruefen
    existing = UserSshKey.query.filter_by(user_id=user_id, fingerprint=fingerprint).first()
    if existing:
        raise SshKeyError(
            f"Ein SSH-Key mit diesem Fingerprint existiert bereits: {existing.name}", 409
        )

    key = UserSshKey(
        user_id=user_id,
        name=name,
        fingerprint=fingerprint,
        public_key=public_key,
    )
    db.session.add(key)
    db.session.commit()

    logger.info("SSH-Key '%s' (Fingerprint: %s) fuer User %d erstellt", name, fingerprint, user_id)

    _log_event("ssh_key:created", user_id, key.id, f"SSH-Key '{name}' hinzugefuegt", {"fingerprint": fingerprint})

    return key


# ── Aktualisieren ────────────────────────────────────────


def update_user_ssh_key_name(user_id: int, key_id: int, name: str) -> UserSshKey:
    """Aktualisiert den Namen eines SSH-Keys."""
    key = get_user_ssh_key(user_id, key_id)

    if not name or not name.strip():
        raise SshKeyError("Field 'name' is required")
    name = name.strip()
    if len(name) > 191:
        raise SshKeyError("'name' darf maximal 191 Zeichen haben")

    key.name = name
    db.session.commit()

    logger.info("SSH-Key %d umbenannt zu '%s'", key_id, name)
    _log_event("ssh_key:updated", user_id, key.id, f"SSH-Key umbenannt zu '{name}'", {"fingerprint": key.fingerprint})

    return key


# ── Loeschen ─────────────────────────────────────────────


def delete_user_ssh_key(user_id: int, key_id: int) -> None:
    """Loescht einen SSH-Key."""
    key = get_user_ssh_key(user_id, key_id)

    name = key.name
    fingerprint = key.fingerprint

    db.session.delete(key)
    db.session.commit()

    logger.info("SSH-Key '%s' (Fingerprint: %s) geloescht", name, fingerprint)
    _log_event("ssh_key:deleted", user_id, None, f"SSH-Key '{name}' geloescht", {"fingerprint": fingerprint})


# ── Intern ───────────────────────────────────────────────


def _log_event(
    event: str,
    user_id: int,
    key_id: int | None,
    description: str,
    properties: dict,
) -> None:
    try:
        from app.domain.activity.service import log_event
        log_event(
            event=event,
            actor_id=user_id,
            actor_type="user",
            subject_id=key_id,
            subject_type="ssh_key",
            description=description,
            properties=properties,
        )
    except Exception as e:
        logger.warning("Activity-Event '%s' konnte nicht geloggt werden: %s", event, str(e))
