"""Zentraler Action-Katalog für Routinen."""

VALID_ACTION_TYPES = {
    "send_command": {
        "description": "Sendet einen Befehl an die Server-Konsole",
        "required_payload": ["command"],
    },
    "power_action": {
        "description": "Sendet eine Power-Aktion (start/stop/restart/kill)",
        "required_payload": ["signal"],
        "valid_signals": ["start", "stop", "restart", "kill"],
    },
    "create_backup": {
        "description": "Erstellt ein Backup",
        "required_payload": ["name"],
    },
    "delete_files": {
        "description": "Löscht Dateien",
        "required_payload": ["path"],
    },
}


def is_valid_action_type(action_type: str) -> bool:
    return action_type in VALID_ACTION_TYPES


def validate_action_payload(action_type: str, payload: dict | None) -> tuple[bool, str]:
    """
    Validiert das Payload für einen Action-Typ.
    Gibt (ok, error_message) zurück.
    """
    if action_type not in VALID_ACTION_TYPES:
        return False, f"Ungültiger Action-Typ: {action_type}"

    spec = VALID_ACTION_TYPES[action_type]
    required = spec.get("required_payload", [])

    if not payload:
        if required:
            return False, f"Payload ist erforderlich mit Feldern: {', '.join(required)}"
        return True, ""

    missing = [f for f in required if f not in payload]
    if missing:
        return False, f"Fehlende Payload-Felder: {', '.join(missing)}"

    # Spezialvalidierung
    if action_type == "power_action":
        valid_signals = spec.get("valid_signals", [])
        if payload.get("signal") not in valid_signals:
            return False, f"Ungültiges Signal. Erlaubt: {', '.join(valid_signals)}"

    return True, ""
