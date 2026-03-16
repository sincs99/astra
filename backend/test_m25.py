"""Schnelltests fuer Meilenstein 25 - Agent Maintenance & Fleet Operations."""

import sys
import os
from datetime import datetime, timezone

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
_agent1_id = None
_agent2_id = None
_bp_id = None
_ep_id = None


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    user = User(username="m25-user", email="m25@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    bp = Blueprint(name="m25-bp")
    db.session.add(bp)
    db.session.flush()
    _bp_id = bp.id

    agent1 = Agent(name="m25-normal-agent", fqdn="normal.m25.test.dev")
    agent1.touch()
    db.session.add(agent1)
    db.session.flush()
    _agent1_id = agent1.id

    agent2 = Agent(name="m25-maint-agent", fqdn="maint.m25.test.dev")
    agent2.touch()
    db.session.add(agent2)
    db.session.flush()
    _agent2_id = agent2.id

    ep1 = Endpoint(agent_id=agent1.id, ip="0.0.0.0", port=25565)
    ep2 = Endpoint(agent_id=agent2.id, ip="0.0.0.0", port=25566)
    db.session.add_all([ep1, ep2])
    db.session.flush()
    _ep_id = ep1.id

    db.session.commit()


# ================================================================
# Test 1: Agent-Modell Maintenance-Felder
# ================================================================
print("\n== Agent-Modell Maintenance ==")

with app.app_context():
    from app.domain.agents.models import Agent

    agent = db.session.get(Agent, _agent1_id)
    check("maintenance_mode Default = False", agent.maintenance_mode is None or agent.maintenance_mode is False)
    check("in_maintenance Property = False", agent.in_maintenance is False)
    check("is_available_for_deployment = True", agent.is_available_for_deployment() is True)
    check("maintenance_reason Default = None", agent.maintenance_reason is None)
    check("maintenance_started_at Default = None", agent.maintenance_started_at is None)

    # to_dict enthaelt Maintenance-Felder
    d = agent.to_dict()
    check("to_dict hat maintenance_mode", "maintenance_mode" in d)
    check("to_dict hat maintenance_reason", "maintenance_reason" in d)
    check("to_dict hat maintenance_started_at", "maintenance_started_at" in d)


# ================================================================
# Test 2: Maintenance-Service
# ================================================================
print("\n== Maintenance-Service ==")

with app.app_context():
    from app.domain.agents.maintenance_service import (
        enable_maintenance, disable_maintenance, MaintenanceError,
    )

    # Maintenance aktivieren
    agent = enable_maintenance(_agent2_id, reason="Hardware-Upgrade")
    check("enable: maintenance_mode = True", agent.maintenance_mode is True)
    check("enable: in_maintenance = True", agent.in_maintenance is True)
    check("enable: reason gespeichert", agent.maintenance_reason == "Hardware-Upgrade")
    check("enable: maintenance_started_at gesetzt", agent.maintenance_started_at is not None)
    check("enable: is_available_for_deployment = False", agent.is_available_for_deployment() is False)

    # Idempotent: nochmals aktivieren
    agent2 = enable_maintenance(_agent2_id, reason="Update")
    check("idempotent enable: kein Fehler", agent2 is not None)
    check("idempotent enable: reason aktualisiert", agent2.maintenance_reason == "Update")

    # Maintenance deaktivieren
    agent3 = disable_maintenance(_agent2_id)
    check("disable: maintenance_mode = False", agent3.maintenance_mode is False)
    check("disable: in_maintenance = False", agent3.in_maintenance is False)
    check("disable: reason = None", agent3.maintenance_reason is None)
    check("disable: maintenance_started_at = None", agent3.maintenance_started_at is None)
    check("disable: is_available_for_deployment = True", agent3.is_available_for_deployment() is True)

    # Idempotent: nochmals deaktivieren
    agent4 = disable_maintenance(_agent2_id)
    check("idempotent disable: kein Fehler", agent4 is not None)

    # Nicht existierender Agent
    try:
        enable_maintenance(99999)
        fail("enable non-existent: sollte Fehler werfen")
    except MaintenanceError as e:
        check("enable non-existent: 404", e.status_code == 404)

    try:
        disable_maintenance(99999)
        fail("disable non-existent: sollte Fehler werfen")
    except MaintenanceError as e:
        check("disable non-existent: 404", e.status_code == 404)


# ================================================================
# Test 3: Placement - Deployment auf Maintenance-Agent verhindern
# ================================================================
print("\n== Placement / Maintenance-Guard ==")

with app.app_context():
    from app.domain.instances.service import create_instance, InstanceCreationError

    # Agent in Maintenance setzen
    enable_maintenance(_agent2_id, reason="Wartung")

    # Deployment auf Maintenance-Agent muss fehlen
    try:
        create_instance(
            name="m25-should-fail",
            owner_id=_user_id,
            agent_id=_agent2_id,
            blueprint_id=_bp_id,
        )
        fail("Deployment auf Maintenance-Agent: sollte 409 liefern")
    except InstanceCreationError as e:
        check("Deployment auf Maintenance-Agent -> 409", e.status_code == 409)
        check("Fehlermeldung enthaelt 'Maintenance'", "Maintenance" in e.message)

    # Deployment auf normalen Agent muss funktionieren
    try:
        inst = create_instance(
            name="m25-on-normal",
            owner_id=_user_id,
            agent_id=_agent1_id,
            blueprint_id=_bp_id,
        )
        check("Deployment auf normalen Agent: OK", inst is not None)
    except InstanceCreationError as e:
        fail(f"Deployment auf normalen Agent fehlgeschlagen: {e.message}")

    # Maintenance deaktivieren
    disable_maintenance(_agent2_id)


# ================================================================
# Test 4: Admin-API Maintenance-Endpunkte
# ================================================================
print("\n== Admin-API Maintenance ==")

client = app.test_client()

with app.app_context():
    # POST /agents/<id>/maintenance
    resp = client.post(f"/api/admin/agents/{_agent1_id}/maintenance",
                       json={"reason": "Test-Wartung"})
    check("POST maintenance -> 200", resp.status_code == 200, f"got {resp.status_code}")
    data = resp.get_json()
    check("Response hat message", "message" in data)
    check("Response hat agent", "agent" in data)
    check("Agent maintenance_mode = True", data["agent"]["maintenance_mode"] is True)
    check("Agent reason = Test-Wartung", data["agent"]["maintenance_reason"] == "Test-Wartung")

    # Idempotent: nochmals POST
    resp = client.post(f"/api/admin/agents/{_agent1_id}/maintenance", json={})
    check("Idempotent POST -> 200", resp.status_code == 200)

    # DELETE /agents/<id>/maintenance
    resp = client.delete(f"/api/admin/agents/{_agent1_id}/maintenance")
    check("DELETE maintenance -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Agent nach DELETE: maintenance_mode = False", data["agent"]["maintenance_mode"] is False)

    # PATCH /agents/<id>/maintenance
    client.post(f"/api/admin/agents/{_agent1_id}/maintenance",
                json={"reason": "Original"})
    resp = client.patch(f"/api/admin/agents/{_agent1_id}/maintenance",
                        json={"reason": "Aktualisiert"})
    check("PATCH maintenance -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("PATCH reason aktualisiert", data["agent"]["maintenance_reason"] == "Aktualisiert")

    # Aufraumen
    client.delete(f"/api/admin/agents/{_agent1_id}/maintenance")

    # 404 fuer nicht existierenden Agent
    resp = client.post("/api/admin/agents/99999/maintenance", json={})
    check("POST 99999/maintenance -> 404", resp.status_code == 404)

    resp = client.delete("/api/admin/agents/99999/maintenance")
    check("DELETE 99999/maintenance -> 404", resp.status_code == 404)


# ================================================================
# Test 5: Monitoring zeigt Maintenance korrekt an
# ================================================================
print("\n== Monitoring + Maintenance ==")

with app.app_context():
    # Agent in Maintenance setzen
    enable_maintenance(_agent2_id, reason="Monitoring-Test")

    resp = client.get("/api/admin/agents/monitoring")
    check("GET /agents/monitoring -> 200", resp.status_code == 200)
    data = resp.get_json()

    maint_agents = [a for a in data if a["id"] == _agent2_id]
    check("Maintenance-Agent in Monitoring gefunden", len(maint_agents) == 1)
    if maint_agents:
        ma = maint_agents[0]
        check("monitoring: maintenance_mode = True", ma["maintenance_mode"] is True)
        check("monitoring: maintenance_reason vorhanden", ma["maintenance_reason"] == "Monitoring-Test")
        check("monitoring: maintenance_started_at vorhanden", ma["maintenance_started_at"] is not None)
        check("monitoring: available_for_deployment = False", ma["available_for_deployment"] is False)
        # Health und Maintenance getrennt
        check("monitoring: health_status != maintenance (getrennt)",
              ma["health_status"] in ("healthy", "stale", "degraded", "unreachable"))

    # Fleet Summary
    resp = client.get("/api/admin/fleet/summary")
    check("GET /fleet/summary -> 200", resp.status_code == 200)
    summary = resp.get_json()
    check("summary hat maintenance_agents", "maintenance_agents" in summary)
    check("summary maintenance_agents >= 1", summary["maintenance_agents"] >= 1,
          f"got {summary.get('maintenance_agents')}")

    # Aufraumen
    disable_maintenance(_agent2_id)


# ================================================================
# Test 6: Activity-/Webhook-Events
# ================================================================
print("\n== Activity/Webhook Events ==")

with app.app_context():
    from app.domain.activity.events import AGENT_MAINTENANCE_ENABLED, AGENT_MAINTENANCE_DISABLED

    check("AGENT_MAINTENANCE_ENABLED definiert",
          AGENT_MAINTENANCE_ENABLED == "agent:maintenance_enabled")
    check("AGENT_MAINTENANCE_DISABLED definiert",
          AGENT_MAINTENANCE_DISABLED == "agent:maintenance_disabled")

    # Event-Katalog
    from app.domain.webhooks.event_catalog import is_valid_webhook_event
    check("maintenance_enabled im Webhook-Katalog",
          is_valid_webhook_event("agent:maintenance_enabled"))
    check("maintenance_disabled im Webhook-Katalog",
          is_valid_webhook_event("agent:maintenance_disabled"))

    # Activity-Log pruefen
    from app.domain.activity.models import ActivityLog
    enable_maintenance(_agent2_id, reason="Event-Test")
    disable_maintenance(_agent2_id)

    logs = ActivityLog.query.filter(
        ActivityLog.event.in_(["agent:maintenance_enabled", "agent:maintenance_disabled"])
    ).all()
    check("Activity-Logs fuer Maintenance existieren", len(logs) >= 2,
          f"got {len(logs)}")


# ================================================================
# Test 7: Bestehende Endpunkte intakt
# ================================================================
print("\n== Regression ==")

with app.app_context():
    resp = client.get("/api/admin/agents")
    check("GET /admin/agents -> 200", resp.status_code == 200)
    data = resp.get_json()
    if data:
        check("to_dict hat maintenance_mode", "maintenance_mode" in data[0])

    resp = client.get("/api/admin/agents/health")
    check("GET /admin/agents/health -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health")
    check("GET /admin/health -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health/detailed")
    check("GET /admin/health/detailed -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/agents/monitoring")
    check("GET /admin/agents/monitoring -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/fleet/summary")
    check("GET /admin/fleet/summary -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/jobs")
    check("GET /admin/jobs -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/system/version")
    check("GET /admin/system/version -> 200", resp.status_code == 200)

    resp = client.get("/health")
    check("GET /health -> 200", resp.status_code == 200)

    resp = client.get("/ops/version")
    check("GET /ops/version -> 200", resp.status_code == 200)

    # Agent erstellen geht noch
    resp = client.post("/api/admin/agents", json={
        "name": "m25-regression", "fqdn": "regression.m25.test.dev"
    })
    check("POST /admin/agents -> 201", resp.status_code == 201)


# ================================================================
# Test 8: Edge Cases
# ================================================================
print("\n== Edge Cases ==")

with app.app_context():
    # Inaktiver Agent: in_maintenance vs is_available_for_deployment
    agent = db.session.get(Agent, _agent1_id)
    agent.is_active = False
    agent.maintenance_mode = False
    check("inactive Agent: is_available_for_deployment = False",
          agent.is_available_for_deployment() is False)

    agent.is_active = True
    agent.maintenance_mode = True
    check("active + maintenance: is_available_for_deployment = False",
          agent.is_available_for_deployment() is False)

    agent.is_active = True
    agent.maintenance_mode = False
    check("active + no maintenance: is_available_for_deployment = True",
          agent.is_available_for_deployment() is True)

    db.session.rollback()


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*60}")
print(f"M25 Agent Maintenance & Fleet Operations: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
