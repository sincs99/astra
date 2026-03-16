"""Konkrete Job-Handler (M23).

Jeder Handler ist eine Funktion: handler(payload: dict) -> str | None
Die Handler werden beim App-Start ueber setup_handlers() registriert.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from app.infrastructure.jobs.registry import (
    register_handler,
    JOB_TYPE_WEBHOOK_DISPATCH,
    JOB_TYPE_ROUTINE_EXECUTE,
    JOB_TYPE_ROUTINE_ACTION,
    JOB_TYPE_AGENT_HEALTH_CHECK,
    JOB_TYPE_INSTANCE_SYNC,
)

logger = logging.getLogger(__name__)


def setup_handlers() -> None:
    """Registriert alle bekannten Job-Handler."""
    register_handler(JOB_TYPE_WEBHOOK_DISPATCH, handle_webhook_dispatch)
    register_handler(JOB_TYPE_ROUTINE_EXECUTE, handle_routine_execute)
    register_handler(JOB_TYPE_ROUTINE_ACTION, handle_routine_action)
    register_handler(JOB_TYPE_AGENT_HEALTH_CHECK, handle_agent_health_check)
    register_handler(JOB_TYPE_INSTANCE_SYNC, handle_instance_sync)
    logger.debug("Alle Job-Handler registriert")


# ── Webhook Dispatch Job ────────────────────────────────


def handle_webhook_dispatch(payload: dict) -> str | None:
    """Sendet einen Webhook-Payload an einen einzelnen Webhook mit Retry.

    Erwartete Payload-Keys:
    - webhook_id: int
    - event: str
    - webhook_payload: dict (der eigentliche Payload)
    - max_retries: int (default 3)
    - retry_delays: list[int] (default [5, 15, 30])
    """
    import requests as http_requests
    from app.extensions import db
    from app.domain.webhooks.models import Webhook, WebhookDelivery

    webhook_id = payload.get("webhook_id")
    event = payload.get("event", "unknown")
    webhook_payload = payload.get("webhook_payload", {})
    max_retries = payload.get("max_retries", 3)
    retry_delays = payload.get("retry_delays", [5, 15, 30])

    webhook = db.session.get(Webhook, webhook_id)
    if not webhook:
        return f"Webhook {webhook_id} nicht gefunden - uebersprungen"

    REQUEST_TIMEOUT = (5, 10)
    last_error = None

    for attempt in range(max_retries):
        headers = {
            "Content-Type": "application/json",
            "X-Astra-Event": event,
            "X-Astra-Token": webhook.secret_token or "",
            "User-Agent": "Astra-Webhook/1.0",
        }

        try:
            response = http_requests.post(
                webhook.endpoint_url,
                json=webhook_payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            is_success = 200 <= response.status_code < 300
            logger.info(
                "Webhook %s -> %s: HTTP %d (Versuch %d)",
                webhook.uuid, webhook.endpoint_url, response.status_code, attempt + 1,
            )

            if is_success:
                _track_delivery(webhook, event, attempt + 1, True, response.status_code)
                return f"Webhook {webhook.uuid} erfolgreich: HTTP {response.status_code}"

            last_error = f"HTTP {response.status_code}"

        except http_requests.Timeout:
            last_error = "Timeout"
        except http_requests.ConnectionError:
            last_error = "Verbindungsfehler"
        except Exception as e:
            last_error = str(e)

        logger.warning(
            "Webhook %s Versuch %d/%d fehlgeschlagen: %s",
            webhook.uuid, attempt + 1, max_retries, last_error,
        )

        # Delay vor Retry
        if attempt < max_retries - 1:
            delay = retry_delays[attempt] if attempt < len(retry_delays) else retry_delays[-1]
            time.sleep(delay)

    # Alle Versuche fehlgeschlagen
    _track_delivery(webhook, event, max_retries, False, None, last_error)
    raise RuntimeError(
        f"Webhook {webhook.uuid}: Alle {max_retries} Versuche fehlgeschlagen: {last_error}"
    )


def _track_delivery(webhook, event: str, attempts: int, success: bool,
                     status_code: int | None, error: str | None = None) -> None:
    """Speichert Delivery-Ergebnis (best-effort)."""
    try:
        from app.extensions import db
        from app.domain.webhooks.models import WebhookDelivery

        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            endpoint_url=webhook.endpoint_url,
            attempts=attempts,
            success=success,
            status_code=status_code,
            error=error,
        )
        db.session.add(delivery)
        db.session.commit()
    except Exception as e:
        logger.debug("Delivery-Tracking fehlgeschlagen: %s", str(e))


# ── Routine Execute Job ─────────────────────────────────


def handle_routine_execute(payload: dict) -> str | None:
    """Fuehrt alle Actions einer Routine sequenziell als Jobs aus.

    Erstellt pro Action einen separaten ROUTINE_ACTION-Job.
    Bei delay_seconds > 0 wird der Job verzoegert.

    Erwartete Payload-Keys:
    - routine_id: int
    """
    from app.extensions import db
    from app.domain.routines.models import Routine, Action
    from app.domain.instances.models import Instance
    from app.infrastructure.jobs.queue import enqueue_job
    from app.infrastructure.jobs.registry import JOB_TYPE_ROUTINE_ACTION

    routine_id = payload.get("routine_id")
    routine = db.session.get(Routine, routine_id)
    if not routine:
        raise RuntimeError(f"Routine {routine_id} nicht gefunden")

    if routine.is_processing:
        return f"Routine '{routine.name}' wird bereits ausgefuehrt - uebersprungen"

    actions = Action.query.filter_by(routine_id=routine.id).order_by(Action.sequence).all()
    if not actions:
        return f"Routine '{routine.name}' hat keine Actions"

    instance = db.session.get(Instance, routine.instance_id)
    if not instance:
        raise RuntimeError(f"Instance {routine.instance_id} nicht gefunden")

    routine.is_processing = True
    db.session.commit()

    # Actions als einzelne Jobs enqueuen
    cumulative_delay = 0
    action_jobs = []

    for action in actions:
        cumulative_delay += action.delay_seconds

        action_job = enqueue_job(
            job_type=JOB_TYPE_ROUTINE_ACTION,
            payload={
                "routine_id": routine.id,
                "action_id": action.id,
                "instance_id": instance.id,
                "action_type": action.action_type,
                "payload": action.payload,
                "sequence": action.sequence,
                "continue_on_failure": action.continue_on_failure,
            },
            max_attempts=1,
            delay_seconds=cumulative_delay,
            payload_summary={
                "routine_id": routine.id,
                "action_type": action.action_type,
                "sequence": action.sequence,
            },
        )
        action_jobs.append(action_job.uuid)

    # Processing-Flag zuruecksetzen + last_run_at
    routine.is_processing = False
    routine.last_run_at = datetime.now(timezone.utc)
    db.session.commit()

    return f"Routine '{routine.name}': {len(action_jobs)} Action-Jobs erstellt"


# ── Routine Action Job ──────────────────────────────────


def handle_routine_action(payload: dict) -> str | None:
    """Fuehrt eine einzelne Routine-Action aus.

    Erwartete Payload-Keys:
    - routine_id: int
    - action_id: int
    - instance_id: int
    - action_type: str
    - payload: dict (Action-Payload)
    - sequence: int
    - continue_on_failure: bool
    """
    from app.extensions import db
    from app.domain.instances.models import Instance
    from app.domain.instances.service import send_power_action, get_runner
    from app.domain.agents.models import Agent

    instance_id = payload.get("instance_id")
    action_type = payload.get("action_type")
    action_payload = payload.get("payload") or {}
    sequence = payload.get("sequence", 0)
    routine_id = payload.get("routine_id")

    instance = db.session.get(Instance, instance_id)
    if not instance:
        raise RuntimeError(f"Instance {instance_id} nicht gefunden")

    logger.info(
        "Routine %s Action #%d (%s) auf Instance %s",
        routine_id, sequence, action_type, instance.uuid,
    )

    if action_type == "power_action":
        signal = action_payload.get("signal", "start")
        result = send_power_action(instance, signal)
        return result.get("message", "OK")

    elif action_type == "send_command":
        command = action_payload.get("command", "")
        logger.info("[ACTION] send_command: '%s' an Instance %s", command, instance.uuid)
        return f"Command '{command}' gesendet"

    elif action_type == "create_backup":
        from app.domain.backups.service import create_backup
        name = action_payload.get(
            "name",
            f"routine-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
        )
        backup = create_backup(instance=instance, name=name)
        return f"Backup '{backup.name}' erstellt (success={backup.is_successful})"

    elif action_type == "delete_files":
        path = action_payload.get("path", "")
        agent = db.session.get(Agent, instance.agent_id)
        if agent:
            runner = get_runner()
            result = runner.delete_file(agent, instance, path)
            return result.message
        return "Agent nicht gefunden"

    return f"Unbekannter Action-Typ: {action_type}"


# ── Agent Health Check Job (optional) ───────────────────


def handle_agent_health_check(payload: dict) -> str | None:
    """Prueft den Health-Status eines Agents.

    Erwartete Payload-Keys:
    - agent_id: int (optional, default: alle Agents)
    """
    from app.domain.agents.models import Agent
    from app.extensions import db

    agent_id = payload.get("agent_id")
    if agent_id:
        agents = [db.session.get(Agent, agent_id)]
        agents = [a for a in agents if a is not None]
    else:
        agents = Agent.query.filter_by(is_active=True).all()

    stale_count = sum(1 for a in agents if a.is_stale())
    return f"Health-Check: {len(agents)} Agents geprueft, {stale_count} stale"


# ── Instance Sync Job (optional) ────────────────────────


def handle_instance_sync(payload: dict) -> str | None:
    """Synchronisiert eine Instance mit dem Runner.

    Erwartete Payload-Keys:
    - instance_id: int
    """
    from app.extensions import db
    from app.domain.instances.models import Instance
    from app.domain.instances.service import get_runner
    from app.domain.agents.models import Agent

    instance_id = payload.get("instance_id")
    instance = db.session.get(Instance, instance_id)
    if not instance:
        return f"Instance {instance_id} nicht gefunden"

    agent = db.session.get(Agent, instance.agent_id)
    if not agent:
        return f"Agent {instance.agent_id} nicht gefunden"

    runner = get_runner()
    # Sync ist runner-spezifisch
    try:
        result = runner.sync_server(agent, instance)
        return f"Instance {instance.uuid} synchronisiert: {result.message if hasattr(result, 'message') else 'OK'}"
    except Exception as e:
        raise RuntimeError(f"Instance-Sync fehlgeschlagen: {e}")
