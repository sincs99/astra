"""Import von Pterodactyl-/Pelican-Eggs als Astra-Blueprints.

Unterstuetzte Formate:
- Pterodactyl PTDL_v1/PTDL_v2 und Pelican PLCN_v1..v3 (`meta.version`), JSON oder YAML
- Natives Astra-Format (`"format": "astra"`), Felder wie im Blueprint-Modell

Mapping (Egg -> Blueprint):
    name, description              -> name, description
    docker_images (erstes Image)   -> docker_image  (Fallback: images/image/docker_image)
    startup / startup_commands     -> startup_command
    scripts.installation.*         -> install_script / install_container / install_entrypoint
    config.startup (JSON-String)   -> config_startup
    config.files   (JSON-String)   -> config_files
    config.stop                    -> config_stop
    file_denylist                  -> file_denylist
    variables[].env_variable       -> variables[].env_var

Die Pterodactyl-Platzhalter ({{server.build.default.port}} u.a.) bleiben unveraendert,
der config_builder versteht sowohl das Legacy- als auch das neue Schema.
"""

from __future__ import annotations

import json
from typing import Any

from app.extensions import db
from app.domain.blueprints.models import Blueprint

EGG_VERSION_PREFIXES = ("PTDL_", "PLCN_")
NATIVE_FORMAT = "astra"

# Wings-Konvention fuer Signal-Stopps in Eggs
_STOP_ALIASES = {"^C": "^SIGINT", "^^C": "^SIGKILL"}

_NATIVE_FIELDS = (
    "name", "description", "docker_image", "startup_command", "install_script",
    "install_container", "install_entrypoint", "variables", "config_schema",
    "config_startup", "config_stop", "config_files", "file_denylist",
)


class EggImportError(ValueError):
    """Eingabe ist kein gueltiges Egg/Blueprint."""


def detect_format(data: Any) -> str:
    """Gibt "astra" oder "egg" zurueck, sonst EggImportError."""
    if not isinstance(data, dict):
        raise EggImportError("Import-Daten muessen ein JSON-Objekt sein")
    if data.get("format") == NATIVE_FORMAT:
        return NATIVE_FORMAT
    version = str((data.get("meta") or {}).get("version", ""))
    if version.startswith(EGG_VERSION_PREFIXES):
        return "egg"
    config = data.get("config")
    if isinstance(config, dict) and ("files" in config or "startup" in config):
        return "egg"
    if "scripts" in data and "variables" in data:
        return "egg"
    raise EggImportError(
        "Unbekanntes Format: erwartet Pterodactyl/Pelican-Egg (meta.version PTDL_*/PLCN_*) "
        "oder natives Blueprint-JSON mit \"format\": \"astra\""
    )


def convert_egg(egg: dict) -> dict:
    """Wandelt ein Egg-Dict in Blueprint-Felder um (ohne DB-Zugriff)."""
    if not isinstance(egg, dict):
        raise EggImportError("Egg muss ein JSON-Objekt sein")
    name = egg.get("name")
    if not name or not isinstance(name, str):
        raise EggImportError("Egg hat keinen 'name'")

    install = (egg.get("scripts") or {}).get("installation") or {}
    config = egg.get("config") or {}

    return {
        "name": name.strip(),
        "description": egg.get("description"),
        "docker_image": _first_image(egg),
        "startup_command": _startup(egg),
        "install_script": install.get("script"),
        "install_container": install.get("container"),
        "install_entrypoint": install.get("entrypoint") or install.get("entry"),
        "variables": [_convert_variable(v) for v in egg.get("variables") or []],
        "config_startup": _json_field(config.get("startup"), "config.startup", dict),
        "config_stop": _stop(config.get("stop")),
        "config_files": _json_field(config.get("files"), "config.files", dict),
        "file_denylist": _denylist(egg.get("file_denylist")),
    }


def convert_native(data: dict) -> dict:
    """Uebernimmt die bekannten Blueprint-Felder aus einem nativen Export."""
    if not data.get("name"):
        raise EggImportError("Blueprint hat keinen 'name'")
    return {k: data[k] for k in _NATIVE_FIELDS if k in data}


def convert(data: Any) -> dict:
    return convert_native(data) if detect_format(data) == NATIVE_FORMAT else convert_egg(data)


def import_blueprint(data: Any) -> Blueprint:
    """Konvertiert, validiert und speichert ein Egg/Blueprint. Gibt das Blueprint zurueck."""
    fields = convert(data)
    # Gleiche Pruefung wie beim manuellen Anlegen (lazy, um Importzyklen zu vermeiden)
    from app.api.admin.routes import _validate_blueprint_process_fields
    err = _validate_blueprint_process_fields(fields)
    if err:
        raise EggImportError(err)
    blueprint = Blueprint(**fields)
    db.session.add(blueprint)
    db.session.commit()
    return blueprint


def export_native(blueprint: Blueprint) -> dict:
    """Natives Export-Format (Gegenstueck zu convert_native)."""
    out = {"format": NATIVE_FORMAT}
    out.update({k: getattr(blueprint, k) for k in _NATIVE_FIELDS})
    return out


# ── Helfer ──────────────────────────────────────────────


def _first_image(egg: dict) -> str | None:
    images = egg.get("docker_images")
    if isinstance(images, dict) and images:
        return str(next(iter(images.values())))
    if isinstance(images, list) and images:
        return str(images[0])
    legacy = egg.get("images")
    if isinstance(legacy, list) and legacy:
        return str(legacy[0])
    return egg.get("docker_image") or egg.get("image")


def _startup(egg: dict) -> str | None:
    if egg.get("startup"):
        return egg["startup"]
    commands = egg.get("startup_commands")  # Pelican: {label: command}
    if isinstance(commands, dict) and commands:
        return str(next(iter(commands.values())))
    return None


def _convert_variable(var: dict) -> dict:
    env = var.get("env_variable") or var.get("env_var")
    if not env:
        raise EggImportError(f"Variable '{var.get('name')}' hat keinen env_variable")
    default = var.get("default_value", "")
    if isinstance(default, bool):
        default = "true" if default else "false"
    out = {
        "name": var.get("name") or env,
        "description": var.get("description") or "",
        "env_var": str(env),
        "default_value": "" if default is None else str(default),
        "user_viewable": bool(var.get("user_viewable", True)),
        "user_editable": bool(var.get("user_editable", False)),
    }
    if var.get("rules"):
        rules = var["rules"]
        out["rules"] = "|".join(rules) if isinstance(rules, list) else str(rules)
    return out


def _json_field(value: Any, label: str, expected: type) -> Any:
    """Egg-Konfigurationen sind JSON-Strings (Pterodactyl) oder Objekte (Pelican/YAML)."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise EggImportError(f"'{label}' ist kein gueltiges JSON: {exc.msg}")
    if not isinstance(value, expected):
        raise EggImportError(f"'{label}' muss ein Objekt sein")
    return value


def _stop(value: Any) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    return _STOP_ALIASES.get(value, value)


def _denylist(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        raise EggImportError("'file_denylist' muss eine Liste sein")
    return [str(v) for v in value if v]
