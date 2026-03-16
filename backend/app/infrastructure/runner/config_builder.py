"""ConfigBuilder – Erstellt Wings-kompatible Server-Konfigurationen.

Erzeugt das JSON-Format, das Wings für create/sync erwartet.
Basiert auf dem Referenzformat aus ServerConfigurationStructureService.
"""

from app.domain.instances.models import Instance
from app.domain.endpoints.models import Endpoint
from app.domain.blueprints.models import Blueprint


def build_server_config(instance: Instance) -> dict:
    """Erstellt die vollständige Wings-kompatible Server-Konfiguration.

    Format orientiert sich an Pelican/Pterodactyl Wings API:
    - id, uuid, meta
    - suspended
    - environment
    - invocation (startup_command)
    - build (Ressourcenlimits)
    - container (Docker-Image)
    - allocations (Netzwerk-Ports)
    """

    # Primary Endpoint laden
    primary_ep = None
    if instance.primary_endpoint_id:
        primary_ep = Endpoint.query.get(instance.primary_endpoint_id)

    # Alle Endpoints dieser Instance laden für Mappings
    instance_endpoints = Endpoint.query.filter_by(instance_id=instance.id).all()

    return {
        "id": instance.id,
        "uuid": instance.uuid,
        "meta": {
            "name": instance.name,
            "description": instance.description or "",
        },
        "suspended": instance.status == "suspended",
        "environment": _build_environment(instance),
        "invocation": instance.startup_command or "",
        "skip_egg_scripts": False,
        "build": _build_limits(instance),
        "container": _build_container(instance),
        "allocations": _build_allocations(primary_ep, instance_endpoints),
    }


def _build_environment(instance: Instance) -> dict:
    """Erstellt die Umgebungsvariablen für den Container.

    Reihenfolge (letzte gewinnt):
    1. Blueprint-Variablen-Defaults
    2. Instance-spezifische variable_values
    3. System-Variablen (STARTUP, SERVER_MEMORY, SERVER_IP, SERVER_PORT)
    """
    env: dict = {}

    # 1. Blueprint-Variablen-Defaults laden
    if instance.blueprint_id:
        blueprint = Blueprint.query.get(instance.blueprint_id)
        if blueprint:
            env.update(blueprint.get_default_env())

    # 2. Instance-spezifische Werte überschreiben
    for key, value in (instance.variable_values or {}).items():
        env[key] = str(value) if value is not None else ""

    # 3. System-Variablen (immer gesetzt, überschreiben alles)
    env["STARTUP"] = instance.startup_command or ""
    env["SERVER_MEMORY"] = str(instance.memory)
    env["SERVER_IP"] = "0.0.0.0"
    env["SERVER_PORT"] = "25565"

    if instance.primary_endpoint_id:
        ep = Endpoint.query.get(instance.primary_endpoint_id)
        if ep:
            env["SERVER_IP"] = ep.ip or "0.0.0.0"
            env["SERVER_PORT"] = str(ep.port)

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
