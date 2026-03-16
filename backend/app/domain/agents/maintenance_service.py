"""Agent Maintenance Service (M25).

Verwaltet den Maintenance-Modus fuer Agents.
Idempotent, mit Activity- und Webhook-Events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.domain.agents.models import Agent

logger = logging.getLogger(__name__)


class MaintenanceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def enable_maintenance(
    agent_id: int,
    reason: str | None = None,
    actor_id: int | None = None,
) -> Agent:
    """Setzt einen Agent in den Maintenance-Modus.

    Idempotent: wiederholtes Aktivieren ist kein Fehler.
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        raise MaintenanceError(f"Agent mit ID {agent_id} nicht gefunden", 404)

    already_in_maintenance = bool(agent.maintenance_mode)

    agent.maintenance_mode = True
    agent.maintenance_reason = reason
    if not already_in_maintenance:
        agent.maintenance_started_at = datetime.now(timezone.utc)
    db.session.commit()

    logger.info("Agent '%s' (ID %d) in Maintenance gesetzt (reason=%s)",
                agent.name, agent.id, reason)

    # Activity-Event
    if not already_in_maintenance:
        _log_maintenance_event(
            event="agent:maintenance_enabled",
            agent=agent,
            actor_id=actor_id,
            description=f"Agent '{agent.name}' in Maintenance gesetzt",
            reason=reason,
        )

    return agent


def disable_maintenance(
    agent_id: int,
    actor_id: int | None = None,
) -> Agent:
    """Nimmt einen Agent aus dem Maintenance-Modus.

    Idempotent: wiederholtes Deaktivieren ist kein Fehler.
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        raise MaintenanceError(f"Agent mit ID {agent_id} nicht gefunden", 404)

    was_in_maintenance = bool(agent.maintenance_mode)

    agent.maintenance_mode = False
    agent.maintenance_reason = None
    agent.maintenance_started_at = None
    db.session.commit()

    logger.info("Agent '%s' (ID %d) aus Maintenance genommen", agent.name, agent.id)

    # Activity-Event
    if was_in_maintenance:
        _log_maintenance_event(
            event="agent:maintenance_disabled",
            agent=agent,
            actor_id=actor_id,
            description=f"Agent '{agent.name}' aus Maintenance genommen",
        )

    return agent


def _log_maintenance_event(
    event: str,
    agent: Agent,
    actor_id: int | None = None,
    description: str | None = None,
    reason: str | None = None,
) -> None:
    """Loggt ein Maintenance-Event in Activity und dispatcht Webhook."""
    try:
        from app.domain.activity.service import log_event
        props = {"agent_id": agent.id, "agent_name": agent.name}
        if reason:
            props["reason"] = reason

        log_event(
            event=event,
            actor_id=actor_id,
            actor_type="admin",
            subject_id=agent.id,
            subject_type="agent",
            description=description,
            properties=props,
        )
    except Exception as e:
        logger.debug("Activity-Logging fehlgeschlagen: %s", e)

    try:
        from app.domain.webhooks.dispatcher import dispatch_webhook_event
        dispatch_webhook_event(
            event=event,
            actor_id=actor_id,
            actor_type="admin",
            subject_id=agent.id,
            subject_type="agent",
            description=description,
            properties={"agent_name": agent.name, "reason": reason},
        )
    except Exception as e:
        logger.debug("Webhook-Dispatch fehlgeschlagen: %s", e)
