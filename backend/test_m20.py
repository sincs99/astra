"""Schnelltests fuer Meilenstein 20 - Production Hardening."""

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

_user_id = None
_agent_id = None
_inst_id = None
_inst_uuid = None


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

    set_runner(StubRunnerAdapter())

    user = User(username="m20-user", email="m20@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()

    agent = Agent(name="m20-agent", fqdn="m20.test.dev")
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m20-bp")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25900)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m20-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status=None,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    _user_id = user.id
    _agent_id = agent.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid


# ================================================================
# Test 1: Agent last_seen_at
# ================================================================
print("\n== Agent last_seen_at ==")

with app.app_context():
    from app.domain.agents.models import Agent

    agent = db.session.get(Agent, _agent_id)

    check("last_seen_at Attribut existiert", hasattr(agent, "last_seen_at"))
    check("last_seen_at initial None", agent.last_seen_at is None)
    check("is_stale ohne last_seen → True", agent.is_stale())

    # Touch
    agent.touch()
    db.session.commit()
    check("last_seen_at nach touch gesetzt", agent.last_seen_at is not None)
    check("is_stale nach touch → False", not agent.is_stale())

    # to_dict hat last_seen_at
    d = agent.to_dict()
    check("to_dict hat last_seen_at", "last_seen_at" in d)
    check("to_dict last_seen_at nicht None", d["last_seen_at"] is not None)


# ================================================================
# Test 2: Agent Route aktualisiert last_seen_at
# ================================================================
print("\n== Agent Route last_seen_at ==")

with app.app_context():
    from app.domain.agents.models import Agent
    from app.domain.instances.models import Instance

    agent = db.session.get(Agent, _agent_id)
    agent.last_seen_at = None
    db.session.commit()

    client = app.test_client()
    resp = client.post(
        f"/api/agent/instances/{_inst_uuid}/container/status",
        json={"state": "running"},
    )
    check("Container-Status -> 200", resp.status_code == 200)

    db.session.expire_all()
    agent = db.session.get(Agent, _agent_id)
    check("last_seen_at nach Callback gesetzt", agent.last_seen_at is not None)


# ================================================================
# Test 3: WebhookDelivery-Modell
# ================================================================
print("\n== WebhookDelivery-Modell ==")

with app.app_context():
    from app.domain.webhooks.models import WebhookDelivery, Webhook

    check("WebhookDelivery Klasse existiert", WebhookDelivery is not None)

    # Webhook erstellen
    wh = Webhook(endpoint_url="https://test.dev/hook", events=["instance:created"])
    db.session.add(wh)
    db.session.flush()

    # Delivery erstellen
    delivery = WebhookDelivery(
        webhook_id=wh.id,
        event="instance:created",
        endpoint_url=wh.endpoint_url,
        attempts=2,
        success=True,
        status_code=200,
    )
    db.session.add(delivery)
    db.session.commit()

    check("Delivery ID", delivery.id is not None)
    d = delivery.to_dict()
    check("Delivery to_dict hat event", d["event"] == "instance:created")
    check("Delivery to_dict hat attempts", d["attempts"] == 2)
    check("Delivery to_dict hat success", d["success"] is True)
    check("Delivery to_dict hat status_code", d["status_code"] == 200)

    db.session.delete(delivery)
    db.session.delete(wh)
    db.session.commit()


# ================================================================
# Test 4: Webhook-Dispatcher Retry-Logik
# ================================================================
print("\n== Webhook-Dispatcher Retry ==")

with app.app_context():
    from app.domain.webhooks.dispatcher import (
        _send_to_webhook, _track_delivery, MAX_RETRIES, RETRY_DELAYS,
    )

    check("MAX_RETRIES >= 3", MAX_RETRIES >= 3)
    check("RETRY_DELAYS hat Eintraege", len(RETRY_DELAYS) >= 3)

    # _send_to_webhook gibt Tuple zurueck
    from app.domain.webhooks.models import Webhook
    wh = Webhook(
        endpoint_url="https://invalid.nonexistent.dev/hook",
        events=["test"],
        secret_token="test-secret",
    )
    success, status_code, error = _send_to_webhook(wh, "test", {"data": True})
    check("Ungueltige URL -> success=False", success is False)
    check("Ungueltige URL -> error vorhanden", error is not None)

    # _track_delivery speichert
    from app.domain.webhooks.models import WebhookDelivery
    wh2 = Webhook(endpoint_url="https://track.dev/hook", events=["test"])
    db.session.add(wh2)
    db.session.commit()

    before = WebhookDelivery.query.filter_by(webhook_id=wh2.id).count()
    _track_delivery(wh2, "test", 3, False, None, "Test-Fehler")
    after = WebhookDelivery.query.filter_by(webhook_id=wh2.id).count()
    check("Delivery-Tracking erstellt Record", after == before + 1)

    delivery = WebhookDelivery.query.filter_by(webhook_id=wh2.id).first()
    check("Tracking: attempts = 3", delivery.attempts == 3)
    check("Tracking: success = False", delivery.success is False)
    check("Tracking: error gespeichert", delivery.error == "Test-Fehler")

    db.session.delete(delivery)
    db.session.delete(wh2)
    db.session.commit()


# ================================================================
# Test 5: Health-Check-Endpunkte
# ================================================================
print("\n== Health-Check-Endpunkte ==")

with app.app_context():
    client = app.test_client()

    # Basis Health
    resp = client.get("/health")
    check("Global Health -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health")
    check("Admin Health -> 200", resp.status_code == 200)

    # Detaillierter Health
    resp = client.get("/api/admin/health/detailed")
    check("Detailed Health -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Detailed hat status", "status" in data)
    check("Detailed hat checks", "checks" in data)
    check("Detailed: app = ok", data["checks"].get("app") == "ok")
    check("Detailed: database = ok", data["checks"].get("database") == "ok")
    check("Detailed: agents vorhanden", "agents" in data["checks"])

    agents_data = data["checks"]["agents"]
    check("Agents hat total", "total" in agents_data)
    check("Agents total >= 1", agents_data["total"] >= 1)

    # Agent Health
    resp = client.get("/api/admin/agents/health")
    check("Agents Health -> 200", resp.status_code == 200)
    agents_list = resp.get_json()
    check("Agents Health ist Liste", isinstance(agents_list, list))
    check("Agents Health >= 1", len(agents_list) >= 1)

    agent_health = agents_list[0]
    check("Agent hat name", "name" in agent_health)
    check("Agent hat last_seen_at", "last_seen_at" in agent_health)
    check("Agent hat is_stale", "is_stale" in agent_health)
    check("Agent hat is_active", "is_active" in agent_health)


# ================================================================
# Test 6: Runner-Fehler konsistent
# ================================================================
print("\n== Runner-Fehler konsistent ==")

with app.app_context():
    from app.infrastructure.runner.wings_http import WingsHttpClient, WingsResponse
    from app.infrastructure.runner.protocol import ResourceStats
    from app.infrastructure.runner.wings_adapter import _parse_wings_resources

    # WingsResponse bei Fehler
    error_response = WingsResponse(success=False, status_code=500, data=None, error="HTTP 500")
    check("WingsResponse error", error_response.error == "HTTP 500")
    check("WingsResponse not success", error_response.success is False)

    # ResourceStats bei Fehler
    stats = _parse_wings_resources(None)
    check("Null-Resources: container_status=unknown", stats.container_status == "unknown")

    stats = _parse_wings_resources({})
    check("Empty-Resources: container_status=unknown", stats.container_status == "unknown")


# ================================================================
# Test 7: Regression
# ================================================================
print("\n== Regression ==")

with app.app_context():
    from app.domain.instances.service import get_runner, VALID_CONTAINER_STATES, set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol

    set_runner(StubRunnerAdapter())
    runner = get_runner()
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))
    check("VALID_CONTAINER_STATES", len(VALID_CONTAINER_STATES) >= 5)

    client = app.test_client()
    check("Agent Health -> 200", client.get("/api/agent/health").status_code == 200)
    check("Client Health -> 200", client.get("/api/client/health").status_code == 200)
    check("Auth Health -> 200", client.get("/api/auth/health").status_code == 200)

    # Login weiter OK
    resp = client.post("/api/auth/login", json={
        "login": "m20-user", "password": "testpass",
    })
    check("Login -> 200", resp.status_code == 200)

    # Webhook-Katalog >= 23 Events
    from app.domain.webhooks.event_catalog import get_event_catalog
    check("Webhook-Katalog >= 23", len(get_event_catalog()) >= 23)


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M20 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
