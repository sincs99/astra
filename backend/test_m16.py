"""Schnelltests fuer Meilenstein 16 - Install-/Reinstall-/Sync-Haertung."""

import sys
import os

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

# IDs fuer Wiederverwendung
_user_id = None
_agent_id = None
_bp_id = None
_ep_id = None
_inst_id = None
_inst_uuid = None


# ================================================================
# Setup: Grunddaten anlegen
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

    set_runner(StubRunnerAdapter())

    user = User(username="m16-user", email="m16@test.dev", password_hash="x")
    db.session.add(user)
    db.session.flush()

    agent = Agent(name="m16-agent", fqdn="m16.test.dev", scheme="https",
                  daemon_connect=8080, daemon_token="m16-token")
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m16-bp", docker_image="test:latest")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565)
    db.session.add(ep)
    db.session.flush()

    _user_id = user.id
    _agent_id = agent.id
    _bp_id = bp.id
    _ep_id = ep.id

    # Instance direkt anlegen (ohne create_instance, um Setup simpel zu halten)
    inst = Instance(
        name="m16-test-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status="provisioning",
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    _inst_id = inst.id
    _inst_uuid = inst.uuid


# ================================================================
# Test 1: Modell - installed_at Feld
# ================================================================
print("\n== Modell - installed_at Feld ==")

with app.app_context():
    from app.domain.instances.models import Instance

    inst = db.session.get(Instance, _inst_id)
    check("installed_at Attribut existiert", hasattr(inst, "installed_at"))
    check("installed_at initial None", inst.installed_at is None)

    d = inst.to_dict()
    check("to_dict hat installed_at", "installed_at" in d)
    check("to_dict installed_at ist None", d["installed_at"] is None)


# ================================================================
# Test 2: Lifecycle-Konstanten
# ================================================================
print("\n== Lifecycle-Konstanten ==")

with app.app_context():
    from app.domain.instances.service import (
        STATUS_PROVISIONING,
        STATUS_PROVISION_FAILED,
        STATUS_REINSTALLING,
        STATUS_REINSTALL_FAILED,
        STATUS_RESTORING,
        STATUS_SUSPENDED,
        STATUS_READY,
        VALID_CONTAINER_STATES,
        VALID_LIFECYCLE_STATUSES,
        SYNCABLE_FIELDS,
    )

    check("STATUS_PROVISIONING", STATUS_PROVISIONING == "provisioning")
    check("STATUS_PROVISION_FAILED", STATUS_PROVISION_FAILED == "provision_failed")
    check("STATUS_REINSTALLING", STATUS_REINSTALLING == "reinstalling")
    check("STATUS_REINSTALL_FAILED", STATUS_REINSTALL_FAILED == "reinstall_failed")
    check("STATUS_RESTORING", STATUS_RESTORING == "restoring")
    check("STATUS_SUSPENDED", STATUS_SUSPENDED == "suspended")
    check("STATUS_READY ist None", STATUS_READY is None)
    check("VALID_CONTAINER_STATES ist set", isinstance(VALID_CONTAINER_STATES, set))
    check("VALID_LIFECYCLE_STATUSES ist set", isinstance(VALID_LIFECYCLE_STATUSES, set))
    check("SYNCABLE_FIELDS hat memory", "memory" in SYNCABLE_FIELDS)
    check("SYNCABLE_FIELDS hat image", "image" in SYNCABLE_FIELDS)
    check("SYNCABLE_FIELDS hat startup_command", "startup_command" in SYNCABLE_FIELDS)


# ================================================================
# Test 3: Install-Callback - Erstinstallation erfolgreich
# ================================================================
print("\n== Install-Callback - Erstinstallation ==")

with app.app_context():
    from app.domain.instances.service import handle_install_callback, STATUS_PROVISIONING
    from app.domain.instances.models import Instance

    inst = db.session.get(Instance, _inst_id)

    # Erstinstallation erfolgreich
    inst.status = STATUS_PROVISIONING
    inst.installed_at = None
    db.session.commit()

    result = handle_install_callback(inst, True)
    check("Erstinstall ok: status = None (ready)", result.status is None)
    check("Erstinstall ok: installed_at gesetzt", result.installed_at is not None)

    installed_ts = result.installed_at

    # Erstinstallation fehlgeschlagen
    inst.status = STATUS_PROVISIONING
    inst.installed_at = None
    db.session.commit()

    result = handle_install_callback(inst, False)
    check("Erstinstall fail: status = provision_failed", result.status == "provision_failed")
    check("Erstinstall fail: installed_at bleibt None", result.installed_at is None)


# ================================================================
# Test 4: Install-Callback - Reinstall
# ================================================================
print("\n== Install-Callback - Reinstall ==")

with app.app_context():
    from app.domain.instances.service import (
        handle_install_callback, STATUS_REINSTALLING, STATUS_REINSTALL_FAILED
    )
    from app.domain.instances.models import Instance
    from datetime import datetime, timezone

    inst = db.session.get(Instance, _inst_id)

    # Reinstall erfolgreich
    inst.status = STATUS_REINSTALLING
    inst.installed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    db.session.commit()

    old_installed_at = inst.installed_at
    result = handle_install_callback(inst, True)
    check("Reinstall ok: status = None (ready)", result.status is None)
    check("Reinstall ok: installed_at bleibt erhalten", result.installed_at == old_installed_at)

    # Reinstall fehlgeschlagen
    inst.status = STATUS_REINSTALLING
    db.session.commit()

    result = handle_install_callback(inst, False)
    check("Reinstall fail: status = reinstall_failed", result.status == STATUS_REINSTALL_FAILED)


# ================================================================
# Test 5: Install-Callback - Idempotenz
# ================================================================
print("\n== Install-Callback - Idempotenz ==")

with app.app_context():
    from app.domain.instances.service import handle_install_callback
    from app.domain.instances.models import Instance
    from datetime import datetime, timezone

    inst = db.session.get(Instance, _inst_id)

    # Bereits ready → nochmal Erfolg
    inst.status = None
    inst.installed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    db.session.commit()

    result = handle_install_callback(inst, True)
    check("Idempotent: status bleibt None", result.status is None)
    check("Idempotent: installed_at unveraendert", result.installed_at is not None)

    # Doppelter Erfolg bei provisioning
    inst.status = "provisioning"
    inst.installed_at = None
    db.session.commit()

    handle_install_callback(inst, True)
    result = handle_install_callback(inst, True)
    check("Doppelt ok: status None", result.status is None)
    check("Doppelt ok: installed_at gesetzt", result.installed_at is not None)

    # Doppelter Fehler bei provisioning
    inst.status = "provisioning"
    inst.installed_at = None
    db.session.commit()

    handle_install_callback(inst, False)
    # Jetzt ist status = provision_failed, nochmal fail
    result = handle_install_callback(inst, False)
    check("Doppelt fail: status stabil", result.status == "provision_failed")

    # Unerwarteter Status → Fehler wird ignoriert
    inst.status = "suspended"
    db.session.commit()
    result = handle_install_callback(inst, False)
    check("Unerwarteter Status: bleibt suspended", result.status == "suspended")


# ================================================================
# Test 6: Reinstall-Service
# ================================================================
print("\n== Reinstall-Service ==")

with app.app_context():
    from app.domain.instances.service import (
        reinstall_instance, set_runner, InstanceActionError,
        STATUS_REINSTALLING, STATUS_REINSTALL_FAILED,
    )
    from app.domain.instances.models import Instance
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    inst = db.session.get(Instance, _inst_id)

    # Normaler Reinstall
    inst.status = None
    db.session.commit()

    result = reinstall_instance(inst)
    check("Reinstall: status = reinstalling", result.status == STATUS_REINSTALLING)

    # Doppelter Reinstall → 409
    inst.status = STATUS_REINSTALLING
    db.session.commit()

    try:
        reinstall_instance(inst)
        fail("Doppelter Reinstall: sollte InstanceActionError werfen")
    except InstanceActionError as e:
        check("Doppelter Reinstall: 409", e.status_code == 409)

    # Reinstall mit provision_failed vorher
    inst.status = "provision_failed"
    db.session.commit()
    result = reinstall_instance(inst)
    check("Reinstall nach provision_failed: reinstalling", result.status == STATUS_REINSTALLING)

    # Reinstall von stopped
    inst.status = "stopped"
    db.session.commit()
    result = reinstall_instance(inst)
    check("Reinstall von stopped: reinstalling", result.status == STATUS_REINSTALLING)


# ================================================================
# Test 7: Sync-Service
# ================================================================
print("\n== Sync-Service ==")

with app.app_context():
    from app.domain.instances.service import sync_instance, set_runner
    from app.domain.instances.models import Instance
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    inst = db.session.get(Instance, _inst_id)
    inst.status = None
    db.session.commit()

    result = sync_instance(inst)
    check("Sync: success = True", result.get("success") is True)
    check("Sync: hat message", "message" in result)


# ================================================================
# Test 8: Config-Update mit Auto-Sync
# ================================================================
print("\n== Config-Update mit Auto-Sync ==")

with app.app_context():
    from app.domain.instances.service import update_instance_config, set_runner
    from app.domain.instances.models import Instance
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    inst.memory = 512
    inst.name = "m16-test-instance"
    db.session.commit()

    # Sync-relevante Aenderung
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    result = update_instance_config(inst, memory=1024)
    check("Config: memory geaendert", result["instance"].memory == 1024)
    check("Config: synced = True", result["synced"] is True)
    check("Config: changed_fields hat memory", "memory" in result["changed_fields"])

    # Nicht-syncbare Aenderung (name)
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    result = update_instance_config(inst, name="neuer-name")
    check("Config name: synced = False", result["synced"] is False)
    check("Config name: Name geaendert", result["instance"].name == "neuer-name")

    # Mehrere Felder
    result = update_instance_config(inst, cpu=200, disk=2048, description="neu")
    check("Config multi: cpu geaendert", result["instance"].cpu == 200)
    check("Config multi: disk geaendert", result["instance"].disk == 2048)
    check("Config multi: synced", result["synced"] is True)
    check("Config multi: changed hat cpu", "cpu" in result["changed_fields"])
    check("Config multi: changed hat disk", "disk" in result["changed_fields"])

    # Gleicher Wert → kein Sync
    result = update_instance_config(inst, cpu=200)
    check("Config gleicher Wert: synced = False", result["synced"] is False)

    # Unbekanntes Feld wird ignoriert
    result = update_instance_config(inst, nonexistent_field=True)
    check("Config unbekannt: synced = False", result["synced"] is False)

    # Name zuruecksetzen
    inst.name = "m16-test-instance"
    db.session.commit()


# ================================================================
# Test 9: Activity-Events
# ================================================================
print("\n== Activity-Events ==")

with app.app_context():
    from app.domain.activity.events import (
        INSTANCE_INSTALL_COMPLETED,
        INSTANCE_INSTALL_FAILED,
        INSTANCE_REINSTALL_STARTED,
        INSTANCE_REINSTALL_COMPLETED,
        INSTANCE_REINSTALL_FAILED,
        INSTANCE_SYNCED,
        INSTANCE_SYNC_FAILED,
    )
    from app.domain.activity.models import ActivityLog

    check("INSTALL_COMPLETED definiert", INSTANCE_INSTALL_COMPLETED == "instance:install_completed")
    check("INSTALL_FAILED definiert", INSTANCE_INSTALL_FAILED == "instance:install_failed")
    check("REINSTALL_STARTED definiert", INSTANCE_REINSTALL_STARTED == "instance:reinstall_started")
    check("REINSTALL_COMPLETED definiert", INSTANCE_REINSTALL_COMPLETED == "instance:reinstall_completed")
    check("REINSTALL_FAILED definiert", INSTANCE_REINSTALL_FAILED == "instance:reinstall_failed")
    check("SYNCED definiert", INSTANCE_SYNCED == "instance:synced")
    check("SYNC_FAILED definiert", INSTANCE_SYNC_FAILED == "instance:sync_failed")

    # Activity-Logs aus vorherigen Tests pruefen
    install_ok_logs = ActivityLog.query.filter_by(
        event=INSTANCE_INSTALL_COMPLETED, subject_id=_inst_id
    ).count()
    check("Activity: mindestens 1 install_completed Log", install_ok_logs >= 1)

    reinstall_started_logs = ActivityLog.query.filter_by(
        event=INSTANCE_REINSTALL_STARTED, subject_id=_inst_id
    ).count()
    check("Activity: mindestens 1 reinstall_started Log", reinstall_started_logs >= 1)

    sync_logs = ActivityLog.query.filter_by(
        event=INSTANCE_SYNCED, subject_id=_inst_id
    ).count()
    check("Activity: mindestens 1 synced Log", sync_logs >= 1)


# ================================================================
# Test 10: Webhook-Event-Katalog
# ================================================================
print("\n== Webhook-Event-Katalog ==")

with app.app_context():
    from app.domain.webhooks.event_catalog import (
        is_valid_webhook_event,
        validate_webhook_events,
        get_event_catalog,
        WEBHOOK_EVENTS,
    )
    from app.domain.activity.events import (
        INSTANCE_INSTALL_COMPLETED,
        INSTANCE_INSTALL_FAILED,
        INSTANCE_REINSTALL_STARTED,
        INSTANCE_REINSTALL_COMPLETED,
        INSTANCE_REINSTALL_FAILED,
        INSTANCE_SYNCED,
        INSTANCE_SYNC_FAILED,
    )

    new_events = [
        INSTANCE_INSTALL_COMPLETED,
        INSTANCE_INSTALL_FAILED,
        INSTANCE_REINSTALL_STARTED,
        INSTANCE_REINSTALL_COMPLETED,
        INSTANCE_REINSTALL_FAILED,
        INSTANCE_SYNCED,
        INSTANCE_SYNC_FAILED,
    ]

    for ev in new_events:
        check(f"Event '{ev}' im Katalog", ev in WEBHOOK_EVENTS)
        check(f"Event '{ev}' ist valid", is_valid_webhook_event(ev))

    ok_result, invalid = validate_webhook_events(new_events)
    check("Alle neuen Events valide", ok_result)

    catalog = get_event_catalog()
    check("Katalog hat >= 20 Events", len(catalog) >= 20)


# ================================================================
# Test 11: Agent-Route Install-Callback (gehaertet)
# ================================================================
print("\n== Agent-Route Install-Callback ==")

with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    client = app.test_client()

    inst = db.session.get(Instance, _inst_id)

    # Erstinstallation via Route
    inst.status = "provisioning"
    inst.installed_at = None
    db.session.commit()

    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/install",
        json={"successful": True},
    )
    check("Install ok -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Install ok: status None", data.get("status") is None)

    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    check("Install ok: installed_at gesetzt", inst.installed_at is not None)

    # Reinstall via Route
    inst.status = "reinstalling"
    db.session.commit()

    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/install",
        json={"successful": True},
    )
    check("Reinstall ok -> 200", resp.status_code == 200)
    check("Reinstall ok: status None", resp.get_json().get("status") is None)

    # Reinstall fail via Route
    inst.status = "reinstalling"
    db.session.commit()

    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/install",
        json={"successful": False},
    )
    check("Reinstall fail -> 200", resp.status_code == 200)
    check("Reinstall fail: reinstall_failed", resp.get_json().get("status") == "reinstall_failed")

    # Unbekannte Instance
    resp = client.post(
        "/api/agent/instances/non-existent/install",
        json={"successful": True},
    )
    check("Unbekannte Instance -> 404", resp.status_code == 404)

    # Fehlender Body
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/install",
        content_type="application/json",
    )
    check("Fehlender Body -> 400", resp.status_code == 400)

    # Fehlendes Feld
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/install",
        json={"wrong": True},
    )
    check("Fehlendes Feld -> 400", resp.status_code == 400)


# ================================================================
# Test 12: Client-Route Reinstall
# ================================================================
print("\n== Client-Route Reinstall ==")

with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    client = app.test_client()
    headers = {"X-User-Id": str(_user_id)}

    inst = db.session.get(Instance, _inst_id)
    inst.status = None
    inst.owner_id = _user_id
    db.session.commit()

    # Reinstall ausloesen
    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/reinstall",
        headers=headers,
    )
    check("Reinstall -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Reinstall: status reinstalling", data.get("status") == "reinstalling")
    check("Reinstall: hat message", "message" in data)

    # Doppelter Reinstall → 409
    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/reinstall",
        headers=headers,
    )
    check("Doppelter Reinstall -> 409", resp.status_code == 409)

    # Ohne Auth → 401
    resp = client.post(f"/api/client/instances/{_inst_uuid}/reinstall")
    check("Reinstall ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 13: Client-Route Config-Update (PATCH /build)
# ================================================================
print("\n== Client-Route Config-Update ==")

with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    client = app.test_client()
    headers = {"X-User-Id": str(_user_id)}

    inst = db.session.get(Instance, _inst_id)
    inst.status = None
    inst.memory = 512
    db.session.commit()

    # Memory aendern
    resp = client.patch(
        f"/api/client/instances/{_inst_uuid}/build",
        json={"memory": 1024},
        headers=headers,
    )
    check("Build PATCH -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Build: memory = 1024", data["instance"]["memory"] == 1024)
    check("Build: synced", data["synced"] is True)
    check("Build: changed_fields hat memory", "memory" in data["changed_fields"])

    # Leerer Body → 400
    resp = client.patch(
        f"/api/client/instances/{_inst_uuid}/build",
        content_type="application/json",
        headers=headers,
    )
    check("Build ohne Body -> 400", resp.status_code == 400)

    # Ungueltiges Feld → 400
    resp = client.patch(
        f"/api/client/instances/{_inst_uuid}/build",
        json={"hacked_field": "evil"},
        headers=headers,
    )
    check("Build ungueltiges Feld -> 400", resp.status_code == 400)

    # Ohne Auth → 401
    resp = client.patch(
        f"/api/client/instances/{_inst_uuid}/build",
        json={"memory": 2048},
    )
    check("Build ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 14: Client-Route Sync
# ================================================================
print("\n== Client-Route Sync ==")

with app.app_context():
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())
    client = app.test_client()
    headers = {"X-User-Id": str(_user_id)}

    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/sync",
        headers=headers,
    )
    check("Sync -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Sync: success = True", data.get("success") is True)

    # Ohne Auth
    resp = client.post(f"/api/client/instances/{_inst_uuid}/sync")
    check("Sync ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 15: Regression – bestehende Flows
# ================================================================
print("\n== Regression - bestehende Flows ==")

with app.app_context():
    from app.domain.instances.service import (
        send_power_action,
        update_container_status,
        set_runner,
        get_runner,
        VALID_CONTAINER_STATES,
    )
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol
    from app.domain.instances.models import Instance

    set_runner(StubRunnerAdapter())
    inst = db.session.get(Instance, _inst_id)
    inst.status = "stopped"
    db.session.commit()

    # Power-Action
    try:
        res = send_power_action(inst, "start")
        check("Power-Action OK", res.get("action") == "start")
    except Exception as e:
        fail("Power-Action", str(e))

    # Container-Status Update (M15)
    inst.container_state = None
    db.session.commit()
    result = update_container_status(inst, "running")
    check("Container-State Update OK", result.container_state == "running")

    # VALID_CONTAINER_STATES vorhanden
    check("VALID_CONTAINER_STATES hat running", "running" in VALID_CONTAINER_STATES)

    # Health
    client = app.test_client()
    resp = client.get("/api/agent/health")
    check("Agent Health -> 200", resp.status_code == 200)

    resp = client.get("/api/client/health")
    check("Client Health -> 200", resp.status_code == 200)

    # Runner
    runner = get_runner()
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M16 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
