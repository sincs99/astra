"""Schnelltests fuer Meilenstein 22 - Agent Fleet Monitoring & Capacity Dashboard."""

import sys
import os
import json
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
_agent1_id = None
_agent2_id = None
_inst1_id = None
_inst2_id = None
_bp_id = None


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

    # User
    user = User(username="m22-user", email="m22@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    # Blueprint
    bp = Blueprint(name="m22-bp")
    db.session.add(bp)
    db.session.flush()
    _bp_id = bp.id

    # Agent 1: healthy, mit Kapazitaet
    agent1 = Agent(
        name="m22-healthy-agent",
        fqdn="healthy.m22.test.dev",
        memory_total=8192,
        disk_total=102400,
        cpu_total=400,
        memory_overalloc=20,
        disk_overalloc=0,
        cpu_overalloc=50,
    )
    agent1.touch()  # aktiv + kuerzlich gesehen
    db.session.add(agent1)
    db.session.flush()
    _agent1_id = agent1.id

    # Agent 2: stale (kein last_seen_at update, aber mit altem Timestamp)
    agent2 = Agent(
        name="m22-stale-agent",
        fqdn="stale.m22.test.dev",
        memory_total=4096,
        disk_total=51200,
        cpu_total=200,
    )
    agent2.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.session.add(agent2)
    db.session.flush()
    _agent2_id = agent2.id

    # Endpoints fuer Agent 1
    ep1 = Endpoint(agent_id=agent1.id, ip="0.0.0.0", port=25565)
    ep2 = Endpoint(agent_id=agent1.id, ip="0.0.0.0", port=25566)
    ep3 = Endpoint(agent_id=agent1.id, ip="0.0.0.0", port=25567, is_locked=True)
    db.session.add_all([ep1, ep2, ep3])
    db.session.flush()

    # Endpoint fuer Agent 2
    ep4 = Endpoint(agent_id=agent2.id, ip="0.0.0.0", port=25565)
    db.session.add(ep4)
    db.session.flush()

    # Instance 1 auf Agent 1
    inst1 = Instance(
        name="m22-inst1",
        owner_id=user.id,
        agent_id=agent1.id,
        blueprint_id=bp.id,
        memory=1024,
        disk=10240,
        cpu=100,
    )
    db.session.add(inst1)
    db.session.flush()
    ep1.instance_id = inst1.id
    _inst1_id = inst1.id

    # Instance 2 auf Agent 1
    inst2 = Instance(
        name="m22-inst2",
        owner_id=user.id,
        agent_id=agent1.id,
        blueprint_id=bp.id,
        memory=2048,
        disk=20480,
        cpu=200,
    )
    db.session.add(inst2)
    db.session.flush()
    ep2.instance_id = inst2.id
    _inst2_id = inst2.id

    db.session.commit()


# ================================================================
# Test 1: Agent-Kapazitaetsmodell
# ================================================================
print("\n== Agent-Kapazitaetsmodell ==")

with app.app_context():
    from app.domain.agents.models import Agent

    agent = db.session.get(Agent, _agent1_id)

    # Effektive Kapazitaet mit Overalloc
    check(
        "effective_memory berechnet korrekt (8192 + 20%)",
        agent.get_effective_memory() == 9830,
        f"got {agent.get_effective_memory()}"
    )
    check(
        "effective_disk ohne Overalloc (102400 + 0%)",
        agent.get_effective_disk() == 102400,
        f"got {agent.get_effective_disk()}"
    )
    check(
        "effective_cpu mit 50% Overalloc (400 + 50%)",
        agent.get_effective_cpu() == 600,
        f"got {agent.get_effective_cpu()}"
    )

    # Kapazitaets-Summary
    cap = agent.get_capacity_summary()
    check("capacity_summary hat memory_total_mb", cap["memory_total_mb"] == 8192)
    check("capacity_summary hat effective_memory_mb", cap["effective_memory_mb"] == 9830)
    check("capacity_summary hat overalloc Felder", cap["memory_overalloc_percent"] == 20)


# ================================================================
# Test 2: Auslastungsberechnung (Utilization)
# ================================================================
print("\n== Auslastungsberechnung ==")

with app.app_context():
    agent = db.session.get(Agent, _agent1_id)

    util = agent.get_utilization_summary()
    check("instance_count = 2", util["instance_count"] == 2, f"got {util['instance_count']}")
    check(
        "used_memory = 1024 + 2048 = 3072",
        util["used_memory_mb"] == 3072,
        f"got {util['used_memory_mb']}"
    )
    check(
        "used_disk = 10240 + 20480 = 30720",
        util["used_disk_mb"] == 30720,
        f"got {util['used_disk_mb']}"
    )
    check(
        "used_cpu = 100 + 200 = 300",
        util["used_cpu_percent"] == 300,
        f"got {util['used_cpu_percent']}"
    )

    # Memory Utilization: 3072 / 9830 * 100 = 31.2%
    check(
        "memory_utilization berechnet korrekt",
        abs(util["memory_utilization"] - 31.2) < 0.2,
        f"got {util['memory_utilization']}"
    )

    # CPU Utilization: 300 / 600 * 100 = 50.0%
    check(
        "cpu_utilization = 50.0%",
        util["cpu_utilization"] == 50.0,
        f"got {util['cpu_utilization']}"
    )

    # Agent 2: keine Instances
    agent2 = db.session.get(Agent, _agent2_id)
    util2 = agent2.get_utilization_summary()
    check("agent2 instance_count = 0", util2["instance_count"] == 0)
    check("agent2 used_memory = 0", util2["used_memory_mb"] == 0)


# ================================================================
# Test 3: Health-Status-Regeln
# ================================================================
print("\n== Health-Status-Regeln ==")

with app.app_context():
    agent1 = db.session.get(Agent, _agent1_id)
    agent2 = db.session.get(Agent, _agent2_id)

    # Agent 1: gerade gesehen -> healthy
    check(
        "agent1 health = healthy",
        agent1.get_health_status() == "healthy",
        f"got {agent1.get_health_status()}"
    )

    # Agent 2: 30 Minuten alt -> stale
    check(
        "agent2 health = stale",
        agent2.get_health_status() == "stale",
        f"got {agent2.get_health_status()}"
    )

    # Agent ohne last_seen_at -> unreachable
    agent_new = Agent(name="test-unreach", fqdn="unreach.test.dev", is_active=True)
    check(
        "agent ohne last_seen_at = unreachable",
        agent_new.get_health_status() == "unreachable",
        f"got {agent_new.get_health_status()}, is_active={agent_new.is_active}, last_seen={agent_new.last_seen_at}"
    )

    # Inaktiver Agent -> degraded
    agent_inactive = Agent(name="test-inactive", fqdn="inactive.test.dev", is_active=False)
    agent_inactive.last_seen_at = datetime.now(timezone.utc)
    check(
        "inaktiver Agent = degraded",
        agent_inactive.get_health_status() == "degraded"
    )

    # is_stale bei konfiguriertem Schwellwert
    check(
        "agent2 is_stale(max_minutes=60) = False (30 < 60)",
        not agent2.is_stale(max_minutes=60)
    )
    check(
        "agent2 is_stale(max_minutes=10) = True (30 > 10)",
        agent2.is_stale(max_minutes=10)
    )

    # Health-Summary
    hs = agent1.get_health_summary()
    check("health_summary hat health_status", "health_status" in hs)
    check("health_summary hat is_stale", "is_stale" in hs)
    check("health_summary hat last_seen_at", "last_seen_at" in hs)


# ================================================================
# Test 4: Monitoring-Service
# ================================================================
print("\n== Monitoring-Service ==")

with app.app_context():
    from app.domain.agents.monitoring_service import (
        get_agent_monitoring,
        get_all_agents_monitoring,
        get_single_agent_monitoring,
        get_fleet_summary,
    )

    # Einzelner Agent
    agent = db.session.get(Agent, _agent1_id)
    entry = get_agent_monitoring(agent)
    check("monitoring entry hat id", entry["id"] == _agent1_id, f"got {entry['id']}")
    check("monitoring entry hat name", entry["name"] == "m22-healthy-agent", f"got {entry['name']}")
    check("monitoring entry hat fqdn", entry["fqdn"] == "healthy.m22.test.dev", f"got {entry['fqdn']}")
    check("monitoring entry hat health_status", entry["health_status"] == "healthy", f"got {entry['health_status']}")
    check("monitoring entry hat capacity", "capacity" in entry)
    check("monitoring entry hat utilization", "utilization" in entry)
    check("monitoring entry hat instance_count", entry["instance_count"] == 2)
    check("monitoring entry hat endpoint_summary", "endpoint_summary" in entry)

    # Endpoint-Summary
    ep_sum = entry["endpoint_summary"]
    check("endpoint_summary total = 3", ep_sum["total"] == 3, f"got {ep_sum['total']}")
    check("endpoint_summary assigned = 2", ep_sum["assigned"] == 2, f"got {ep_sum['assigned']}")
    check("endpoint_summary locked = 1", ep_sum["locked"] == 1, f"got {ep_sum['locked']}")
    check("endpoint_summary free = 0", ep_sum["free"] == 0, f"got {ep_sum['free']}")

    # Alle Agents
    all_agents = get_all_agents_monitoring()
    check("all_agents liefert >= 2 Agents", len(all_agents) >= 2, f"got {len(all_agents)}")

    # Filter: nur healthy
    healthy_only = get_all_agents_monitoring(health_filter="healthy")
    check(
        "health_filter=healthy: alle Ergebnisse = healthy",
        all(a["health_status"] == "healthy" for a in healthy_only)
    )

    # Filter: nur stale
    stale_only = get_all_agents_monitoring(health_filter="stale")
    check(
        "health_filter=stale: alle Ergebnisse = stale",
        all(a["health_status"] == "stale" for a in stale_only)
    )
    check("stale_only hat mindestens 1 Agent", len(stale_only) >= 1)

    # Suche
    search_result = get_all_agents_monitoring(search="healthy")
    check(
        "Suche nach 'healthy' findet agent1",
        any(a["name"] == "m22-healthy-agent" for a in search_result)
    )
    search_none = get_all_agents_monitoring(search="nonexistent")
    check("Suche nach 'nonexistent' = leer", len(search_none) == 0)

    # Einzelner Agent via ID
    single = get_single_agent_monitoring(_agent1_id)
    check("single agent monitoring nicht None", single is not None)
    check("single agent monitoring korrekte ID", single["id"] == _agent1_id)

    # Nicht existierender Agent
    missing = get_single_agent_monitoring(99999)
    check("nicht existierender Agent = None", missing is None)


# ================================================================
# Test 5: Fleet Summary
# ================================================================
print("\n== Fleet Summary ==")

with app.app_context():
    from app.domain.agents.monitoring_service import get_fleet_summary

    summary = get_fleet_summary()
    check("summary hat total_agents", summary["total_agents"] >= 2, f"got {summary['total_agents']}")
    check("summary hat healthy_agents", "healthy_agents" in summary)
    check("summary hat stale_agents", "stale_agents" in summary)
    check("summary hat total_instances", summary["total_instances"] >= 2, f"got {summary['total_instances']}")
    check("summary hat total_memory_mb", summary["total_memory_mb"] > 0, f"got {summary['total_memory_mb']}")
    check("summary hat used_memory_mb", summary["used_memory_mb"] > 0, f"got {summary['used_memory_mb']}")
    check("summary hat memory_utilization", "memory_utilization" in summary)
    check("summary hat total_disk_mb", summary["total_disk_mb"] > 0)
    check("summary hat used_disk_mb", summary["used_disk_mb"] > 0)
    check("summary hat total_cpu_percent", summary["total_cpu_percent"] > 0)
    check("summary hat used_cpu_percent", summary["used_cpu_percent"] > 0)
    check("summary hat total_endpoints", summary["total_endpoints"] >= 4, f"got {summary['total_endpoints']}")
    check("summary hat assigned_endpoints", summary["assigned_endpoints"] >= 2)

    # Zaehlungen konsistent
    check(
        "healthy + stale + degraded + unreachable = total",
        summary["healthy_agents"] + summary["stale_agents"] +
        summary["degraded_agents"] + summary["unreachable_agents"] == summary["total_agents"],
        f"{summary['healthy_agents']}+{summary['stale_agents']}+{summary['degraded_agents']}+{summary['unreachable_agents']} != {summary['total_agents']}"
    )


# ================================================================
# Test 6: Monitoring-API-Endpunkte
# ================================================================
print("\n== Monitoring-API-Endpunkte ==")

client = app.test_client()

# GET /api/admin/agents/monitoring
with app.app_context():
    resp = client.get("/api/admin/agents/monitoring")
    check("GET /agents/monitoring -> 200", resp.status_code == 200, f"got {resp.status_code}")
    data = resp.get_json()
    check("monitoring liefert Liste", isinstance(data, list))
    check("monitoring hat >= 2 Eintraege", len(data) >= 2, f"got {len(data)}")

    # Struktur pruefen
    if len(data) > 0:
        entry = data[0]
        check("entry hat id", "id" in entry)
        check("entry hat name", "name" in entry)
        check("entry hat fqdn", "fqdn" in entry)
        check("entry hat health_status", "health_status" in entry)
        check("entry hat is_stale", "is_stale" in entry)
        check("entry hat last_seen_at", "last_seen_at" in entry)
        check("entry hat capacity", "capacity" in entry)
        check("entry hat utilization", "utilization" in entry)
        check("entry hat instance_count", "instance_count" in entry)
        check("entry hat endpoint_summary", "endpoint_summary" in entry)

# Filter: health=healthy
with app.app_context():
    resp = client.get("/api/admin/agents/monitoring?health=healthy")
    check("GET ?health=healthy -> 200", resp.status_code == 200)
    data = resp.get_json()
    check(
        "health=healthy: alle = healthy",
        all(e["health_status"] == "healthy" for e in data),
        f"health values: {[e['health_status'] for e in data]}"
    )

# Filter: health=stale
with app.app_context():
    resp = client.get("/api/admin/agents/monitoring?health=stale")
    check("GET ?health=stale -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("health=stale: mindestens 1", len(data) >= 1, f"got {len(data)}")

# Suche
with app.app_context():
    resp = client.get("/api/admin/agents/monitoring?search=healthy")
    check("GET ?search=healthy -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("search: findet mindestens 1", len(data) >= 1)

# Einzelner Agent
with app.app_context():
    resp = client.get(f"/api/admin/agents/{_agent1_id}/monitoring")
    check(f"GET /agents/{_agent1_id}/monitoring -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("single agent hat korrekte ID", data["id"] == _agent1_id)
    check("single agent hat health_status", "health_status" in data)

# Nicht existierender Agent
with app.app_context():
    resp = client.get("/api/admin/agents/99999/monitoring")
    check("GET /agents/99999/monitoring -> 404", resp.status_code == 404)


# ================================================================
# Test 7: Fleet Summary API
# ================================================================
print("\n== Fleet Summary API ==")

with app.app_context():
    resp = client.get("/api/admin/fleet/summary")
    check("GET /fleet/summary -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("summary hat total_agents", "total_agents" in data)
    check("summary hat healthy_agents", "healthy_agents" in data)
    check("summary hat stale_agents", "stale_agents" in data)
    check("summary hat degraded_agents", "degraded_agents" in data)
    check("summary hat unreachable_agents", "unreachable_agents" in data)
    check("summary hat total_instances", "total_instances" in data)
    check("summary hat total_memory_mb", "total_memory_mb" in data)
    check("summary hat used_memory_mb", "used_memory_mb" in data)
    check("summary hat memory_utilization", "memory_utilization" in data)
    check("summary hat total_disk_mb", "total_disk_mb" in data)
    check("summary hat total_cpu_percent", "total_cpu_percent" in data)
    check("summary hat total_endpoints", "total_endpoints" in data)
    check("summary hat assigned_endpoints", "assigned_endpoints" in data)

    # stale_threshold Query-Parameter
    resp2 = client.get("/api/admin/fleet/summary?stale_threshold=60")
    check("GET /fleet/summary?stale_threshold=60 -> 200", resp2.status_code == 200)
    data2 = resp2.get_json()
    # Bei threshold=60 sollte agent2 (30 Min alt) nicht mehr stale sein
    check(
        "stale_threshold=60: weniger stale Agents",
        data2["stale_agents"] < data["stale_agents"] or data2["stale_agents"] == 0,
        f"stale_agents: threshold=10 -> {data['stale_agents']}, threshold=60 -> {data2['stale_agents']}"
    )


# ================================================================
# Test 8: Bestehende Agent-Endpunkte nicht gebrochen
# ================================================================
print("\n== Regression: bestehende Agent-Endpunkte ==")

with app.app_context():
    # GET /api/admin/agents – muss weiterhin funktionieren
    resp = client.get("/api/admin/agents")
    check("GET /admin/agents -> 200 (unveraendert)", resp.status_code == 200)
    data = resp.get_json()
    check("agents ist Liste", isinstance(data, list))
    check("agents hat >= 2 Eintraege", len(data) >= 2)

    # to_dict liefert neue Felder
    if len(data) > 0:
        a = data[0]
        check("to_dict hat memory_total", "memory_total" in a)
        check("to_dict hat disk_total", "disk_total" in a)
        check("to_dict hat cpu_total", "cpu_total" in a)

    # GET /api/admin/agents/health – muss ungebrochen bleiben
    resp = client.get("/api/admin/agents/health")
    check("GET /admin/agents/health -> 200 (unveraendert)", resp.status_code == 200)
    data = resp.get_json()
    check("agents/health ist Liste", isinstance(data, list))

    # POST /api/admin/agents – Agent erstellen geht noch
    resp = client.post("/api/admin/agents", json={
        "name": "m22-regression",
        "fqdn": "regression.m22.test.dev"
    })
    check("POST /admin/agents -> 201 (unveraendert)", resp.status_code == 201)

    # Health-Detailed
    resp = client.get("/api/admin/health/detailed")
    check("GET /admin/health/detailed -> 200 (unveraendert)", resp.status_code == 200)


# ================================================================
# Test 9: Agent-Kapazitaet bei Null-Werten / Edge Cases
# ================================================================
print("\n== Edge Cases ==")

with app.app_context():
    # Agent ohne Kapazitaetswerte
    agent_zero = Agent(name="m22-zero", fqdn="zero.m22.test.dev")
    db.session.add(agent_zero)
    db.session.flush()

    check("agent_zero effective_memory = 0", agent_zero.get_effective_memory() == 0)
    check("agent_zero effective_disk = 0", agent_zero.get_effective_disk() == 0)
    check("agent_zero effective_cpu = 0", agent_zero.get_effective_cpu() == 0)

    util = agent_zero.get_utilization_summary()
    check("zero-agent utilization memory = 0.0", util["memory_utilization"] == 0.0)
    check("zero-agent utilization disk = 0.0", util["disk_utilization"] == 0.0)
    check("zero-agent utilization cpu = 0.0", util["cpu_utilization"] == 0.0)

    cap = agent_zero.get_capacity_summary()
    check("zero-agent capacity summary korrekt", cap["memory_total_mb"] == 0)
    check("zero-agent effective_memory_mb = 0", cap["effective_memory_mb"] == 0)

    db.session.rollback()


# ================================================================
# Test 10: Monitoring liefert degradierte/unknown-Zustaende korrekt
# ================================================================
print("\n== Degradierte Zustaende ==")

with app.app_context():
    # Inaktiven Agent erstellen
    agent_inact = Agent(
        name="m22-inactive",
        fqdn="inactive.m22.test.dev",
        is_active=False,
        memory_total=2048,
    )
    agent_inact.touch()
    db.session.add(agent_inact)
    db.session.commit()

    from app.domain.agents.monitoring_service import get_agent_monitoring

    entry = get_agent_monitoring(agent_inact)
    check("inaktiver Agent health_status = degraded", entry["health_status"] == "degraded")
    check("inaktiver Agent is_active = False", entry["is_active"] is False)

    # API liefert auch degradierte
    resp = client.get("/api/admin/agents/monitoring?health=degraded")
    check("GET ?health=degraded -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("degraded-Filter liefert mindestens 1", len(data) >= 1)
    check(
        "degraded-Ergebnisse alle degraded",
        all(e["health_status"] == "degraded" for e in data)
    )


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*60}")
print(f"M22 Fleet Monitoring Tests: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
