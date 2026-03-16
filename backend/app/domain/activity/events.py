"""Vordefinierte Activity-Events und Convenience-Funktionen."""

from app.domain.activity.service import log_event


# ── Event-Namen ─────────────────────────────────────────

INSTANCE_CREATED = "instance:created"
INSTANCE_POWER = "instance:power"
INSTANCE_INSTALL = "instance:install_callback"
INSTANCE_CONTAINER_STATE_CHANGED = "instance:container_state_changed"

# M16: Install-/Reinstall-/Sync-Events
INSTANCE_INSTALL_COMPLETED = "instance:install_completed"
INSTANCE_INSTALL_FAILED = "instance:install_failed"
INSTANCE_REINSTALL_STARTED = "instance:reinstall_started"
INSTANCE_REINSTALL_COMPLETED = "instance:reinstall_completed"
INSTANCE_REINSTALL_FAILED = "instance:reinstall_failed"
INSTANCE_SYNCED = "instance:synced"
INSTANCE_SYNC_FAILED = "instance:sync_failed"

# M17/M19: Auth-Events
AUTH_LOGIN_SUCCESS = "auth:login_success"
AUTH_LOGIN_FAILED = "auth:login_failed"
AUTH_LOGOUT = "auth:logout"
AUTH_API_KEY_CREATED = "auth:api_key_created"
AUTH_API_KEY_DELETED = "auth:api_key_deleted"
AUTH_MFA_ENABLED = "auth:mfa_enabled"
AUTH_MFA_DISABLED = "auth:mfa_disabled"

# M18: Database-Events
DATABASE_CREATED = "database:created"
DATABASE_DELETED = "database:deleted"
DATABASE_PASSWORD_ROTATED = "database:password_rotated"

FILE_WRITTEN = "file:written"
FILE_DELETED = "file:deleted"
BACKUP_CREATED = "backup:created"
BACKUP_RESTORED = "backup:restored"
BACKUP_DELETED = "backup:deleted"
COLLABORATOR_ADDED = "collaborator:added"
COLLABORATOR_UPDATED = "collaborator:updated"
COLLABORATOR_REMOVED = "collaborator:removed"
ROUTINE_CREATED = "routine:created"
ROUTINE_DELETED = "routine:deleted"
ROUTINE_EXECUTED = "routine:executed"

# M25: Agent Maintenance-Events
AGENT_MAINTENANCE_ENABLED = "agent:maintenance_enabled"
AGENT_MAINTENANCE_DISABLED = "agent:maintenance_disabled"

# M28: SSH-Key-Events
SSH_KEY_CREATED = "ssh_key:created"
SSH_KEY_UPDATED = "ssh_key:updated"
SSH_KEY_DELETED = "ssh_key:deleted"

# M29: Suspension-Events
INSTANCE_SUSPENDED = "instance:suspended"
INSTANCE_UNSUSPENDED = "instance:unsuspended"

# M30: SFTP-/SSH-Key-Auth-Events
SSH_KEY_AUTH_SUCCESS = "ssh_key:auth_success"
SSH_KEY_AUTH_FAILED = "ssh_key:auth_failed"


# ── Convenience ─────────────────────────────────────────


def log_instance_event(
    event: str,
    instance_id: int,
    actor_id: int | None = None,
    description: str | None = None,
    properties: dict | None = None,
) -> None:
    """Loggt ein Instance-bezogenes Event."""
    log_event(
        event=event,
        actor_id=actor_id,
        subject_id=instance_id,
        subject_type="instance",
        description=description,
        properties=properties,
    )
