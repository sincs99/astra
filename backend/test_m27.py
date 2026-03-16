"""Schnelltests fuer Meilenstein 27 - Release Candidate Hardening."""

import sys
import os
import json

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

    user = User(username="m27-user", email="m27@test.dev")
    user.set_password("testpass123")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    bp = Blueprint(name="m27-bp")
    db.session.add(bp)
    db.session.flush()
    _bp_id = bp.id

    agent = Agent(name="m27-agent", fqdn="m27.test.dev")
    agent.touch()
    db.session.add(agent)
    db.session.flush()
    _agent_id = agent.id

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25800)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m27-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        memory=512, disk=1024, cpu=100,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid
    db.session.commit()


client = app.test_client()


# ================================================================
# Test 1: Security - Keine Secrets in Responses
# ================================================================
print("\n== Security: Keine Secrets in Responses ==")

with app.app_context():
    # User to_dict darf kein Passwort-Hash enthalten
    user = db.session.get(User, _user_id)
    ud = user.to_dict()
    check("User to_dict: kein password_hash", "password_hash" not in ud)
    check("User to_dict: kein password", "password" not in ud)

    # Agent to_dict darf kein daemon_token enthalten
    agent = db.session.get(Agent, _agent_id)
    ad = agent.to_dict()
    check("Agent to_dict: kein daemon_token", "daemon_token" not in ad or ad.get("daemon_token") is None)

    # API-Responses pruefen
    resp = client.get("/api/admin/agents")
    agents_data = resp.get_json()
    if agents_data:
        # daemon_token_id ist erlaubt (Non-Secret ID), daemon_token (Secret) darf nicht drin sein
        check("GET /agents: kein daemon_token Secret",
              "daemon_token" not in agents_data[0] or agents_data[0].get("daemon_token") is None)

    resp = client.get("/api/admin/users")
    raw = resp.get_data(as_text=True)
    check("GET /users: kein password_hash", "password_hash" not in raw)

    # Ops-Endpunkte: keine Secrets
    for endpoint in ["/ops/version", "/ops/info", "/health", "/health/ready"]:
        resp = client.get(endpoint)
        raw = resp.get_data(as_text=True).lower()
        check(f"{endpoint}: kein secret_key", "dev-secret-key" not in raw)
        check(f"{endpoint}: kein jwt_secret", "jwt-secret-key" not in raw)


# ================================================================
# Test 2: Security - Auth-Fehlerbehandlung
# ================================================================
print("\n== Security: Auth-Fehlerbehandlung ==")

with app.app_context():
    # Login mit falschen Credentials
    resp = client.post("/api/auth/login", json={"login": "wrong", "password": "wrong"})
    check("Login falsch: nicht 200", resp.status_code != 200)
    check("Login falsch: 401", resp.status_code == 401, f"got {resp.status_code}")

    # Login ohne Body
    resp = client.post("/api/auth/login", json={})
    check("Login ohne Daten: nicht 200", resp.status_code != 200)

    # Login mit leerem Passwort
    resp = client.post("/api/auth/login", json={"login": "m27-user", "password": ""})
    check("Login leeres PW: nicht 200", resp.status_code != 200)


# ================================================================
# Test 3: Failure Cases - Ungueltige Eingaben
# ================================================================
print("\n== Failure Cases: Ungueltige Eingaben ==")

with app.app_context():
    # Agent ohne Name
    resp = client.post("/api/admin/agents", json={"fqdn": "noname.test.dev"})
    check("Agent ohne Name: 400", resp.status_code == 400, f"got {resp.status_code}")

    # Agent ohne FQDN
    resp = client.post("/api/admin/agents", json={"name": "no-fqdn"})
    check("Agent ohne FQDN: 400", resp.status_code == 400)

    # Instance ohne erforderliche Felder
    resp = client.post("/api/admin/instances", json={"name": "incomplete"})
    check("Instance ohne Felder: 400", resp.status_code == 400)

    # Instance mit nicht existierendem Agent
    resp = client.post("/api/admin/instances", json={
        "name": "bad-agent", "owner_id": _user_id, "agent_id": 99999, "blueprint_id": _bp_id
    })
    check("Instance bad agent: 404", resp.status_code == 404, f"got {resp.status_code}")

    # Instance mit nicht existierendem User
    resp = client.post("/api/admin/instances", json={
        "name": "bad-user", "owner_id": 99999, "agent_id": _agent_id, "blueprint_id": _bp_id
    })
    check("Instance bad user: 404", resp.status_code == 404)

    # Webhook ohne URL
    resp = client.post("/api/admin/webhooks", json={"events": ["instance:created"]})
    check("Webhook ohne URL: 400", resp.status_code == 400)

    # Leerer Request-Body
    resp = client.post("/api/admin/agents", data="", content_type="application/json")
    check("Agent leerer Body: 400", resp.status_code == 400, f"got {resp.status_code}")


# ================================================================
# Test 4: Status-Konsistenz
# ================================================================
print("\n== Status-Konsistenz ==")

with app.app_context():
    # Lifecycle und Container-State sind getrennt
    inst = db.session.get(Instance, _inst_id)
    d = inst.to_dict()
    check("Instance hat status UND container_state", "status" in d and "container_state" in d)
    check("status und container_state sind verschieden", d["status"] != d["container_state"] or d["status"] is None)

    # Agent: Health und Maintenance sind getrennt
    agent = db.session.get(Agent, _agent_id)
    check("Agent health_status != maintenance (getrennt)",
          agent.get_health_status() in ("healthy", "stale", "degraded", "unreachable"))
    check("Agent in_maintenance ist bool", isinstance(agent.in_maintenance, bool))

    # Monitoring-Data hat beides getrennt
    resp = client.get("/api/admin/agents/monitoring")
    data = resp.get_json()
    if data:
        a = data[0]
        check("Monitoring: health_status vorhanden", "health_status" in a)
        check("Monitoring: maintenance_mode vorhanden", "maintenance_mode" in a)
        check("Monitoring: available_for_deployment vorhanden", "available_for_deployment" in a)


# ================================================================
# Test 5: Ops-/Preflight-Endpunkte korrekt
# ================================================================
print("\n== Ops-/Preflight-Endpunkte ==")

with app.app_context():
    from app.version import VERSION

    resp = client.get("/health")
    check("GET /health -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/health: status=ok", data["status"] == "ok")
    check("/health: version = RC", VERSION in data["version"])

    resp = client.get("/health/ready")
    check("GET /health/ready -> 200", resp.status_code == 200)

    resp = client.get("/ops/version")
    check("GET /ops/version -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/ops/version: version korrekt", data["version"] == VERSION)
    check("/ops/version: hat environment", "environment" in data)

    resp = client.get("/ops/upgrade-status")
    check("GET /ops/upgrade-status -> 200", resp.status_code == 200)

    resp = client.get("/ops/preflight")
    check("GET /ops/preflight -> 200 oder 503", resp.status_code in (200, 503))
    data = resp.get_json()
    check("/ops/preflight: hat compatible", "compatible" in data)

    resp = client.get("/ops/info")
    check("GET /ops/info -> 200", resp.status_code == 200)


# ================================================================
# Test 6: RC End-to-End Flow - Agent -> Instance -> Power
# ================================================================
print("\n== RC End-to-End Flow ==")

with app.app_context():
    # Agent erstellen
    resp = client.post("/api/admin/agents", json={
        "name": "m27-e2e-agent", "fqdn": "e2e.m27.test.dev"
    })
    check("E2E: Agent erstellt -> 201", resp.status_code == 201)
    e2e_agent_id = resp.get_json()["id"]

    # Endpoint erstellen
    resp = client.post(f"/api/admin/agents/{e2e_agent_id}/endpoints", json={
        "port": 25900
    })
    check("E2E: Endpoint erstellt -> 201", resp.status_code == 201)

    # Instance erstellen
    resp = client.post("/api/admin/instances", json={
        "name": "m27-e2e-instance",
        "owner_id": _user_id,
        "agent_id": e2e_agent_id,
        "blueprint_id": _bp_id,
    })
    check("E2E: Instance erstellt -> 201", resp.status_code == 201)
    e2e_uuid = resp.get_json()["uuid"]

    # Install-Callback
    resp = client.post(f"/api/agent/instances/{e2e_uuid}/install", json={
        "successful": True
    })
    check("E2E: Install-Callback -> 200", resp.status_code == 200)


# ================================================================
# Test 7: RC Maintenance-Guard Flow
# ================================================================
print("\n== RC Maintenance-Guard ==")

with app.app_context():
    # Agent in Maintenance
    resp = client.post(f"/api/admin/agents/{e2e_agent_id}/maintenance", json={
        "reason": "RC Test"
    })
    check("Maintenance Enable -> 200", resp.status_code == 200)

    # Deployment versuchen
    resp = client.post("/api/admin/instances", json={
        "name": "m27-should-fail",
        "owner_id": _user_id,
        "agent_id": e2e_agent_id,
        "blueprint_id": _bp_id,
    })
    check("Deployment auf Maintenance -> 409", resp.status_code == 409)

    # Maintenance deaktivieren
    resp = client.delete(f"/api/admin/agents/{e2e_agent_id}/maintenance")
    check("Maintenance Disable -> 200", resp.status_code == 200)


# ================================================================
# Test 8: Job-System unter Fehlerbedingungen
# ================================================================
print("\n== Job-System Fehlerbehandlung ==")

with app.app_context():
    from app.infrastructure.jobs.queue import enqueue_job
    from app.infrastructure.jobs.models import JobRecord, JobStatus
    from app.infrastructure.jobs.registry import register_handler

    # Job mit Fehler
    def bad_handler(payload):
        raise ValueError("RC Testfehler")

    register_handler("rc_bad_job", bad_handler)

    job = enqueue_job(job_type="rc_bad_job", payload={}, max_attempts=2)
    db.session.refresh(job)
    check("Bad Job -> failed", job.status == JobStatus.FAILED)
    check("Bad Job error vorhanden", job.error is not None)
    check("Bad Job attempts = 2", job.attempts == 2)

    # Job-API zeigt Fehler korrekt
    resp = client.get(f"/api/admin/jobs/{job.id}")
    check(f"GET /admin/jobs/{job.id} -> 200", resp.status_code == 200)
    jdata = resp.get_json()
    check("Job-API: status=failed", jdata["status"] == "failed")
    check("Job-API: error vorhanden", jdata["error"] is not None)


# ================================================================
# Test 9: Nicht-existierende Ressourcen (404)
# ================================================================
print("\n== 404 Handling ==")

with app.app_context():
    resp = client.get("/api/admin/agents/99999/monitoring")
    check("Agent 99999 monitoring -> 404", resp.status_code == 404)

    resp = client.get("/api/admin/jobs/99999")
    check("Job 99999 -> 404", resp.status_code == 404)

    resp = client.post("/api/admin/agents/99999/maintenance", json={})
    check("Maintenance 99999 -> 404", resp.status_code == 404)

    resp = client.delete("/api/admin/agents/99999/maintenance")
    check("Maintenance delete 99999 -> 404", resp.status_code == 404)


# ================================================================
# Test 10: Vollstaendige Regression
# ================================================================
print("\n== Vollstaendige Regression ==")

with app.app_context():
    endpoints = [
        ("/health", 200),
        ("/health/ready", 200),
        ("/ops/info", 200),
        ("/ops/version", 200),
        ("/api/admin/health", 200),
        ("/api/admin/health/detailed", 200),
        ("/api/admin/agents", 200),
        ("/api/admin/agents/health", 200),
        ("/api/admin/agents/monitoring", 200),
        ("/api/admin/fleet/summary", 200),
        ("/api/admin/blueprints", 200),
        ("/api/admin/instances", 200),
        ("/api/admin/endpoints", 200),
        ("/api/admin/webhooks", 200),
        ("/api/admin/webhooks/events", 200),
        ("/api/admin/activity", 200),
        ("/api/admin/jobs", 200),
        ("/api/admin/jobs/summary", 200),
        ("/api/admin/runner/info", 200),
        ("/api/admin/system/version", 200),
        ("/api/admin/database-providers", 200),
    ]
    for path, expected in endpoints:
        resp = client.get(path)
        check(f"GET {path} -> {expected}", resp.status_code == expected, f"got {resp.status_code}")


# ================================================================
# Test 11: Version ist RC
# ================================================================
print("\n== Version ==")

with app.app_context():
    from app.version import VERSION
    check("VERSION ist RC", "rc" in VERSION.lower() or "0.27" in VERSION, f"got {VERSION}")

    from app import __version__
    check("__version__ == VERSION", __version__ == VERSION)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*60}")
print(f"M27 Release Candidate Hardening: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
