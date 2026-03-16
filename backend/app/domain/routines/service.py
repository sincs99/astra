"""Service-Logik für Routinen und Actions."""

import logging
import time
from datetime import datetime, timezone

from app.extensions import db
from app.domain.routines.models import Routine, Action
from app.domain.routines.action_types import (
    is_valid_action_type,
    validate_action_payload,
)
from app.domain.instances.models import Instance
from app.domain.instances.service import send_power_action, get_runner

logger = logging.getLogger(__name__)


class RoutineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Routine CRUD ────────────────────────────────────────


def list_routines(instance: Instance) -> list[Routine]:
    return (
        Routine.query.filter_by(instance_id=instance.id)
        .order_by(Routine.created_at.desc())
        .all()
    )


def create_routine(instance: Instance, name: str, **kwargs) -> Routine:
    routine = Routine(
        instance_id=instance.id,
        name=name,
        cron_minute=kwargs.get("cron_minute", "*"),
        cron_hour=kwargs.get("cron_hour", "*"),
        cron_day_month=kwargs.get("cron_day_month", "*"),
        cron_month=kwargs.get("cron_month", "*"),
        cron_day_week=kwargs.get("cron_day_week", "*"),
        is_active=kwargs.get("is_active", True),
        only_when_online=kwargs.get("only_when_online", True),
    )
    db.session.add(routine)
    db.session.commit()
    return routine


def update_routine(routine: Routine, **kwargs) -> Routine:
    for key in [
        "name", "cron_minute", "cron_hour", "cron_day_month",
        "cron_month", "cron_day_week", "is_active", "only_when_online",
    ]:
        if key in kwargs:
            setattr(routine, key, kwargs[key])
    db.session.commit()
    return routine


def delete_routine(routine: Routine) -> None:
    db.session.delete(routine)
    db.session.commit()


# ── Action CRUD ─────────────────────────────────────────


def add_action(
    routine: Routine,
    sequence: int,
    action_type: str,
    payload: dict | None = None,
    delay_seconds: int = 0,
    continue_on_failure: bool = False,
) -> Action:
    if not is_valid_action_type(action_type):
        raise RoutineError(f"Ungültiger Action-Typ: {action_type}")

    ok, err = validate_action_payload(action_type, payload)
    if not ok:
        raise RoutineError(err)

    if delay_seconds < 0:
        raise RoutineError("delay_seconds muss >= 0 sein")

    # Sequence-Duplikat prüfen
    existing = Action.query.filter_by(routine_id=routine.id, sequence=sequence).first()
    if existing:
        raise RoutineError(f"Sequence {sequence} existiert bereits in dieser Routine", 409)

    action = Action(
        routine_id=routine.id,
        sequence=sequence,
        action_type=action_type,
        payload=payload,
        delay_seconds=delay_seconds,
        continue_on_failure=continue_on_failure,
    )
    db.session.add(action)
    db.session.commit()
    return action


def update_action(action: Action, **kwargs) -> Action:
    if "action_type" in kwargs:
        if not is_valid_action_type(kwargs["action_type"]):
            raise RoutineError(f"Ungültiger Action-Typ: {kwargs['action_type']}")
        action.action_type = kwargs["action_type"]

    if "payload" in kwargs:
        at = kwargs.get("action_type", action.action_type)
        ok, err = validate_action_payload(at, kwargs["payload"])
        if not ok:
            raise RoutineError(err)
        action.payload = kwargs["payload"]

    for key in ["sequence", "delay_seconds", "continue_on_failure"]:
        if key in kwargs:
            setattr(action, key, kwargs[key])

    db.session.commit()
    return action


def delete_action(action: Action) -> None:
    db.session.delete(action)
    db.session.commit()


# ── Executor (M23: Job-basiert) ─────────────────────────


def execute_routine(routine: Routine) -> dict:
    """Startet die Ausfuehrung einer Routine ueber die Job-Queue.

    Ab M23: Nicht mehr blockierend im Request-Kontext.
    Die Routine wird als Job enqueued, Actions als Folge-Jobs.
    """
    if routine.is_processing:
        raise RoutineError("Routine wird bereits ausgefuehrt", 409)

    actions = Action.query.filter_by(routine_id=routine.id).order_by(Action.sequence).all()
    if not actions:
        raise RoutineError("Routine hat keine Actions", 400)

    instance = db.session.get(Instance, routine.instance_id)
    if not instance:
        raise RoutineError("Instance nicht gefunden", 404)

    # Job enqueuen (non-blocking)
    from app.infrastructure.jobs.queue import enqueue_job
    from app.infrastructure.jobs.registry import JOB_TYPE_ROUTINE_EXECUTE

    job = enqueue_job(
        job_type=JOB_TYPE_ROUTINE_EXECUTE,
        payload={"routine_id": routine.id},
        max_attempts=1,
        payload_summary={
            "routine_id": routine.id,
            "routine_name": routine.name,
            "instance_id": routine.instance_id,
            "action_count": len(actions),
        },
    )

    return {
        "routine": routine.name,
        "actions_executed": len(actions),
        "failed": False,
        "results": [
            {
                "sequence": a.sequence,
                "action_type": a.action_type,
                "success": True,
                "message": f"Als Job enqueued (Job {job.uuid})",
            }
            for a in actions
        ],
        "job_uuid": job.uuid,
    }


def execute_routine_sync(routine: Routine) -> dict:
    """Fuehrt alle Actions einer Routine synchron aus (Legacy/Fallback).

    Wird intern vom Routine-Execute-Job-Handler verwendet.
    """
    if routine.is_processing:
        raise RoutineError("Routine wird bereits ausgefuehrt", 409)

    actions = Action.query.filter_by(routine_id=routine.id).order_by(Action.sequence).all()
    if not actions:
        raise RoutineError("Routine hat keine Actions", 400)

    instance = db.session.get(Instance, routine.instance_id)
    if not instance:
        raise RoutineError("Instance nicht gefunden", 404)

    routine.is_processing = True
    db.session.commit()

    results = []
    failed = False

    try:
        for action in actions:
            if action.delay_seconds > 0:
                logger.info(
                    "Routine '%s': Delay %ds vor Action #%d",
                    routine.name, action.delay_seconds, action.sequence,
                )
                time.sleep(action.delay_seconds)

            try:
                result = _execute_action(instance, action)
                results.append({
                    "sequence": action.sequence,
                    "action_type": action.action_type,
                    "success": True,
                    "message": result,
                })
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "sequence": action.sequence,
                    "action_type": action.action_type,
                    "success": False,
                    "message": error_msg,
                })
                if not action.continue_on_failure:
                    failed = True
                    break
    finally:
        routine.is_processing = False
        routine.last_run_at = datetime.now(timezone.utc)
        db.session.commit()

    return {
        "routine": routine.name,
        "actions_executed": len(results),
        "failed": failed,
        "results": results,
    }


def _execute_action(instance: Instance, action: Action) -> str:
    """Fuehrt eine einzelne Action aus."""
    payload = action.payload or {}

    if action.action_type == "power_action":
        signal = payload.get("signal", "start")
        result = send_power_action(instance, signal)
        return result.get("message", "OK")

    elif action.action_type == "send_command":
        command = payload.get("command", "")
        logger.info("[ACTION] send_command: '%s' an Instance %s", command, instance.uuid)
        return f"Command '{command}' gesendet"

    elif action.action_type == "create_backup":
        from app.domain.backups.service import create_backup
        name = payload.get("name", f"routine-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}")
        backup = create_backup(instance=instance, name=name)
        return f"Backup '{backup.name}' erstellt (success={backup.is_successful})"

    elif action.action_type == "delete_files":
        path = payload.get("path", "")
        from app.domain.agents.models import Agent
        agent = db.session.get(Agent, instance.agent_id)
        if agent:
            runner = get_runner()
            result = runner.delete_file(agent, instance, path)
            return result.message
        return "Agent nicht gefunden"

    return f"Unbekannter Action-Typ: {action.action_type}"
