"""ConfigBuilder – Erstellt Wings-kompatible Server-Konfigurationen.

Erzeugt das JSON-Format, das Wings für create/sync erwartet und das die
Remote-API (`/api/remote/servers/...`) an Wings ausliefert.
Basiert auf dem Referenzformat aus ServerConfigurationStructureService
und EggConfigurationService.
"""

from __future__ import annotations

import re

from app.domain.instances.models import Instance
from app.domain.endpoints.models import Endpoint
from app.domain.blueprints.models import Blueprint

_PLACEHOLDER_RE = re.compile(r"{{(?P<key>[\w.-]*)}}")


def build_server_config(instance: Instance) -> dict:
    """Erstellt die vollständige Wings-kompatible Server-Konfiguration ("settings").

    Format orientiert sich an Pelican/Pterodactyl Wings API:
    - id, uuid, meta
    - suspended
    - environment
    - invocation (startup_command)
    - build (Ressourcenlimits)
    - container (Docker-Image)
    - allocations (Netzwerk-Ports)
    - egg (id, file_denylist, features)
    """

    # Primary Endpoint laden
    primary_ep = None
    if instance.primary_endpoint_id:
        primary_ep = Endpoint.query.get(instance.primary_endpoint_id)

    # Alle Endpoints dieser Instance laden für Mappings
    instance_endpoints = Endpoint.query.filter_by(instance_id=instance.id).all()

    blueprint = _get_blueprint(instance)

    return {
        "id": instance.id,
        "uuid": instance.uuid,
        "meta": {
            "name": instance.name,
            "description": instance.description or "",
        },
        "suspended": instance.status == "suspended",
        "environment": _build_environment(instance, blueprint, primary_ep),
        "invocation": instance.startup_command or "",
        "skip_egg_scripts": False,
        "build": _build_limits(instance),
        "container": _build_container(instance),
        "allocations": _build_allocations(primary_ep, instance_endpoints),
        "egg": _build_egg(blueprint),
    }


def build_process_configuration(instance: Instance, settings: dict | None = None) -> dict:
    """Erstellt die Wings-"process_configuration" (Startup-Erkennung, Stop, Config-Dateien).

    Entspricht EggConfigurationService::handle() im Referenz-Panel.
    """
    blueprint = _get_blueprint(instance)
    if settings is None:
        settings = build_server_config(instance)

    if blueprint:
        startup = {
            "done": blueprint.get_startup_done_lines(),
            "user_interaction": [],
            "strip_ansi": blueprint.get_startup_strip_ansi(),
        }
        stop = blueprint.get_stop_configuration()
        configs = _build_config_files(blueprint.config_files, settings)
    else:
        startup = {"done": [], "user_interaction": [], "strip_ansi": False}
        stop = {"type": "command", "value": "stop"}
        configs = []

    return {
        "startup": startup,
        "stop": stop,
        "configs": configs,
    }


def build_remote_server_payload(instance: Instance) -> dict:
    """Payload fuer GET /api/remote/servers/{uuid} bzw. ein Element der Server-Liste."""
    settings = build_server_config(instance)
    return {
        "settings": settings,
        "process_configuration": build_process_configuration(instance, settings),
    }


def build_install_payload(instance: Instance) -> dict:
    """Payload fuer GET /api/remote/servers/{uuid}/install."""
    blueprint = _get_blueprint(instance)
    if not blueprint:
        return {"container_image": "ghcr.io/pterodactyl/installers:debian", "entrypoint": "bash", "script": ""}
    return {
        "container_image": blueprint.get_install_container(),
        "entrypoint": blueprint.get_install_entrypoint(),
        "script": blueprint.install_script or "",
    }


# ── Hilfsfunktionen ─────────────────────────────────────


def _get_blueprint(instance: Instance) -> Blueprint | None:
    if not instance.blueprint_id:
        return None
    return Blueprint.query.get(instance.blueprint_id)


def _build_environment(instance: Instance, blueprint: Blueprint | None, primary_ep: Endpoint | None) -> dict:
    """Erstellt die Umgebungsvariablen für den Container.

    Reihenfolge (letzte gewinnt):
    1. Blueprint-Variablen-Defaults
    2. Instance-spezifische variable_values
    3. System-Variablen (STARTUP, SERVER_MEMORY, SERVER_IP, SERVER_PORT, P_SERVER_*)
    """
    env: dict = {}

    # 1. Blueprint-Variablen-Defaults laden
    if blueprint:
        env.update(blueprint.get_default_env())

    # 2. Instance-spezifische Werte überschreiben
    for key, value in (instance.variable_values or {}).items():
        env[key] = str(value) if value is not None else ""

    # 3. System-Variablen (immer gesetzt, überschreiben alles)
    env["STARTUP"] = instance.startup_command or ""
    env["SERVER_MEMORY"] = str(instance.memory)
    env["SERVER_IP"] = primary_ep.ip if (primary_ep and primary_ep.ip) else "0.0.0.0"
    env["SERVER_PORT"] = str(primary_ep.port) if primary_ep else "25565"
    # Pterodactyl-kompatible Zusatzvariablen (viele Eggs/Images erwarten sie)
    env["P_SERVER_UUID"] = instance.uuid
    env["P_SERVER_ALLOCATION_LIMIT"] = "1"

    return env


def _build_limits(instance: Instance) -> dict:
    """Erstellt die Ressourcen-Limits im Wings-Format."""
    return {
        "memory_limit": instance.memory,       # MB
        "swap": instance.swap,                  # MB
        "io_weight": instance.io,               # IO-Weight (10-1000)
        "cpu_limit": instance.cpu,              # CPU in % (100 = 1 Core)
        "threads": None,                        # CPU-Thread-Pinning (optional)
        "disk_space": instance.disk,            # MB
        "oom_killer": True,                     # OOM-Killer aktiviert
    }


def _build_container(instance: Instance) -> dict:
    """Erstellt die Container-Konfiguration."""
    return {
        "image": instance.image or "ghcr.io/pelican-eggs/generic:latest",
        "requires_rebuild": False,
    }


def _build_allocations(
    primary_ep: Endpoint | None,
    all_endpoints: list[Endpoint],
) -> dict:
    """Erstellt die Netzwerk-Allocation-Konfiguration im Wings-Format."""

    # Default Allocation
    default_ip = primary_ep.ip if primary_ep else "0.0.0.0"
    default_port = primary_ep.port if primary_ep else 25565

    # Mappings: IP → [Port, Port, ...]
    mappings: dict[str, list[int]] = {}
    for ep in all_endpoints:
        ip = ep.ip or "0.0.0.0"
        if ip not in mappings:
            mappings[ip] = []
        mappings[ip].append(ep.port)

    # Mindestens den Default-Port in Mappings haben
    if not mappings:
        mappings[default_ip] = [default_port]

    return {
        "force_outgoing_ip": False,
        "default": {
            "ip": default_ip,
            "port": default_port,
        },
        "mappings": mappings,
    }


def _build_egg(blueprint: Blueprint | None) -> dict:
    """Egg-/Blueprint-Metadaten, die Wings in der Server-Konfiguration erwartet."""
    if not blueprint:
        return {"id": "", "file_denylist": [], "features": []}
    return {
        "id": str(blueprint.id),
        "file_denylist": blueprint.get_file_denylist(),
        "features": [],
    }


# ── Config-Dateien (Platzhalter-Ersetzung) ──────────────


def _build_config_files(config_files, settings: dict) -> list[dict]:
    """Wandelt das Egg-Format `{"file": {"parser": ..., "find": {...}}}` in das
    Wings-Format `[{"file": ..., "parser": ..., "replace": [{"match", "replace_with"}]}]`.

    Platzhalter:
    - {{server.X.Y}}  -> Wert aus der Server-Konfiguration (settings)
    - {{server.build.default.port}} / {{server.build.env.X}} -> Legacy-Pfade (Pterodactyl-Eggs),
      werden auf allocations.default.* bzw. environment.* abgebildet
    - {{env.NAME}}    -> Wert aus settings["environment"]
    - {{config.X}}    -> bleibt stehen, wird von Wings selbst aufgeloest
    """
    if not isinstance(config_files, dict):
        return []

    result: list[dict] = []
    for file_name, data in config_files.items():
        if not isinstance(data, dict) or "find" not in data or not isinstance(data["find"], dict):
            continue

        entry = {k: v for k, v in data.items() if k != "find"}
        entry["file"] = file_name
        entry["replace"] = []

        for match, replace in _iterate_find(data["find"], settings):
            if isinstance(replace, dict):
                for if_value, replace_with in replace.items():
                    entry["replace"].append({
                        "match": match,
                        "if_value": if_value,
                        "replace_with": replace_with,
                    })
                continue
            entry["replace"].append({"match": match, "replace_with": replace})

        result.append(entry)

    return result


def _iterate_find(find: dict, settings: dict):
    """Ersetzt Platzhalter in allen Werten eines find-Objekts (rekursiv fuer if_value-Maps)."""
    for key, value in find.items():
        if isinstance(value, dict):
            yield key, {k: _replace_placeholders(v, settings) for k, v in value.items()}
        else:
            yield key, _replace_placeholders(value, settings)


def _replace_placeholders(value, settings: dict):
    if not isinstance(value, str):
        return value

    def _sub(match: re.Match) -> str:
        key = match.group("key")
        if key.startswith("config."):
            return match.group(0)  # Wings loest config.* selbst auf
        if key.startswith("server."):
            path = key[len("server."):]
            # Pterodactyl-Eggs nutzen das Legacy-Schema server.build.default.* / server.build.env.*
            if path.startswith("build.default."):
                path = "allocations.default." + path[len("build.default."):]
            elif path.startswith("build.env."):
                path = "environment." + path[len("build.env."):]
            return _to_str(_dig(settings, path))
        if key.startswith("env."):
            return _to_str(_dig(settings.get("environment", {}), key[len("env."):]))
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_sub, value)


def _dig(data, dotted: str):
    current = data
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current


def _to_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
