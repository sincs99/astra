"""Zentraler Permission-Katalog für Astra."""

# ── Alle gültigen Permissions ───────────────────────────

CONTROL_PERMISSIONS = [
    "control.console",
    "control.start",
    "control.stop",
    "control.restart",
]

FILE_PERMISSIONS = [
    "file.read",
    "file.update",
    "file.delete",
    "file.sftp",  # M30: SFTP-/SSH-Key-Zugriff fuer Collaborators
]

BACKUP_PERMISSIONS = [
    "backup.read",
    "backup.create",
    "backup.restore",
    "backup.delete",
]

DATABASE_PERMISSIONS = [
    "database.read",
    "database.create",
    "database.update",
    "database.delete",
]

ALL_PERMISSIONS: list[str] = (
    CONTROL_PERMISSIONS + FILE_PERMISSIONS + BACKUP_PERMISSIONS + DATABASE_PERMISSIONS
)

# Power-Signal → benötigte Permission
POWER_SIGNAL_PERMISSIONS: dict[str, str] = {
    "start": "control.start",
    "stop": "control.stop",
    "restart": "control.restart",
    "kill": "control.stop",  # Kill benötigt Stop-Permission
}


def is_valid_permission(permission: str) -> bool:
    """Prüft ob eine Permission gültig ist."""
    return permission in ALL_PERMISSIONS


def validate_permissions(permission_list: list[str]) -> tuple[bool, list[str]]:
    """
    Validiert eine Liste von Permissions.
    Gibt (ok, invalid_permissions) zurück.
    """
    invalid = [p for p in permission_list if not is_valid_permission(p)]
    return len(invalid) == 0, invalid
