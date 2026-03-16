"""Service-Logik fuer Instances.

Enthaelt:
- Lifecycle-Konstanten
- Instance-Erstellung
- Power-Aktionen
- Container-Status-Update (M15)
- Install/Reinstall-Callback (M16)
- Reinstall-Flow (M16)
- Config-Update mit Auto-Sync (M16)
"""

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.domain.instances.models import Instance
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.users.models import User
from app.domain.endpoints.models import Endpoint
from app.infrastructure.runner.protocol import RunnerProtocol, PowerAction

logger = logging.getLogger(__name__)


# ── Lifecycle-Konstanten ────────────────────────────────

# Fachliche Lifecycle-Status (instance.status)
STATUS_PROVISIONING = "provisioning"
STATUS_PROVISION_FAILED = "provision_failed"
STATUS_REINSTALLING = "reinstalling"
STATUS_REINSTALL_FAILED = "reinstall_failed"
STATUS_RESTORING = "restoring"
STATUS_SUSPENDED = "suspended"
STATUS_TRANSFERRING = "transferring"
STATUS_TRANSFER_FAILED = "transfer_failed"
STATUS_READY = None  # None / null = bereit

# Alle gueltigen Lifecycle-Status-Werte
VALID_LIFECYCLE_STATUSES = {
    STATUS_PROVISIONING,
    STATUS_PROVISION_FAILED,
    STATUS_REINSTALLING,
    STATUS_REINSTALL_FAILED,
    STATUS_RESTORING,
    STATUS_SUSPENDED,
    STATUS_TRANSFERRING,
    STATUS_TRANSFER_FAILED,
    "stopped",  # Legacy-Default
}

# Gueltige Wings-Container-States (instance.container_state)
VALID_CONTAINER_STATES = {"running", "starting", "stopping", "stopped", "offline"}

# Felder, deren Aenderung einen Sync ausloesen soll
SYNCABLE_FIELDS = {"memory", "swap", "disk", "io", "cpu", "image", "startup_command"}


# ── Exceptions ──────────────────────────────────────────


class InstanceCreationError(Exception):
    """Fehler beim Erstellen einer Instance."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InstanceActionError(Exception):
    """Fehler bei einer Instance-Aktion."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Runner-Provider ─────────────────────────────────────

_runner: RunnerProtocol | None = None


def set_runner(runner: RunnerProtocol) -> None:
    """Globalen Runner setzen (wird beim App-Start aufgerufen)."""
    global _runner
    _runner = runner


def get_runner() -> RunnerProtocol:
    """Globalen Runner abrufen."""
    if _runner is None:
        raise RuntimeError("Runner ist nicht initialisiert. Bitte set_runner() aufrufen.")
    return _runner


# ── Instance erstellen ──────────────────────────────────


def create_instance(
    name: str,
    owner_id: int,
    agent_id: int,
    blueprint_id: int,
    description: str | None = None,
    endpoint_id: int | None = None,
    memory: int = 512,
    swap: int = 0,
    disk: int = 1024,
    io: int = 500,
    cpu: int = 100,
    image: str | None = None,
    startup_command: str | None = None,
    variable_values: dict | None = None,
) -> Instance:
    """
    Erstellt eine neue Instance mit Validierung, Endpoint-Zuweisung und Runner-Hook.

    Phase 1: Datenbankseitige Erstellung (Status: provisioning)
    Phase 2: Runner-Hook aufrufen
    """

    # 1. Owner pruefen
    owner = db.session.get(User, owner_id)
    if not owner:
        raise InstanceCreationError(f"User mit ID {owner_id} nicht gefunden", 404)

    # 2. Agent pruefen
    agent = db.session.get(Agent, agent_id)
    if not agent:
        raise InstanceCreationError(f"Agent mit ID {agent_id} nicht gefunden", 404)
    if not agent.is_active:
        raise InstanceCreationError(f"Agent '{agent.name}' ist nicht aktiv", 400)
    # M25: Maintenance-Guard – keine neuen Deployments auf Maintenance-Agents
    if agent.in_maintenance:
        raise InstanceCreationError(
            f"Agent '{agent.name}' befindet sich im Maintenance-Modus. "
            f"Neue Deployments sind nicht moeglich.", 409
        )

    # 3. Blueprint pruefen
    blueprint = db.session.get(Blueprint, blueprint_id)
    if not blueprint:
        raise InstanceCreationError(
            f"Blueprint mit ID {blueprint_id} nicht gefunden", 404
        )

    # 4. Endpoint finden oder pruefen
    endpoint = _resolve_endpoint(agent_id, endpoint_id)

    # Image und startup_command vom Blueprint uebernehmen, falls nicht explizit gesetzt
    if not image and blueprint.docker_image:
        image = blueprint.docker_image
    if not startup_command and blueprint.startup_command:
        startup_command = blueprint.startup_command

    # ── Phase 1: DB-Erstellung ──────────────────────────

    instance = Instance(
        name=name,
        description=description,
        owner_id=owner_id,
        agent_id=agent_id,
        blueprint_id=blueprint_id,
        status=STATUS_PROVISIONING,
        memory=memory,
        swap=swap,
        disk=disk,
        io=io,
        cpu=cpu,
        image=image,
        startup_command=startup_command,
        variable_values=variable_values or {},
    )
    db.session.add(instance)
    db.session.flush()  # ID generieren

    # Endpoint der Instance zuweisen
    endpoint.instance_id = instance.id
    instance.primary_endpoint_id = endpoint.id

    db.session.commit()

    # Activity Log
    from app.domain.activity.events import log_instance_event, INSTANCE_CREATED
    log_instance_event(INSTANCE_CREATED, instance.id, owner_id,
                       f"Instance '{name}' erstellt", {"agent_id": agent_id, "blueprint_id": blueprint_id})

    # ── Phase 2: Runner-Hook ────────────────────────────

    try:
        runner = get_runner()
        response = runner.create_instance(agent, instance)

        if not response.success:
            logger.warning(
                "Runner create_instance fehlgeschlagen: %s", response.message
            )
            instance.status = STATUS_PROVISION_FAILED
            db.session.commit()

            from app.domain.activity.events import log_instance_event, INSTANCE_INSTALL_FAILED
            log_instance_event(INSTANCE_INSTALL_FAILED, instance.id,
                               description=f"Erstinstallation fehlgeschlagen: {response.message}")

    except Exception as e:
        logger.error("Runner create_instance Fehler: %s", str(e))
        instance.status = STATUS_PROVISION_FAILED
        db.session.commit()

    return instance


# ── Power-Aktion ────────────────────────────────────────


def send_power_action(instance: Instance, action: PowerAction) -> dict:
    """Sendet eine Power-Aktion an eine Instance."""

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise InstanceActionError("Agent nicht gefunden", 404)

    runner = get_runner()
    response = runner.send_power_action(agent, instance, action)

    if not response.success:
        raise InstanceActionError(
            f"Power-Aktion '{action}' fehlgeschlagen: {response.message}", 502
        )

    return {"action": action, "message": response.message}


# ── Container-Status-Update (M15) ──────────────────────


def update_container_status(instance: Instance, state: str) -> Instance:
    """Wings/Agent meldet Container-Laufzeitstatus.

    Aktualisiert NUR instance.container_state (nicht instance.status).
    Nur bei tatsaechlicher Aenderung wird persistiert, Activity geloggt
    und Webhook dispatcht.
    """
    state = state.strip().lower() if state else ""

    if state not in VALID_CONTAINER_STATES:
        logger.warning(
            "Unbekannter Container-State '%s' fuer Instance %s – ignoriert",
            state, instance.uuid,
        )
        return instance

    old_state = instance.container_state

    # Nur bei echtem Wechsel persistieren
    if old_state == state:
        return instance

    instance.container_state = state
    db.session.commit()

    logger.info(
        "Instance %s (%s): container_state %s → %s",
        instance.name, instance.uuid, old_state or "None", state,
    )

    # Activity-Log + Webhook
    from app.domain.activity.events import log_instance_event, INSTANCE_CONTAINER_STATE_CHANGED
    log_instance_event(
        INSTANCE_CONTAINER_STATE_CHANGED,
        instance.id,
        description=f"Container-Status: {old_state or 'None'} → {state}",
        properties={"old_state": old_state, "new_state": state},
    )

    return instance


# ── Install-Callback (gehaertet M16) ───────────────────


def handle_install_callback(instance: Instance, successful: bool) -> Instance:
    """Agent meldet Installationsergebnis zurueck.

    Unterscheidet zwischen Erstinstallation und Reinstall anhand von instance.status:
    - status == 'provisioning' → Erstinstallation
    - status == 'reinstalling' → Reinstallation
    - status == None/ready → bereits fertig (idempotent)
    - andere Status → werden geloggt, aber nicht überschrieben

    Idempotent: Doppelte Erfolgs-/Fehlermeldungen erzeugen keinen Chaoszustand.
    """
    current_status = instance.status
    is_reinstall = current_status == STATUS_REINSTALLING
    is_transfer = current_status == STATUS_TRANSFERRING
    is_first_install = current_status == STATUS_PROVISIONING

    # Idempotenz: Wenn bereits ready, ignorieren
    if current_status is None and successful:
        logger.info(
            "Instance %s (%s): Install-Callback ignoriert (bereits ready)",
            instance.name, instance.uuid,
        )
        return instance

    if successful:
        instance.status = STATUS_READY  # None = ready

        # installed_at nur bei erstem Erfolg setzen
        if not instance.installed_at:
            instance.installed_at = datetime.now(timezone.utc)

        db.session.commit()

        if is_transfer:
            logger.info("Instance %s (%s): Transfer erfolgreich", instance.name, instance.uuid)
            from app.domain.activity.events import log_instance_event
            log_instance_event("instance.transfer.completed", instance.id,
                               description="Transfer erfolgreich abgeschlossen")
        elif is_reinstall:
            logger.info("Instance %s (%s): Reinstall erfolgreich", instance.name, instance.uuid)
            from app.domain.activity.events import log_instance_event, INSTANCE_REINSTALL_COMPLETED
            log_instance_event(INSTANCE_REINSTALL_COMPLETED, instance.id,
                               description="Reinstallation erfolgreich abgeschlossen")
        else:
            logger.info("Instance %s (%s): Installation erfolgreich", instance.name, instance.uuid)
            from app.domain.activity.events import log_instance_event, INSTANCE_INSTALL_COMPLETED
            log_instance_event(INSTANCE_INSTALL_COMPLETED, instance.id,
                               description="Installation erfolgreich abgeschlossen")
    else:
        if is_transfer:
            instance.status = STATUS_TRANSFER_FAILED
            logger.warning("Instance %s (%s): Transfer fehlgeschlagen", instance.name, instance.uuid)
            db.session.commit()
            from app.domain.activity.events import log_instance_event
            log_instance_event("instance.transfer.failed", instance.id,
                               description="Transfer fehlgeschlagen")
        elif is_reinstall:
            instance.status = STATUS_REINSTALL_FAILED
            logger.warning("Instance %s (%s): Reinstall fehlgeschlagen", instance.name, instance.uuid)
            db.session.commit()
            from app.domain.activity.events import log_instance_event, INSTANCE_REINSTALL_FAILED
            log_instance_event(INSTANCE_REINSTALL_FAILED, instance.id,
                               description="Reinstallation fehlgeschlagen")
        elif is_first_install:
            instance.status = STATUS_PROVISION_FAILED
            logger.warning("Instance %s (%s): Installation fehlgeschlagen", instance.name, instance.uuid)
            db.session.commit()
            from app.domain.activity.events import log_instance_event, INSTANCE_INSTALL_FAILED
            log_instance_event(INSTANCE_INSTALL_FAILED, instance.id,
                               description="Erstinstallation fehlgeschlagen")
        else:
            # Unerwarteter Zustand – loggen, aber stabilen Status beibehalten
            logger.warning(
                "Instance %s (%s): Install-Callback (failed) im Status '%s' – ignoriert",
                instance.name, instance.uuid, current_status,
            )
            db.session.commit()

    return instance


# ── Reinstall-Flow (M16) ───────────────────────────────


def reinstall_instance(instance: Instance) -> Instance:
    """Loest eine Reinstallation der Instance aus.

    - Setzt status auf 'reinstalling'
    - Ruft runner.create_instance() auf (gleicher Mechanismus wie Erstinstallation)
    - Bei Runner-Fehler: status → reinstall_failed
    """
    # Validierung: Darf nur bei existierender Instance
    if instance.status in (STATUS_PROVISIONING, STATUS_REINSTALLING):
        raise InstanceActionError(
            f"Instance ist bereits im Status '{instance.status}' – Reinstall nicht moeglich", 409
        )

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise InstanceActionError("Agent nicht gefunden", 404)

    # Status auf reinstalling setzen
    old_status = instance.status
    instance.status = STATUS_REINSTALLING
    db.session.commit()

    logger.info(
        "Instance %s (%s): Reinstall gestartet (vorher: %s)",
        instance.name, instance.uuid, old_status,
    )

    from app.domain.activity.events import log_instance_event, INSTANCE_REINSTALL_STARTED
    log_instance_event(INSTANCE_REINSTALL_STARTED, instance.id,
                       description=f"Reinstallation gestartet (vorheriger Status: {old_status})")

    # Runner aufrufen
    try:
        runner = get_runner()
        response = runner.create_instance(agent, instance)

        if not response.success:
            logger.warning(
                "Runner reinstall fehlgeschlagen: %s", response.message
            )
            instance.status = STATUS_REINSTALL_FAILED
            db.session.commit()

            from app.domain.activity.events import INSTANCE_REINSTALL_FAILED
            log_instance_event(INSTANCE_REINSTALL_FAILED, instance.id,
                               description=f"Reinstall-Runner-Fehler: {response.message}")

    except Exception as e:
        logger.error("Runner reinstall Fehler: %s", str(e))
        instance.status = STATUS_REINSTALL_FAILED
        db.session.commit()

    return instance


# ── Sync (M16) ─────────────────────────────────────────


def sync_instance(instance: Instance) -> dict:
    """Synchronisiert die Instance-Konfiguration mit dem Runner.

    Best-effort: Hauptaktion bleibt erfolgreich, Sync-Fehler wird geloggt.
    """
    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        raise InstanceActionError("Agent nicht gefunden", 404)

    try:
        runner = get_runner()
        response = runner.sync_instance(agent, instance)

        if response.success:
            logger.info("Instance %s (%s): Sync erfolgreich", instance.name, instance.uuid)

            from app.domain.activity.events import log_instance_event, INSTANCE_SYNCED
            log_instance_event(INSTANCE_SYNCED, instance.id,
                               description="Konfiguration synchronisiert")
            return {"success": True, "message": response.message}
        else:
            logger.warning("Instance %s (%s): Sync fehlgeschlagen: %s",
                           instance.name, instance.uuid, response.message)

            from app.domain.activity.events import log_instance_event, INSTANCE_SYNC_FAILED
            log_instance_event(INSTANCE_SYNC_FAILED, instance.id,
                               description=f"Sync fehlgeschlagen: {response.message}")
            return {"success": False, "message": response.message}

    except Exception as e:
        logger.error("Sync Fehler fuer Instance %s: %s", instance.uuid, str(e))
        return {"success": False, "message": f"Sync-Fehler: {str(e)}"}


# ── Config-Update mit Auto-Sync (M16) ──────────────────


def update_instance_config(instance: Instance, **changes) -> dict:
    """Aktualisiert Instance-Konfiguration und loest bei Bedarf einen Sync aus.

    Akzeptierte Felder: memory, swap, disk, io, cpu, image, startup_command, description, name

    Returns:
        {"instance": Instance, "synced": bool, "sync_message": str|None}
    """
    changed_syncable = set()

    for key, value in changes.items():
        if not hasattr(instance, key):
            continue

        old_value = getattr(instance, key)
        if old_value != value:
            setattr(instance, key, value)
            if key in SYNCABLE_FIELDS:
                changed_syncable.add(key)

    db.session.commit()

    # Sync nur wenn sync-relevante Felder geaendert wurden
    sync_result = None
    if changed_syncable:
        logger.info(
            "Instance %s (%s): Config-Aenderung %s – Sync wird ausgeloest",
            instance.name, instance.uuid, changed_syncable,
        )
        sync_result = sync_instance(instance)

    return {
        "instance": instance,
        "synced": sync_result is not None and sync_result.get("success", False) if sync_result else False,
        "sync_message": sync_result.get("message") if sync_result else None,
        "changed_fields": list(changed_syncable),
    }


# ── Hilfsfunktionen ─────────────────────────────────────


# ── Suspension (M29) ────────────────────────────────────


def is_instance_suspended(instance: Instance) -> bool:
    """Gibt True zurueck wenn die Instance administrativ suspendiert ist."""
    return instance.status == STATUS_SUSPENDED


def suspend_instance(instance: Instance, admin_user_id: int, reason: str | None = None) -> Instance:
    """Setzt eine Instance in den administrativen Suspension-Status.

    Idempotent: Wiederholtes Suspend auf bereits suspendierter Instance
    aktualisiert Grund und Zeitstempel.
    """
    from datetime import datetime, timezone

    instance.status = STATUS_SUSPENDED
    instance.suspended_reason = reason.strip() if reason and reason.strip() else None
    instance.suspended_at = datetime.now(timezone.utc)
    instance.suspended_by_user_id = admin_user_id
    db.session.commit()

    logger.info(
        "Instance %s (%s): suspendiert von User %d (Grund: %s)",
        instance.name, instance.uuid, admin_user_id, reason or "–",
    )

    from app.domain.activity.events import log_instance_event, INSTANCE_SUSPENDED
    log_instance_event(
        INSTANCE_SUSPENDED, instance.id,
        actor_id=admin_user_id,
        description=f"Instance suspendiert{f': {reason}' if reason else ''}",
        properties={"reason": reason, "by_user_id": admin_user_id},
    )

    return instance


def unsuspend_instance(instance: Instance, admin_user_id: int) -> Instance:
    """Hebt die Suspension einer Instance auf.

    Idempotent: Ist die Instance nicht suspendiert, passiert nichts.
    Setzt status auf None (ready) und loescht Suspension-Metadaten.
    """
    if instance.status != STATUS_SUSPENDED:
        logger.info(
            "Instance %s (%s): unsuspend aufgerufen, aber Status ist '%s' – ignoriert",
            instance.name, instance.uuid, instance.status,
        )
        return instance

    instance.status = STATUS_READY
    instance.suspended_reason = None
    instance.suspended_at = None
    instance.suspended_by_user_id = None
    db.session.commit()

    logger.info(
        "Instance %s (%s): Suspension aufgehoben von User %d",
        instance.name, instance.uuid, admin_user_id,
    )

    from app.domain.activity.events import log_instance_event, INSTANCE_UNSUSPENDED
    log_instance_event(
        INSTANCE_UNSUSPENDED, instance.id,
        actor_id=admin_user_id,
        description="Suspension aufgehoben",
        properties={"by_user_id": admin_user_id},
    )

    return instance


# ── Hilfsfunktionen ─────────────────────────────────────


def _resolve_endpoint(agent_id: int, endpoint_id: int | None) -> Endpoint:
    """
    Findet einen freien Endpoint fuer den Agent.
    Wenn endpoint_id angegeben, wird dieser geprueft.
    """

    if endpoint_id is not None:
        endpoint = db.session.get(Endpoint, endpoint_id)
        if not endpoint:
            raise InstanceCreationError(
                f"Endpoint mit ID {endpoint_id} nicht gefunden", 404
            )
        if endpoint.agent_id != agent_id:
            raise InstanceCreationError(
                f"Endpoint {endpoint_id} gehoert nicht zu Agent {agent_id}", 400
            )
        if endpoint.instance_id is not None:
            raise InstanceCreationError(
                f"Endpoint {endpoint_id} ist bereits belegt", 409
            )
        if endpoint.is_locked:
            raise InstanceCreationError(
                f"Endpoint {endpoint_id} ist gesperrt", 400
            )
        return endpoint

    # Automatisch ersten freien Endpoint finden
    endpoint = (
        Endpoint.query.filter_by(agent_id=agent_id, instance_id=None, is_locked=False)
        .order_by(Endpoint.port.asc())
        .first()
    )

    if not endpoint:
        raise InstanceCreationError(
            f"Kein freier Endpoint auf Agent {agent_id} verfuegbar", 409
        )

    return endpoint


# ── Server Transfer (Feature 3) ─────────────────────────


def transfer_instance(instance: Instance, target_agent_id: int) -> Instance:
    """Transferiert eine Instance von ihrem aktuellen Agent auf einen anderen.

    Ablauf:
    1. Ziel-Agent und freien Endpoint validieren
    2. Status → transferring
    3. Alten Agent via Runner löschen
    4. Alten Endpoint freigeben
    5. Neuen Endpoint und Agent zuweisen
    6. Neuen Agent via Runner erstellen
    7. Status bleibt 'transferring' bis Agent-Callback

    Bei Fehler: status → transfer_failed
    """
    if instance.agent_id == target_agent_id:
        raise InstanceActionError("Ziel-Agent ist derselbe wie der aktuelle Agent", 400)

    if instance.status in (STATUS_PROVISIONING, STATUS_REINSTALLING, STATUS_TRANSFERRING):
        raise InstanceActionError(
            f"Instance ist im Status '{instance.status}' – Transfer nicht möglich", 409
        )

    # Ziel-Agent validieren
    target_agent = db.session.get(Agent, target_agent_id)
    if not target_agent:
        raise InstanceActionError(f"Ziel-Agent {target_agent_id} nicht gefunden", 404)
    if not target_agent.is_active:
        raise InstanceActionError(f"Ziel-Agent '{target_agent.name}' ist nicht aktiv", 400)
    if target_agent.in_maintenance:
        raise InstanceActionError(
            f"Ziel-Agent '{target_agent.name}' befindet sich im Maintenance-Modus", 409
        )

    # Freien Endpoint auf Ziel-Agent finden
    try:
        new_endpoint = _resolve_endpoint(target_agent_id, None)
    except InstanceCreationError as e:
        raise InstanceActionError(e.message, e.status_code)

    old_agent = db.session.get(Agent, instance.agent_id)
    old_endpoint_id = instance.primary_endpoint_id

    # Status auf transferring setzen
    instance.status = STATUS_TRANSFERRING
    db.session.commit()

    logger.info(
        "Instance %s (%s): Transfer gestartet von Agent %s → Agent %s",
        instance.name, instance.uuid, instance.agent_id, target_agent_id,
    )

    from app.domain.activity.events import log_instance_event
    log_instance_event(
        "instance.transfer.started", instance.id,
        description=f"Transfer zu Agent '{target_agent.name}' gestartet",
        properties={"from_agent_id": instance.agent_id, "to_agent_id": target_agent_id},
    )

    # Alten Agent via Runner löschen (best-effort)
    if old_agent:
        try:
            runner = get_runner()
            runner.delete_instance(old_agent, instance)
        except Exception as e:
            logger.warning("Transfer: Löschen auf altem Agent fehlgeschlagen: %s", str(e))

    # Alten Endpoint freigeben
    if old_endpoint_id:
        old_ep = db.session.get(Endpoint, old_endpoint_id)
        if old_ep:
            old_ep.instance_id = None

    # Neuen Endpoint und Agent zuweisen
    new_endpoint.instance_id = instance.id
    instance.agent_id = target_agent_id
    instance.primary_endpoint_id = new_endpoint.id
    db.session.commit()

    # Auf neuem Agent erstellen
    try:
        runner = get_runner()
        response = runner.create_instance(target_agent, instance)

        if not response.success:
            logger.warning("Transfer: create_instance auf Ziel-Agent fehlgeschlagen: %s", response.message)
            instance.status = STATUS_TRANSFER_FAILED
            db.session.commit()
            log_instance_event(
                "instance.transfer.failed", instance.id,
                description=f"Transfer fehlgeschlagen: {response.message}",
            )

    except Exception as e:
        logger.error("Transfer: Runner-Fehler: %s", str(e))
        instance.status = STATUS_TRANSFER_FAILED
        db.session.commit()

    return instance
