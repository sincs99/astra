"""Schnelltests fuer Meilenstein 23 - Queue & Background Jobs."""

import sys
import os
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  OK {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {label} - {detail}")


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


app = create_app("testing")

_user_id = None
_agent_id = None
_bp_id = None
_inst_id = None
_inst_uuid = None
_routine_id = None


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.domain.routines.models import Routine, Action

    set_runner(StubRunnerAdapter())

    user = User(username="m23-user", email="m23@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    bp = Blueprint(name="m23-bp")
    db.session.add(bp)
    db.session.flush()
    _bp_id = bp.id

    agent = Agent(name="m23-agent", fqdn="m23.test.dev")
    agent.touch()
    db.session.add(agent)
    db.session.flush()
    _agent_id = agent.id

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25900)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m23-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        memory=512, disk=1024, cpu=100,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid

    # Routine mit 2 Actions
    routine = Routine(
        instance_id=inst.id,
        name="m23-test-routine",
    )
    db.session.add(routine)
    db.session.flush()
    _routine_id = routine.id

    a1 = Action(
        routine_id=routine.id,
        sequence=1,
        action_type="send_command",
        payload={"command": "say Hello"},
        delay_seconds=0,
    )
    a2 = Action(
        routine_id=routine.id,
        sequence=2,
        action_type="power_action",
        payload={"signal": "restart"},
        delay_seconds=0,
    )
    db.session.add_all([a1, a2])
    db.session.commit()


# ================================================================
# Test 1: Job-Abstraktion
# ================================================================
print("\n== Job-Abstraktion ==")

with app.app_context():
    from app.infrastructure.jobs.models import JobRecord, JobStatus
    from app.infrastructure.jobs.queue import enqueue_job, get_queue, SyncQueue

    # Queue ist SyncQueue (Test-Default)
    queue = get_queue()
    check("Queue ist SyncQueue in Tests", isinstance(queue, SyncQueue), f"got {type(queue).__name__}")

    # Job erstellen und enqueuen
    job = enqueue_job(
        job_type="agent_health_check",
        payload={"agent_id": _agent_id},
        max_attempts=3,
    )
    check("Job erstellt", job is not None)
    check("Job hat UUID", job.uuid is not None)
    check("Job hat job_type", job.job_type == "agent_health_check")

    # SyncQueue fuehrt sofort aus -> Job sollte completed sein
    db.session.refresh(job)
    check("Job Status nach Sync-Ausfuehrung = completed",
          job.status == JobStatus.COMPLETED,
          f"got {job.status}")
    check("Job attempts = 1", job.attempts == 1, f"got {job.attempts}")
    check("Job hat started_at", job.started_at is not None)
    check("Job hat finished_at", job.finished_at is not None)
    check("Job hat result", job.result is not None)


# ================================================================
# Test 2: Job-Statusuebergaenge
# ================================================================
print("\n== Job-Statusuebergaenge ==")

with app.app_context():
    job = JobRecord(
        job_type="test_status",
        status=JobStatus.PENDING,
        max_attempts=3,
    )
    db.session.add(job)
    db.session.commit()

    check("Initialer Status = pending", job.status == JobStatus.PENDING)
    check("can_retry = True (0 < 3)", job.can_retry is True)

    job.mark_running()
    check("Nach mark_running: status = running", job.status == JobStatus.RUNNING)
    check("Nach mark_running: attempts = 1", job.attempts == 1)
    check("Nach mark_running: started_at gesetzt", job.started_at is not None)

    job.mark_retrying("Testfehler")
    check("Nach mark_retrying: status = retrying", job.status == JobStatus.RETRYING)
    check("Nach mark_retrying: error gesetzt", job.error == "Testfehler")
    check("can_retry = True (1 < 3)", job.can_retry is True)

    job.mark_running()
    job.mark_completed("Erfolg")
    check("Nach mark_completed: status = completed", job.status == JobStatus.COMPLETED)
    check("Nach mark_completed: result = Erfolg", job.result == "Erfolg")
    check("Nach mark_completed: finished_at gesetzt", job.finished_at is not None)

    # Neuer Job fuer failed-Test
    job2 = JobRecord(job_type="test_fail", max_attempts=1)
    job2.mark_running()
    job2.mark_failed("Endgueltig fehlgeschlagen")
    check("mark_failed: status = failed", job2.status == JobStatus.FAILED)
    check("mark_failed: error gesetzt", "fehlgeschlagen" in job2.error)

    db.session.rollback()


# ================================================================
# Test 3: Job mit fehlerhaftem Handler
# ================================================================
print("\n== Fehlerbehandlung ==")

with app.app_context():
    from app.infrastructure.jobs.registry import register_handler

    # Fehlerhaften Handler registrieren
    def failing_handler(payload):
        raise RuntimeError("Absichtlicher Testfehler")

    register_handler("test_failing", failing_handler)

    job = enqueue_job(
        job_type="test_failing",
        payload={},
        max_attempts=2,
    )
    db.session.refresh(job)

    # Nach 2 Versuchen sollte der Job failed sein
    check("Fehlerhafter Job status = failed",
          job.status == JobStatus.FAILED,
          f"got {job.status}")
    check("Fehlerhafter Job attempts = 2",
          job.attempts == 2,
          f"got {job.attempts}")
    check("Fehlerhafter Job hat error",
          job.error is not None and "Testfehler" in job.error,
          f"got {job.error}")


# ================================================================
# Test 4: Unbekannter Job-Typ
# ================================================================
print("\n== Unbekannter Job-Typ ==")

with app.app_context():
    job = enqueue_job(
        job_type="nonexistent_type",
        payload={},
        max_attempts=1,
    )
    db.session.refresh(job)

    check("Unbekannter Typ -> failed",
          job.status == JobStatus.FAILED,
          f"got {job.status}")
    check("Error enthaelt 'Kein Handler'",
          job.error is not None and "Kein Handler" in job.error,
          f"got {job.error}")


# ================================================================
# Test 5: Routine ueber Job-Queue ausfuehren
# ================================================================
print("\n== Routine-Jobs ==")

with app.app_context():
    from app.domain.routines.service import execute_routine
    from app.domain.routines.models import Routine

    routine = db.session.get(Routine, _routine_id)
    check("Routine existiert", routine is not None)

    result = execute_routine(routine)
    check("execute_routine liefert dict", isinstance(result, dict))
    check("result hat routine Name", result["routine"] == "m23-test-routine")
    check("result hat actions_executed", result["actions_executed"] == 2)
    check("result hat job_uuid", "job_uuid" in result, f"keys: {list(result.keys())}")

    # Routine-Execute-Job und Action-Jobs pruefen
    from app.infrastructure.jobs.models import JobRecord
    routine_jobs = JobRecord.query.filter_by(job_type="routine_execute").all()
    check("mindestens 1 routine_execute Job", len(routine_jobs) >= 1)

    action_jobs = JobRecord.query.filter_by(job_type="routine_action").all()
    check("mindestens 2 routine_action Jobs", len(action_jobs) >= 2,
          f"got {len(action_jobs)}")

    # Actions sollten completed sein (SyncQueue)
    completed_actions = [j for j in action_jobs if j.status == JobStatus.COMPLETED]
    check("Action-Jobs sind completed",
          len(completed_actions) >= 2,
          f"got {len(completed_actions)} completed von {len(action_jobs)}")


# ================================================================
# Test 6: Webhook ueber Job-Queue
# ================================================================
print("\n== Webhook-Jobs ==")

with app.app_context():
    from app.domain.webhooks.models import Webhook
    from app.domain.webhooks.dispatcher import dispatch_webhook_event

    # Webhook erstellen (wird fehlschlagen da kein Server, aber Job wird erstellt)
    wh = Webhook(
        endpoint_url="http://localhost:19999/webhook-test",
        events=["instance:created"],
        is_active=True,
    )
    db.session.add(wh)
    db.session.commit()

    # Event dispatchen
    dispatch_webhook_event(
        event="instance:created",
        actor_id=_user_id,
        subject_id=_inst_id,
        subject_type="instance",
    )

    # Webhook-Job sollte erstellt worden sein
    webhook_jobs = JobRecord.query.filter_by(job_type="webhook_dispatch").all()
    check("mindestens 1 webhook_dispatch Job", len(webhook_jobs) >= 1,
          f"got {len(webhook_jobs)}")

    if webhook_jobs:
        wj = webhook_jobs[-1]
        check("Webhook-Job hat payload_summary mit event",
              wj.payload_summary is not None and "event" in wj.payload_summary)
        # Job wird failed sein (kein Server auf Port 19999)
        check("Webhook-Job verarbeitet (completed oder failed)",
              wj.status in (JobStatus.COMPLETED, JobStatus.FAILED),
              f"got {wj.status}")


# ================================================================
# Test 7: Job-Tracking Modell
# ================================================================
print("\n== Job-Tracking Modell ==")

with app.app_context():
    job = JobRecord(
        job_type="test_tracking",
        payload_summary={"key": "value"},
        max_attempts=5,
    )
    db.session.add(job)
    db.session.commit()

    d = job.to_dict()
    check("to_dict hat id", "id" in d)
    check("to_dict hat uuid", "uuid" in d)
    check("to_dict hat job_type", d["job_type"] == "test_tracking")
    check("to_dict hat status", d["status"] == "pending")
    check("to_dict hat attempts", d["attempts"] == 0)
    check("to_dict hat max_attempts", d["max_attempts"] == 5)
    check("to_dict hat payload_summary", d["payload_summary"] == {"key": "value"})
    check("to_dict hat created_at", d["created_at"] is not None)


# ================================================================
# Test 8: Admin-Job-API
# ================================================================
print("\n== Admin-Job-API ==")

client = app.test_client()

with app.app_context():
    resp = client.get("/api/admin/jobs")
    check("GET /admin/jobs -> 200", resp.status_code == 200, f"got {resp.status_code}")
    data = resp.get_json()
    check("jobs response hat items", "items" in data)
    check("jobs response hat total", "total" in data)
    check("jobs response hat page", "page" in data)
    check("jobs items ist Liste", isinstance(data["items"], list))
    check("jobs hat mindestens 1 Eintrag", len(data["items"]) >= 1)

    # Einzelner Job
    if data["items"]:
        job_id = data["items"][0]["id"]
        resp = client.get(f"/api/admin/jobs/{job_id}")
        check(f"GET /admin/jobs/{job_id} -> 200", resp.status_code == 200)
        job_data = resp.get_json()
        check("Einzelner Job hat uuid", "uuid" in job_data)

    # Nicht existierender Job
    resp = client.get("/api/admin/jobs/99999")
    check("GET /admin/jobs/99999 -> 404", resp.status_code == 404)

    # Filter: status=completed
    resp = client.get("/api/admin/jobs?status=completed")
    check("GET ?status=completed -> 200", resp.status_code == 200)
    data = resp.get_json()
    if data["items"]:
        check("Alle gefilterten Jobs = completed",
              all(j["status"] == "completed" for j in data["items"]))

    # Filter: type
    resp = client.get("/api/admin/jobs?type=routine_action")
    check("GET ?type=routine_action -> 200", resp.status_code == 200)
    data = resp.get_json()
    if data["items"]:
        check("Alle gefilterten Jobs = routine_action",
              all(j["job_type"] == "routine_action" for j in data["items"]))

    # Summary
    resp = client.get("/api/admin/jobs/summary")
    check("GET /admin/jobs/summary -> 200", resp.status_code == 200)
    summary = resp.get_json()
    check("Summary hat total", "total" in summary)
    check("Summary hat by_status", "by_status" in summary)
    check("Summary hat by_type", "by_type" in summary)
    check("Summary total > 0", summary["total"] > 0, f"got {summary['total']}")


# ================================================================
# Test 9: Dev/Test-Fallback
# ================================================================
print("\n== Dev/Test-Fallback ==")

with app.app_context():
    from app.infrastructure.jobs.queue import SyncQueue, get_queue, set_queue

    # Sicherstellen, dass SyncQueue aktiv ist
    queue = get_queue()
    check("Queue in Tests = SyncQueue", isinstance(queue, SyncQueue))

    # Job wird sofort ausgefuehrt
    job = enqueue_job(
        job_type="agent_health_check",
        payload={},
        max_attempts=1,
    )
    db.session.refresh(job)
    check("SyncQueue: Job sofort completed",
          job.status == JobStatus.COMPLETED,
          f"got {job.status}")


# ================================================================
# Test 10: Bestehende Endpunkte nicht gebrochen
# ================================================================
print("\n== Regression ==")

with app.app_context():
    # Bestehende Admin-Endpunkte
    resp = client.get("/api/admin/agents")
    check("GET /admin/agents -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/instances")
    check("GET /admin/instances -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/webhooks")
    check("GET /admin/webhooks -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health")
    check("GET /admin/health -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health/detailed")
    check("GET /admin/health/detailed -> 200", resp.status_code == 200)

    # Fleet Monitoring (M22)
    resp = client.get("/api/admin/agents/monitoring")
    check("GET /admin/agents/monitoring -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/fleet/summary")
    check("GET /admin/fleet/summary -> 200", resp.status_code == 200)

    # Client-Endpunkt
    resp = client.get("/health")
    check("GET /health -> 200", resp.status_code == 200)


# ================================================================
# Test 11: Payload-Summary sicher (keine Secrets)
# ================================================================
print("\n== Payload-Safety ==")

with app.app_context():
    from app.infrastructure.jobs.queue import _safe_summary

    payload = {
        "event": "test:event",
        "webhook_id": 42,
        "secret_token": "SUPER_SECRET",
        "password": "geheim",
        "routine_id": 7,
    }
    summary = _safe_summary("webhook_dispatch", payload)

    check("Summary enthaelt event", summary.get("event") == "test:event")
    check("Summary enthaelt webhook_id", summary.get("webhook_id") == 42)
    check("Summary enthaelt routine_id", summary.get("routine_id") == 7)
    check("Summary enthaelt NICHT secret_token", "secret_token" not in summary)
    check("Summary enthaelt NICHT password", "password" not in summary)


# ================================================================
# Test 12: Job-Registry
# ================================================================
print("\n== Job-Registry ==")

with app.app_context():
    from app.infrastructure.jobs.registry import (
        get_handler, list_registered_types,
        JOB_TYPE_WEBHOOK_DISPATCH,
        JOB_TYPE_ROUTINE_EXECUTE,
        JOB_TYPE_ROUTINE_ACTION,
    )

    types = list_registered_types()
    check("webhook_dispatch registriert", JOB_TYPE_WEBHOOK_DISPATCH in types)
    check("routine_execute registriert", JOB_TYPE_ROUTINE_EXECUTE in types)
    check("routine_action registriert", JOB_TYPE_ROUTINE_ACTION in types)

    handler = get_handler(JOB_TYPE_WEBHOOK_DISPATCH)
    check("webhook_dispatch handler nicht None", handler is not None)

    unknown = get_handler("completely_unknown")
    check("unknown handler = None", unknown is None)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*60}")
print(f"M23 Queue & Background Jobs: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
