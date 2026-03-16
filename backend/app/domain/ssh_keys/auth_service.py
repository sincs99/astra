"""SFTP-/SSH-Key-Authentifizierungs-Service (M30).

Zentrale Auth-Entscheidung fuer schluesselbasierte SFTP-Zugaenge.
Wird vom Agent-API-Endpunkt aufgerufen, wenn ein Benutzer sich via
SFTP mit einem SSH Public Key authentifizieren moechte.

Entscheidungsreihenfolge:
  1. Username → User existiert?
  2. Instance → Instance existiert?
  3. Key → key bekannt und gehoert diesem User?
  4. Zugriff → Owner oder Collaborator mit file.sftp?
  5. Suspension → Instance nicht gesperrt?
"""

import logging
from dataclasses import dataclass, field

from app.extensions import db
from app.domain.users.models import User
from app.domain.instances.models import Instance
from app.domain.ssh_keys.models import UserSshKey
from app.domain.ssh_keys.validator import (
    SshKeyValidationError,
    compute_fingerprint,
    SUPPORTED_KEY_TYPES,
)
from app.domain.collaborators.checker import can_access_instance
from app.domain.collaborators.models import Collaborator
from app.domain.instances.service import is_instance_suspended

logger = logging.getLogger(__name__)

# Moegliche Deny-Gruende (fuer Logging und Response)
REASON_OK = "ok"
REASON_USER_UNKNOWN = "user_unknown"
REASON_INSTANCE_NOT_FOUND = "instance_not_found"
REASON_KEY_UNKNOWN = "key_unknown"
REASON_PERMISSION_DENIED = "permission_denied"
REASON_INSTANCE_SUSPENDED = "instance_suspended"
REASON_MALFORMED = "malformed_request"


@dataclass
class SftpAuthResult:
    """Ergebnis einer SFTP-/SSH-Key-Auth-Entscheidung."""

    allowed: bool
    reason: str  # einer der REASON_*-Konstanten
    user_id: int | None = None
    username: str | None = None
    instance_uuid: str | None = None
    # Effektive Permissions des Users auf der Instance (nur bei allowed=True)
    permissions: list[str] = field(default_factory=list)


# ── Hilfsfunktionen ──────────────────────────────────────


def find_key_by_fingerprint(user_id: int, fingerprint: str) -> UserSshKey | None:
    """Sucht einen SSH-Key des Users anhand des Fingerprints."""
    return UserSshKey.query.filter_by(
        user_id=user_id, fingerprint=fingerprint
    ).first()


def find_key_by_public_key(user_id: int, public_key: str) -> UserSshKey | None:
    """Sucht einen SSH-Key des Users anhand des exakten Public Keys."""
    normalized = public_key.strip()
    return UserSshKey.query.filter_by(
        user_id=user_id, public_key=normalized
    ).first()


def find_user_key(
    user_id: int,
    public_key: str | None = None,
    fingerprint: str | None = None,
) -> UserSshKey | None:
    """Findet einen SSH-Key des Users – bevorzugt Fingerprint, dann Public Key.

    Wenn ein Public Key angegeben ist, wird der Fingerprint daraus berechnet
    (serverseitig, nicht blind dem Agent vertraut).
    """
    if public_key:
        try:
            fp = compute_fingerprint(public_key)
        except SshKeyValidationError:
            return None
        return find_key_by_fingerprint(user_id, fp)

    if fingerprint:
        return find_key_by_fingerprint(user_id, fingerprint)

    return None


def _get_effective_permissions(user_id: int, instance: Instance) -> list[str]:
    """Gibt die effektiven Permissions eines Users auf einer Instance zurueck.

    Owner haben alle Permissions; Collaborators die zugewiesenen.
    """
    if instance.owner_id == user_id:
        # Owner hat implizit alle Permissions
        from app.domain.collaborators.permissions import ALL_PERMISSIONS
        return list(ALL_PERMISSIONS)

    collab = Collaborator.query.filter_by(
        user_id=user_id, instance_id=instance.id
    ).first()
    if collab:
        return list(collab.permissions or [])
    return []


# ── Zentrale Auth-Entscheidung ───────────────────────────


def authorize_ssh_key_access(
    instance_uuid: str,
    username: str,
    public_key: str | None = None,
    fingerprint: str | None = None,
) -> SftpAuthResult:
    """Entscheidet, ob ein SSH-Key-Zugriff auf eine Instance erlaubt ist.

    Args:
        instance_uuid: UUID der Ziel-Instance.
        username:      Astra-Benutzername des anfragenden Users.
        public_key:    SSH Public Key (bevorzugt – Fingerprint wird serverseitig berechnet).
        fingerprint:   Alternativ: bereits berechneter Fingerprint (SHA256:...).
                       Wird nur genutzt wenn kein public_key angegeben ist.

    Returns:
        SftpAuthResult mit allowed=True/False und Grund.
    """
    # ── Eingabe-Validierung ─────────────────────────────
    if not username or not username.strip():
        return SftpAuthResult(allowed=False, reason=REASON_MALFORMED)
    if not instance_uuid or not instance_uuid.strip():
        return SftpAuthResult(allowed=False, reason=REASON_MALFORMED)
    if not public_key and not fingerprint:
        return SftpAuthResult(allowed=False, reason=REASON_MALFORMED)

    username = username.strip()

    # ── 1. User existiert? ──────────────────────────────
    user = User.query.filter_by(username=username).first()
    if not user:
        logger.info(
            "SFTP-Auth abgelehnt: Unbekannter User '%s' fuer Instance %s",
            username,
            instance_uuid[:8],
        )
        _log_auth_failure(
            reason=REASON_USER_UNKNOWN,
            username=username,
            instance_uuid=instance_uuid,
        )
        return SftpAuthResult(allowed=False, reason=REASON_USER_UNKNOWN)

    # ── 2. Instance existiert? ──────────────────────────
    instance = Instance.query.filter_by(uuid=instance_uuid).first()
    if not instance:
        logger.info(
            "SFTP-Auth abgelehnt: Instance %s nicht gefunden (User: %s)",
            instance_uuid,
            username,
        )
        _log_auth_failure(
            reason=REASON_INSTANCE_NOT_FOUND,
            username=username,
            instance_uuid=instance_uuid,
            user_id=user.id,
        )
        return SftpAuthResult(allowed=False, reason=REASON_INSTANCE_NOT_FOUND)

    # ── 3. Key dem User bekannt? ────────────────────────
    ssh_key = find_user_key(
        user_id=user.id,
        public_key=public_key,
        fingerprint=fingerprint,
    )
    if not ssh_key:
        logger.info(
            "SFTP-Auth abgelehnt: Key nicht bekannt fuer User '%s' auf Instance %s",
            username,
            instance_uuid[:8],
        )
        _log_auth_failure(
            reason=REASON_KEY_UNKNOWN,
            username=username,
            instance_uuid=instance_uuid,
            user_id=user.id,
            instance_id=instance.id,
        )
        return SftpAuthResult(
            allowed=False,
            reason=REASON_KEY_UNKNOWN,
            user_id=user.id,
            instance_uuid=instance_uuid,
        )

    # ── 4. Zugriffsberechtigung? ────────────────────────
    # Owner: immer erlaubt (sofern nicht suspendiert – Prüfung folgt)
    # Collaborator: braucht file.sftp
    is_owner = instance.owner_id == user.id

    if not is_owner:
        has_sftp_permission = can_access_instance(user.id, instance, "file.sftp")
        if not has_sftp_permission:
            logger.info(
                "SFTP-Auth abgelehnt: User '%s' hat keine file.sftp-Berechtigung auf Instance %s",
                username,
                instance_uuid[:8],
            )
            _log_auth_failure(
                reason=REASON_PERMISSION_DENIED,
                username=username,
                instance_uuid=instance_uuid,
                user_id=user.id,
                instance_id=instance.id,
                fingerprint=ssh_key.fingerprint,
            )
            return SftpAuthResult(
                allowed=False,
                reason=REASON_PERMISSION_DENIED,
                user_id=user.id,
                instance_uuid=instance_uuid,
            )

    # ── 5. Instance suspendiert? ────────────────────────
    if is_instance_suspended(instance):
        logger.info(
            "SFTP-Auth abgelehnt: Instance %s ist suspendiert (User: %s)",
            instance_uuid[:8],
            username,
        )
        _log_auth_failure(
            reason=REASON_INSTANCE_SUSPENDED,
            username=username,
            instance_uuid=instance_uuid,
            user_id=user.id,
            instance_id=instance.id,
            fingerprint=ssh_key.fingerprint,
        )
        return SftpAuthResult(
            allowed=False,
            reason=REASON_INSTANCE_SUSPENDED,
            user_id=user.id,
            instance_uuid=instance_uuid,
        )

    # ── Zugriff erlaubt ─────────────────────────────────
    effective_permissions = _get_effective_permissions(user.id, instance)

    logger.info(
        "SFTP-Auth erlaubt: User '%s' (role=%s) auf Instance %s",
        username,
        "owner" if is_owner else "collaborator",
        instance_uuid[:8],
    )
    _log_auth_success(
        user_id=user.id,
        instance_id=instance.id,
        fingerprint=ssh_key.fingerprint,
        username=username,
        instance_uuid=instance_uuid,
        is_owner=is_owner,
    )

    return SftpAuthResult(
        allowed=True,
        reason=REASON_OK,
        user_id=user.id,
        username=user.username,
        instance_uuid=instance_uuid,
        permissions=effective_permissions,
    )


# ── Logging-Hilfsfunktionen ──────────────────────────────


def _log_auth_success(
    user_id: int,
    instance_id: int,
    fingerprint: str,
    username: str,
    instance_uuid: str,
    is_owner: bool,
) -> None:
    try:
        from app.domain.activity.service import log_event
        log_event(
            event="ssh_key:auth_success",
            actor_id=user_id,
            actor_type="user",
            subject_id=instance_id,
            subject_type="instance",
            description=f"SFTP-Key-Auth erfolgreich: {username} auf Instance {instance_uuid[:8]}",
            properties={
                "username": username,
                "instance_uuid": instance_uuid,
                "fingerprint": fingerprint,
                "role": "owner" if is_owner else "collaborator",
            },
        )
    except Exception as exc:
        logger.warning("Activity-Event ssh_key:auth_success konnte nicht geloggt werden: %s", exc)


def _log_auth_failure(
    reason: str,
    username: str,
    instance_uuid: str,
    user_id: int | None = None,
    instance_id: int | None = None,
    fingerprint: str | None = None,
) -> None:
    """Loggt einen Auth-Fehler – keine sensiblen Key-Daten ausser Fingerprint."""
    try:
        from app.domain.activity.service import log_event
        props: dict = {
            "username": username,
            "instance_uuid": instance_uuid,
            "reason": reason,
        }
        # Nur Fingerprint (kein Public Key) loggen
        if fingerprint:
            props["fingerprint"] = fingerprint

        log_event(
            event="ssh_key:auth_failed",
            actor_id=user_id,
            actor_type="user" if user_id else None,
            subject_id=instance_id,
            subject_type="instance" if instance_id else None,
            description=f"SFTP-Key-Auth abgelehnt ({reason}): {username} auf Instance {instance_uuid[:8]}",
            properties=props,
        )
    except Exception as exc:
        logger.warning("Activity-Event ssh_key:auth_failed konnte nicht geloggt werden: %s", exc)
