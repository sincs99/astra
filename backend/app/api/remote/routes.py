"""Wings Remote-API (M33) – Endpunkte, die der Wings-Daemon am Panel aufruft.

Pfade und Formate entsprechen `routes/api-remote.php` im Referenz-Panel, damit
ein unveraenderter Wings-Daemon (Pterodactyl oder Pelican) mit Astra arbeitet:

  GET  /api/remote/servers                      Server-Liste beim Wings-Boot (paginiert)
  POST /api/remote/servers/reset                Zustaende nach Wings-Neustart zuruecksetzen
  GET  /api/remote/servers/{uuid}               Server-Konfiguration (settings + process_configuration)
  GET  /api/remote/servers/{uuid}/install       Install-Container, Entrypoint, Script
  POST /api/remote/servers/{uuid}/install       Install-Ergebnis (successful, reinstall)
  POST /api/remote/servers/{uuid}/container/status   Container-Status (data.new_state)
  GET/POST /api/remote/servers/{uuid}/transfer/success|failure
  POST /api/remote/sftp/auth                    SFTP-Login (Passwort oder Public Key)
  POST /api/remote/activity                     Activity-Events von Wings
  GET  /api/remote/backups/{uuid}               S3-Presigned-URLs (nicht unterstuetzt -> 400)
  POST /api/remote/backups/{uuid}               Backup-Ergebnis (successful, checksum, size)
  POST /api/remote/backups/{uuid}/restore       Restore-Ergebnis

Jeder Request wird ueber `Authorization: Bearer {token_id}.{token}` dem Agent zugeordnet.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.api.remote.auth import authenticate_agent_request, current_agent
from app.domain.instances.models import Instance
from app.domain.instances.service import (
    handle_install_callback,
    update_container_status,
    STATUS_PROVISIONING,
    STATUS_REINSTALLING,
    STATUS_RESTORING,
    STATUS_TRANSFERRING,
    STATUS_TRANSFER_FAILED,
    STATUS_READY,
    STATUS_SUSPENDED,
)
from app.domain.users.models import User
from app.domain.backups.models import Backup
from app.domain.collaborators.models import Collaborator
from app.infrastructure.runner.config_builder import (
    build_remote_server_payload,
    build_install_payload,
)

logger = logging.getLogger(__name__)

remote_bp = Blueprint("remote", __name__)
remote_bp.before_request(authenticate_agent_request)

# Wings-Container-States (environment.ProcessState) -> Astra container_state
_WINGS_STATE_MAP = {
    "offline": "offline",
    "starting": "starting",
    "running": "running",
    "stopping": "stopping",
    "stopped": "stopped",
}

# Astra-Permissions -> SFTP-Permissions, die Wings erwartet (sftp/server.go)
_SFTP_PERMISSION_MAP = {
    "file.read": ["file.read", "file.read-content"],
    "file.update": ["file.update", "file.create"],
    "file.delete": ["file.delete"],
}
_SFTP_ALL_PERMISSIONS = ["file.read", "file.read-content", "file.create", "file.update", "file.delete"]


# ── Hilfsfunktionen ─────────────────────────────────────


def _no_content():
    return "", 204


def _error(status: int, message: str):
    return jsonify({"error": message}), status


def _find_instance_for_agent(uuid: str) -> Instance | None:
    """Instance per UUID (voll oder Kurzform, 8 Zeichen) – nur auf dem anfragenden Agent."""
    agent = current_agent()
    query = Instance.query.filter(Instance.agent_id == agent.id)
    if len(uuid) == 8:
        return query.filter(Instance.uuid.like(f"{uuid}%")).first()
    return query.filter(Instance.uuid == uuid).first()


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return False


# ── Server ──────────────────────────────────────────────


@remote_bp.route("/servers", methods=["GET"])
def list_servers():
    """Alle Server des Agents, paginiert (Laravel-Pagination-Format, Wings liest data + meta)."""
    agent = current_agent()

    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = min(max(int(request.args.get("per_page", 50)), 1), 200)
    except ValueError:
        per_page = 50

    base_query = Instance.query.filter_by(agent_id=agent.id).order_by(Instance.id.asc())
    total = base_query.count()
    items = base_query.offset((page - 1) * per_page).limit(per_page).all()
    last_page = max((total + per_page - 1) // per_page, 1)

    data = []
    for instance in items:
        payload = build_remote_server_payload(instance)
        data.append({
            "uuid": instance.uuid,
            "settings": payload["settings"],
            "process_configuration": payload["process_configuration"],
        })

    first = (page - 1) * per_page + 1 if items else None
    last = (page - 1) * per_page + len(items) if items else None

    return jsonify({
        "data": data,
        "links": {
            "first": f"{request.base_url}?page=1",
            "last": f"{request.base_url}?page={last_page}",
            "prev": f"{request.base_url}?page={page - 1}" if page > 1 else None,
            "next": f"{request.base_url}?page={page + 1}" if page < last_page else None,
        },
        "meta": {
            "current_page": page,
            "from": first,
            "last_page": last_page,
            "links": [],
            "path": request.base_url,
            "per_page": per_page,
            "to": last,
            "total": total,
        },
    })


@remote_bp.route("/servers/reset", methods=["POST"])
def reset_servers():
    """Wings wurde neu gestartet: haengende Install-/Restore-Zustaende aufloesen."""
    agent = current_agent()
    stuck = Instance.query.filter(
        Instance.agent_id == agent.id,
        Instance.status.in_([STATUS_PROVISIONING, STATUS_REINSTALLING, STATUS_RESTORING]),
    ).all()

    for instance in stuck:
        logger.info(
            "Remote-API reset: Instance %s (%s) von '%s' auf ready gesetzt (Agent-Neustart)",
            instance.name, instance.uuid, instance.status,
        )
        instance.status = STATUS_READY
    if stuck:
        db.session.commit()

    return _no_content()


@remote_bp.route("/servers/<uuid>", methods=["GET"])
def server_details(uuid: str):
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")
    return jsonify(build_remote_server_payload(instance))


@remote_bp.route("/servers/<uuid>/install", methods=["GET"])
def server_install_details(uuid: str):
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")
    return jsonify(build_install_payload(instance))


@remote_bp.route("/servers/<uuid>/install", methods=["POST"])
def server_install_result(uuid: str):
    """Body: {"successful": bool, "reinstall": bool}"""
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")

    data = _json_body()
    if "successful" not in data:
        return _error(422, "The successful field is required.")

    successful = _as_bool(data.get("successful"))
    handle_install_callback(instance, successful)
    return _no_content()


@remote_bp.route("/servers/<uuid>/container/status", methods=["POST"])
def server_container_status(uuid: str):
    """Body: {"data": {"new_state": "running"}}"""
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")

    data = _json_body()
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    new_state = inner.get("new_state") or data.get("new_state") or ""
    mapped = _WINGS_STATE_MAP.get(str(new_state).strip().lower())
    if mapped:
        update_container_status(instance, mapped)
    else:
        logger.warning("Remote-API: unbekannter Container-State '%s' fuer %s", new_state, instance.uuid)

    return jsonify({})


@remote_bp.route("/servers/<uuid>/transfer/success", methods=["GET", "POST"])
def server_transfer_success(uuid: str):
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")
    if instance.status != STATUS_TRANSFERRING:
        return _error(409, "Server is not being transferred.")

    instance.status = STATUS_READY
    db.session.commit()
    from app.domain.activity.events import log_instance_event
    log_instance_event("instance.transfer.completed", instance.id,
                       description="Transfer vom Agent als erfolgreich gemeldet")
    return _no_content()


@remote_bp.route("/servers/<uuid>/transfer/failure", methods=["GET", "POST"])
def server_transfer_failure(uuid: str):
    instance = _find_instance_for_agent(uuid)
    if not instance:
        return _error(404, "The requested server was not found on this node.")
    if instance.status != STATUS_TRANSFERRING:
        return _error(409, "Server is not being transferred.")

    instance.status = STATUS_TRANSFER_FAILED
    db.session.commit()
    from app.domain.activity.events import log_instance_event
    log_instance_event("instance.transfer.failed", instance.id,
                       description="Transfer vom Agent als fehlgeschlagen gemeldet")
    return _no_content()


# ── SFTP ────────────────────────────────────────────────


def _parse_sftp_username(value: str) -> tuple[str, str]:
    """'user.serverid' -> ('user', 'serverid'); getrennt am LETZTEN Punkt."""
    value = (value or "").strip()
    if "." not in value:
        return value, ""
    username, _, server = value.rpartition(".")
    return username, server


def _sftp_permissions(user: User, instance: Instance) -> list[str] | None:
    """Liefert die SFTP-Permissions oder None, wenn der User keinen SFTP-Zugriff hat."""
    if instance.owner_id == user.id or user.is_admin:
        return list(_SFTP_ALL_PERMISSIONS)

    collab = Collaborator.query.filter_by(user_id=user.id, instance_id=instance.id).first()
    if not collab:
        return None
    perms = set(collab.permissions or [])
    if "file.sftp" not in perms:
        return None

    result: list[str] = []
    for astra_perm, wings_perms in _SFTP_PERMISSION_MAP.items():
        if astra_perm in perms:
            result.extend(wings_perms)
    return result


def _sftp_reject(username: str, reason: str, method: str):
    logger.info("Remote-API SFTP abgelehnt: user='%s' method=%s reason=%s", username, method, reason)
    return _error(403, "Authorization credentials were not correct, please try again.")


@remote_bp.route("/sftp/auth", methods=["POST"])
def sftp_auth():
    """Body: {"type": "password"|"public_key", "username": "user.serverid", "password": "..."}

    Bei type=public_key enthaelt "password" den OpenSSH-Public-Key.
    Antwort 200: {"user": ..., "server": <uuid>, "permissions": [...]}
    """
    data = _json_body()
    raw_username = str(data.get("username") or "")
    secret = data.get("password")
    auth_type = str(data.get("type") or "password").lower()

    if not raw_username or not isinstance(secret, str) or not secret:
        return _error(400, "The username and password fields are required.")

    username, server_identifier = _parse_sftp_username(raw_username)
    if not server_identifier or not username:
        return _error(400, "No valid server identifier was included in the request.")

    method = "public_key" if auth_type == "public_key" else "password"

    user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
    if not user:
        return _sftp_reject(username, "user_unknown", method)

    instance = _find_instance_for_agent(server_identifier)
    if not instance:
        return _sftp_reject(username, "instance_not_found", method)

    if method == "password":
        if not user.check_password(secret):
            from app.domain.activity.service import log_event
            try:
                log_event("auth:sftp_failed", actor_id=user.id, subject_id=instance.id,
                          subject_type="instance", description="SFTP-Login mit Passwort fehlgeschlagen",
                          properties={"method": "password"}, ip_address=request.remote_addr)
            except Exception:  # pragma: no cover
                pass
            return _sftp_reject(username, "bad_password", method)
    else:
        from app.domain.ssh_keys.auth_service import authorize_ssh_key_access, REASON_OK
        result = authorize_ssh_key_access(
            instance_uuid=instance.uuid,
            username=user.username,
            public_key=secret.strip(),
        )
        if result.reason != REASON_OK:
            return _sftp_reject(username, result.reason, method)

    if instance.status == STATUS_SUSPENDED:
        return _sftp_reject(username, "instance_suspended", method)

    permissions = _sftp_permissions(user, instance)
    if permissions is None:
        return _sftp_reject(username, "permission_denied", method)

    return jsonify({
        "user": str(user.id),
        "server": instance.uuid,
        "permissions": permissions,
    })


# ── Activity ────────────────────────────────────────────


def _parse_wings_timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _resolve_activity_user(value) -> User | None:
    """Wings liefert den Wert aus dem JWT-Claim user_uuid (bei Astra die User-ID als String)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return db.session.get(User, int(text))
    return User.query.filter_by(username=text).first()


@remote_bp.route("/activity", methods=["POST"])
def ingest_activity():
    """Body: {"data": [{"user", "server", "event", "metadata", "ip", "timestamp"}, ...]}"""
    from app.domain.activity.models import ActivityLog

    agent = current_agent()
    data = _json_body().get("data")
    if not isinstance(data, list):
        return _error(422, "The data field must be an array.")

    uuids = {str(d.get("server")) for d in data if isinstance(d, dict) and d.get("server")}
    instances = {
        i.uuid: i for i in Instance.query.filter(
            Instance.agent_id == agent.id, Instance.uuid.in_(list(uuids))
        ).all()
    } if uuids else {}

    stored = 0
    for datum in data:
        if not isinstance(datum, dict):
            continue
        event = str(datum.get("event") or "")
        instance = instances.get(str(datum.get("server")))
        if not instance or not event.startswith("server:"):
            continue

        metadata = datum.get("metadata") if isinstance(datum.get("metadata"), dict) else {}
        when = _parse_wings_timestamp(datum.get("timestamp"))
        if when is None:
            when = datetime.now(timezone.utc)
            metadata = dict(metadata, original_timestamp=datum.get("timestamp"))

        user = _resolve_activity_user(datum.get("user"))
        entry = ActivityLog(
            event=event,
            actor_id=user.id if user else None,
            actor_type="user" if user else "agent",
            subject_id=instance.id,
            subject_type="instance",
            description=None,
            properties=metadata,
            ip_address=str(datum.get("ip") or "") or None,
            created_at=when,
        )
        db.session.add(entry)
        stored += 1

    if stored:
        db.session.commit()

    return _no_content()


# ── Backups ─────────────────────────────────────────────


def _find_backup_for_agent(backup_uuid: str) -> tuple[Backup | None, Instance | None]:
    backup = Backup.query.filter_by(uuid=backup_uuid).first()
    if not backup:
        return None, None
    instance = db.session.get(Instance, backup.instance_id)
    if not instance or instance.agent_id != current_agent().id:
        return None, None
    return backup, instance


@remote_bp.route("/backups/<backup_uuid>", methods=["GET"])
def backup_upload_urls(backup_uuid: str):
    """S3-Multipart-Upload-URLs – Astra nutzt den lokalen Wings-Backup-Adapter."""
    backup, _ = _find_backup_for_agent(backup_uuid)
    if not backup:
        return _error(404, "The requested backup was not found.")
    return _error(400, "The configured backup adapter is not an S3 compatible adapter.")


@remote_bp.route("/backups/<backup_uuid>", methods=["POST"])
def backup_status(backup_uuid: str):
    """Body: {"successful": bool, "checksum": "...", "checksum_type": "sha1", "size": 123}"""
    backup, instance = _find_backup_for_agent(backup_uuid)
    if not backup:
        return _error(404, "The requested backup was not found.")
    if backup.is_successful:
        return _error(400, "Cannot update the status of a backup that is already marked as completed.")

    data = _json_body()
    successful = _as_bool(data.get("successful"))

    backup.is_successful = successful
    backup.completed_at = datetime.now(timezone.utc)
    if successful:
        checksum = data.get("checksum")
        checksum_type = data.get("checksum_type") or "sha1"
        backup.checksum = f"{checksum_type}:{checksum}" if checksum else None
        try:
            backup.bytes = int(data.get("size") or 0)
        except (TypeError, ValueError):
            backup.bytes = 0
    else:
        backup.is_locked = False
        backup.bytes = 0
        backup.checksum = None
    db.session.commit()

    from app.domain.activity.events import log_instance_event, BACKUP_CREATED
    if successful:
        log_instance_event(BACKUP_CREATED, instance.id,
                           description=f"Backup '{backup.name}' abgeschlossen",
                           properties={"backup_uuid": backup.uuid, "bytes": backup.bytes})
    else:
        log_instance_event("backup:failed", instance.id,
                           description=f"Backup '{backup.name}' fehlgeschlagen",
                           properties={"backup_uuid": backup.uuid})

    return _no_content()


@remote_bp.route("/backups/<backup_uuid>/restore", methods=["POST"])
def backup_restore_status(backup_uuid: str):
    """Body: {"successful": bool} – Instance verlaesst in jedem Fall den Status 'restoring'."""
    backup, instance = _find_backup_for_agent(backup_uuid)
    if not backup:
        return _error(404, "The requested backup was not found.")

    successful = _as_bool(_json_body().get("successful"))
    if instance.status == STATUS_RESTORING:
        instance.status = STATUS_READY
        db.session.commit()

    from app.domain.activity.events import log_instance_event, BACKUP_RESTORED
    log_instance_event(
        BACKUP_RESTORED if successful else "backup:restore_failed",
        instance.id,
        description=f"Restore von Backup '{backup.name}' {'abgeschlossen' if successful else 'fehlgeschlagen'}",
        properties={"backup_uuid": backup.uuid},
    )
    return _no_content()
