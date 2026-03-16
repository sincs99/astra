"""Job-Handler-Registry (M23).

Zentraler Katalog fuer alle verfuegbaren Job-Typen.
Handler registrieren sich mit einem Namen und einer Callable.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)

# Type: handler(payload: dict) -> str | None (result message)
JobHandler = Callable[[dict], str | None]

_handlers: dict[str, JobHandler] = {}


# ── Bekannte Job-Typen ──────────────────────────────────

JOB_TYPE_WEBHOOK_DISPATCH = "webhook_dispatch"
JOB_TYPE_ROUTINE_EXECUTE = "routine_execute"
JOB_TYPE_ROUTINE_ACTION = "routine_action"
JOB_TYPE_AGENT_HEALTH_CHECK = "agent_health_check"
JOB_TYPE_INSTANCE_SYNC = "instance_sync"

ALL_JOB_TYPES = [
    JOB_TYPE_WEBHOOK_DISPATCH,
    JOB_TYPE_ROUTINE_EXECUTE,
    JOB_TYPE_ROUTINE_ACTION,
    JOB_TYPE_AGENT_HEALTH_CHECK,
    JOB_TYPE_INSTANCE_SYNC,
]


def register_handler(job_type: str, handler: JobHandler) -> None:
    """Registriert einen Handler fuer einen Job-Typ."""
    _handlers[job_type] = handler
    logger.debug("Job-Handler registriert: %s", job_type)


def get_handler(job_type: str) -> JobHandler | None:
    """Gibt den Handler fuer einen Job-Typ zurueck."""
    return _handlers.get(job_type)


def list_registered_types() -> list[str]:
    """Gibt alle registrierten Job-Typen zurueck."""
    return list(_handlers.keys())
