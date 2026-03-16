"""Schnelltests fuer Meilenstein 15 - Status-Synchronisation & Resource-Monitoring."""

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

# IDs fuer Wiederverwendung zwischen Bloecken
_user_id = None
_agent_id = None
_bp_id = None
_ep_id = None
_inst_id = None
_inst_uuid = None


# ================================================================
# Test 1: Modell – container_state Feld existiert
# ================================================================
print("\n== Modell - container_state Feld ==")

with app.app_context():
    db.create_all()

    from app.domain.instances.models import Instance
    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint

    # Grunddaten anlegen
    user = User(username="m15-user", email="m15@test.dev", password_hash="x")
    db.session.add(user)
    db.session.flush()

    agent = Agent(
        name="m15-agent", fqdn="m15.test.dev",
        scheme="https", daemon_connect=8080,
        daemon_token="m15-test-token",
    )
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m15-bp", docker_image="test:latest")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565)
    db.session.add(ep)
    db.session.flush()

    # Instance erstellen
    inst = Instance(
        name="m15-test-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status="stopped",
    )
    db.session.add(inst)
    db.session.commit()

    # IDs merken
    _user_id = user.id
    _agent_id = agent.id
    _bp_id = bp.id
    _ep_id = ep.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid

    check("Instance hat container_state Attribut", hasattr(inst, "container_state"))
    check("container_state ist initial None", inst.container_state is None)

    # container_state setzen
    inst.container_state = "running"
    db.session.commit()

    reloaded = db.session.get(Instance, inst.id)
    check("container_state persistiert", reloaded.container_state == "running")

    # to_dict enthaelt container_state
    d = inst.to_dict()
    check("to_dict hat container_state", "container_state" in d)
    check("to_dict container_state Wert korrekt", d["container_state"] == "running")
    check("to_dict hat weiterhin status", "status" in d)
    check("status und container_state getrennt", d["status"] != d["container_state"])

    # Zuruecksetzen
    inst.container_state = None
    db.session.commit()


# ================================================================
# Test 2: Resource-Stats Parsing (_parse_wings_resources)
# ================================================================
print("\n== Resource-Stats Parsing ==")

with app.app_context():
    from app.infrastructure.runner.wings_adapter import _parse_wings_resources
    from app.infrastructure.runner.protocol import ResourceStats

    # Vollstaendige Wings-Response
    full_response = {
        "current_state": "running",
        "is_suspended": False,
        "resources": {
            "memory_bytes": 268435456,
            "memory_limit_bytes": 536870912,
            "cpu_absolute": 45.23,
            "disk_bytes": 100000000,
            "network_rx_bytes": 1234567,
            "network_tx_bytes": 7654321,
            "uptime": 3600,
        },
    }
    stats = _parse_wings_resources(full_response)
    check("ResourceStats Typ", isinstance(stats, ResourceStats))
    check("cpu_percent korrekt", stats.cpu_percent == 45.23)
    check("memory_bytes korrekt", stats.memory_bytes == 268435456)
    check("memory_limit_bytes korrekt", stats.memory_limit_bytes == 536870912)
    check("disk_bytes korrekt", stats.disk_bytes == 100000000)
    check("network_rx_bytes korrekt", stats.network_rx_bytes == 1234567)
    check("network_tx_bytes korrekt", stats.network_tx_bytes == 7654321)
    check("uptime_seconds korrekt", stats.uptime_seconds == 3600)
    check("container_status = running", stats.container_status == "running")

    # Fehlende Felder – defensiv handlen
    partial_response = {
        "current_state": "stopped",
        "resources": {
            "memory_bytes": 100000,
        },
    }
    stats2 = _parse_wings_resources(partial_response)
    check("Partial: cpu_percent default 0", stats2.cpu_percent == 0.0)
    check("Partial: memory_bytes vorhanden", stats2.memory_bytes == 100000)
    check("Partial: disk_bytes default 0", stats2.disk_bytes == 0)
    check("Partial: container_status = stopped", stats2.container_status == "stopped")

    # None-Input
    stats3 = _parse_wings_resources(None)
    check("None-Input: container_status = unknown", stats3.container_status == "unknown")

    # Leeres Dict
    stats4 = _parse_wings_resources({})
    check("Leeres Dict: container_status = unknown", stats4.container_status == "unknown")

    # Flache Response (ohne nested resources)
    flat_response = {
        "state": "starting",
        "cpu_absolute": 12.5,
        "memory_bytes": 50000,
        "memory_limit_bytes": 200000,
        "disk_bytes": 300000,
        "network_rx_bytes": 111,
        "network_tx_bytes": 222,
        "uptime": 60,
    }
    stats5 = _parse_wings_resources(flat_response)
    check("Flach: state als container_status", stats5.container_status == "starting")
    check("Flach: cpu_percent", stats5.cpu_percent == 12.5)
    check("Flach: memory_bytes", stats5.memory_bytes == 50000)

    # Ungueltige Typen in Feldern
    bad_types = {
        "current_state": "running",
        "resources": {
            "cpu_absolute": "not-a-number",
            "memory_bytes": None,
            "uptime": "abc",
        },
    }
    stats6 = _parse_wings_resources(bad_types)
    check("Bad types: cpu_percent default", stats6.cpu_percent == 0.0)
    check("Bad types: memory_bytes default", stats6.memory_bytes == 0)
    check("Bad types: uptime default", stats6.uptime_seconds == 0)
    check("Bad types: container_status OK", stats6.container_status == "running")


# ================================================================
# Test 3: StubRunnerAdapter – Kompatibilitaet
# ================================================================
print("\n== StubRunnerAdapter Kompatibilitaet ==")

with app.app_context():
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import ResourceStats
    from app.domain.instances.models import Instance
    from app.domain.agents.models import Agent

    agent = db.session.get(Agent, _agent_id)
    inst = db.session.get(Instance, _inst_id)

    stub = StubRunnerAdapter()
    stats = stub.get_instance_resources(agent, inst)

    check("Stub liefert ResourceStats", isinstance(stats, ResourceStats))
    check("Stub: cpu_percent ist float", isinstance(stats.cpu_percent, float))
    check("Stub: memory_bytes > 0", stats.memory_bytes > 0)
    check("Stub: container_status = running", stats.container_status == "running")
    check("Stub: uptime_seconds > 0", stats.uptime_seconds > 0)


# ================================================================
# Test 4: Container-Status Persistierung (update_container_status)
# ================================================================
print("\n== Container-Status Persistierung ==")

with app.app_context():
    from app.domain.instances.service import update_container_status, VALID_CONTAINER_STATES
    from app.domain.instances.models import Instance

    inst = db.session.get(Instance, _inst_id)

    # Sicherstellen, dass Instance sauber ist
    inst.container_state = None
    db.session.commit()

    # Gueltige States testen
    for state in ["running", "starting", "stopping", "stopped", "offline"]:
        inst.container_state = None
        db.session.commit()
        result = update_container_status(inst, state)
        check(f"State '{state}' wird gesetzt", result.container_state == state)

    # Ungueltiger State wird ignoriert
    inst.container_state = "running"
    db.session.commit()
    result = update_container_status(inst, "INVALID_STATE")
    check("Ungueltiger State ignoriert", result.container_state == "running")

    result = update_container_status(inst, "")
    check("Leerer String ignoriert", result.container_state == "running")

    result = update_container_status(inst, "   ")
    check("Whitespace ignoriert", result.container_state == "running")

    # Gleicher State erzeugt keinen Re-Write
    inst.container_state = "stopped"
    db.session.commit()
    result = update_container_status(inst, "stopped")
    check("Gleicher State: kein Fehler", result.container_state == "stopped")

    # instance.status bleibt unberuehrt
    inst.status = "provisioning"
    inst.container_state = None
    db.session.commit()
    result = update_container_status(inst, "running")
    check("status bleibt unberuehrt", result.status == "provisioning")
    check("container_state unabhaengig gesetzt", result.container_state == "running")

    # Zuruecksetzen
    inst.status = "stopped"
    inst.container_state = None
    db.session.commit()

    # VALID_CONTAINER_STATES Check
    check("VALID_CONTAINER_STATES enthaelt running", "running" in VALID_CONTAINER_STATES)
    check("VALID_CONTAINER_STATES enthaelt stopped", "stopped" in VALID_CONTAINER_STATES)
    check("VALID_CONTAINER_STATES enthaelt starting", "starting" in VALID_CONTAINER_STATES)
    check("VALID_CONTAINER_STATES enthaelt stopping", "stopping" in VALID_CONTAINER_STATES)
    check("VALID_CONTAINER_STATES enthaelt offline", "offline" in VALID_CONTAINER_STATES)


# ================================================================
# Test 5: Activity-Event bei Statuswechsel
# ================================================================
print("\n== Activity-Event bei Statuswechsel ==")

with app.app_context():
    from app.domain.activity.models import ActivityLog
    from app.domain.activity.events import INSTANCE_CONTAINER_STATE_CHANGED
    from app.domain.instances.service import update_container_status
    from app.domain.instances.models import Instance

    inst = db.session.get(Instance, _inst_id)

    check("Event-Konstante definiert", INSTANCE_CONTAINER_STATE_CHANGED == "instance:container_state_changed")

    # Vorherige Activity-Logs zaehlen
    before_count = ActivityLog.query.filter_by(
        event=INSTANCE_CONTAINER_STATE_CHANGED,
        subject_id=inst.id,
    ).count()

    # State aendern → sollte Activity-Log erzeugen
    inst.container_state = None
    db.session.commit()
    update_container_status(inst, "running")

    after_count = ActivityLog.query.filter_by(
        event=INSTANCE_CONTAINER_STATE_CHANGED,
        subject_id=inst.id,
    ).count()
    check("Activity-Log bei Aenderung erzeugt", after_count == before_count + 1)

    # Gleicher State nochmal → kein neuer Log
    update_container_status(inst, "running")
    same_count = ActivityLog.query.filter_by(
        event=INSTANCE_CONTAINER_STATE_CHANGED,
        subject_id=inst.id,
    ).count()
    check("Kein Activity-Log bei gleichem State", same_count == after_count)

    # Erneuter Wechsel → neuer Log
    update_container_status(inst, "stopped")
    final_count = ActivityLog.query.filter_by(
        event=INSTANCE_CONTAINER_STATE_CHANGED,
        subject_id=inst.id,
    ).count()
    check("Activity-Log bei erneutem Wechsel", final_count == same_count + 1)

    # Log-Inhalt pruefen
    log_entry = ActivityLog.query.filter_by(
        event=INSTANCE_CONTAINER_STATE_CHANGED,
        subject_id=inst.id,
    ).order_by(ActivityLog.created_at.desc()).first()
    check("Log hat subject_type=instance", log_entry.subject_type == "instance")
    check("Log hat Beschreibung", log_entry.description is not None)
    check("Log-Properties enthalten new_state",
          log_entry.properties and log_entry.properties.get("new_state") == "stopped")

    # Zuruecksetzen
    inst.container_state = None
    db.session.commit()


# ================================================================
# Test 6: Agent-Route – Container-Status Callback
# ================================================================
print("\n== Agent-Route Container-Status ==")

with app.app_context():
    from app.domain.instances.models import Instance

    client = app.test_client()
    inst = db.session.get(Instance, _inst_id)

    # Reset container_state
    inst.container_state = None
    db.session.commit()

    # Gueltiger State → 200
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": "running"},
    )
    check("POST running -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Response container_state = running", data.get("container_state") == "running")
    check("Response hat status-Feld", "status" in data)
    check("Response hat message", "message" in data)

    # Bestaetigen: DB persistiert
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    check("DB: container_state = running", inst.container_state == "running")
    check("DB: status bleibt unveraendert", inst.status == "stopped")

    # Weiterer gueltiger State
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": "stopped"},
    )
    check("POST stopped -> 200", resp.status_code == 200)
    check("Response container_state = stopped", resp.get_json().get("container_state") == "stopped")

    # Unbekannte Instance → 404
    resp = client.post(
        "/api/agent/instances/non-existent-uuid/container/status",
        json={"state": "running"},
    )
    check("Unbekannte Instance -> 404", resp.status_code == 404)

    # Fehlender Body → 400
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        content_type="application/json",
    )
    check("Fehlender Body -> 400", resp.status_code == 400)

    # Fehlendes state-Feld → 400
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"wrong_field": "running"},
    )
    check("Fehlendes state-Feld -> 400", resp.status_code == 400)

    # Leerer String → 400
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": ""},
    )
    check("Leerer state -> 400", resp.status_code == 400)

    # Nicht-String state → 400
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": 123},
    )
    check("Nicht-String state -> 400", resp.status_code == 400)

    # Ungueltiger State → 200 (wird ignoriert, kein Crash)
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    inst.container_state = "running"
    db.session.commit()
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": "totally_invalid"},
    )
    check("Ungueltiger State -> 200", resp.status_code == 200)
    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    check("Ungueltiger State ignoriert", inst.container_state == "running")

    # Alle gueltigen States via Route testen
    for state in ["starting", "stopping", "offline"]:
        inst.container_state = None
        db.session.commit()
        resp = client.post(
            f"/api/agent/instances/{_inst_uuid}/container/status",
            json={"state": state},
        )
        check(f"Route: state '{state}' -> 200", resp.status_code == 200)
        check(f"Route: container_state = '{state}'",
              resp.get_json().get("container_state") == state)


# ================================================================
# Test 7: Event-Katalog
# ================================================================
print("\n== Event-Katalog ==")

with app.app_context():
    from app.domain.webhooks.event_catalog import (
        is_valid_webhook_event,
        validate_webhook_events,
        get_event_catalog,
        WEBHOOK_EVENTS,
    )
    from app.domain.activity.events import INSTANCE_CONTAINER_STATE_CHANGED

    check("Event im Webhook-Katalog", INSTANCE_CONTAINER_STATE_CHANGED in WEBHOOK_EVENTS)
    check("Event ist valid", is_valid_webhook_event(INSTANCE_CONTAINER_STATE_CHANGED))

    ok_result, invalid = validate_webhook_events([INSTANCE_CONTAINER_STATE_CHANGED])
    check("Event-Validierung OK", ok_result)
    check("Keine invaliden Events", len(invalid) == 0)

    catalog = get_event_catalog()
    event_names = [e["event"] for e in catalog]
    check("Event in Katalog-Liste", INSTANCE_CONTAINER_STATE_CHANGED in event_names)

    # Beschreibung vorhanden
    entry = next((e for e in catalog if e["event"] == INSTANCE_CONTAINER_STATE_CHANGED), None)
    check("Katalog-Eintrag hat Beschreibung", entry is not None and "description" in entry)


# ================================================================
# Test 8: Client-Resource-API
# ================================================================
print("\n== Client Resource-API ==")

with app.app_context():
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.domain.instances.models import Instance
    from app.domain.endpoints.models import Endpoint

    # Sicherstellen dass Stub-Runner aktiv ist
    set_runner(StubRunnerAdapter())

    client = app.test_client()
    headers = {"X-User-Id": str(_user_id)}

    # Endpoint zuweisen
    ep = db.session.get(Endpoint, _ep_id)
    inst = db.session.get(Instance, _inst_id)
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    inst.owner_id = _user_id
    db.session.commit()

    # Resources abrufen
    resp = client.get(
        f"/api/client/instances/{_inst_uuid}/resources",
        headers=headers,
    )
    check("GET resources -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Resources hat cpu_percent", "cpu_percent" in data)
    check("Resources hat memory_bytes", "memory_bytes" in data)
    check("Resources hat container_status", "container_status" in data)
    check("Resources hat uptime_seconds", "uptime_seconds" in data)

    # Ohne Auth → 401
    resp = client.get(f"/api/client/instances/{_inst_uuid}/resources")
    check("Ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 9: Regression – bestehende Flows
# ================================================================
print("\n== Regression - bestehende Flows ==")

with app.app_context():
    from app.domain.instances.service import (
        handle_install_callback,
        send_power_action,
        set_runner,
        get_runner,
    )
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol
    from app.domain.instances.models import Instance

    set_runner(StubRunnerAdapter())
    inst = db.session.get(Instance, _inst_id)

    # Install-Callback funktioniert weiterhin
    inst.status = "provisioning"
    inst.container_state = None
    db.session.commit()

    result = handle_install_callback(inst, True)
    check("Install-Callback: status = None (ready)", result.status is None)
    check("Install-Callback: container_state unberuehrt",
          result.container_state is None)

    # Power-Action funktioniert weiterhin
    inst.status = "stopped"
    db.session.commit()
    try:
        res = send_power_action(inst, "start")
        check("Power-Action start: OK", res.get("action") == "start")
    except Exception as e:
        fail(f"Power-Action start: Exception", str(e))

    # Agent Health-Route funktioniert
    client = app.test_client()
    resp = client.get("/api/agent/health")
    check("Agent Health -> 200", resp.status_code == 200)

    # Runner-Protocol hat get_instance_resources
    check("RunnerProtocol hat get_instance_resources",
          hasattr(RunnerProtocol, "get_instance_resources"))

    # get_runner liefert Adapter
    runner = get_runner()
    check("get_runner liefert Runner", runner is not None)
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))


# ================================================================
# Test 10: WingsRunnerAdapter.get_instance_resources Signatur
# ================================================================
print("\n== WingsRunnerAdapter Signatur ==")

with app.app_context():
    from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol

    check("WingsRunnerAdapter erbt RunnerProtocol",
          issubclass(WingsRunnerAdapter, RunnerProtocol))

    # Methode existiert und ist nicht mehr der alte Stub
    import inspect
    source = inspect.getsource(WingsRunnerAdapter.get_instance_resources)
    check("get_instance_resources nicht mehr Stub",
          "noch nicht implementiert" not in source)
    check("get_instance_resources nutzt Wings-API",
          "_http" in source or "_parse_wings_resources" in source)


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M15 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
