"""M41 – Wings-Erreichbarkeit (Monitoring, Preflight) und Endpoint-Pflicht bei Instanz-Erstellung."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents import reachability
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.system.upgrade_service import run_preflight_check
from app.domain.users.models import User
from app.infrastructure.runner.wings_http import WingsResponse
from app.infrastructure.runner.config_builder import build_server_config

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK  {label}")
    else:
        failed += 1
        print(f"  FAIL {label}" + (f" – {detail}" if detail else ""))


# ── Fake fuer den Wings-HTTP-Client ─────────────────────
calls = []
behavior = {}  # agent name -> WingsResponse


class FakeWingsClient:
    def __init__(self, timeout=None, debug=False):
        self.timeout = timeout

    def get(self, agent, path, params=None):
        calls.append((agent.name, path, agent.daemon_token, self.timeout))
        return behavior[agent.name]


reachability.WingsHttpClient = FakeWingsClient

app = create_app("testing")
with app.app_context():
    db.create_all()
    owner = User(username="own", email="own@t.local")
    owner.set_password("test1234")
    up = Agent(name="up", fqdn="up.test")
    down = Agent(name="down", fqdn="down.test")
    maint = Agent(name="maint", fqdn="maint.test")
    inactive = Agent(name="inactive", fqdn="inactive.test", is_active=False)
    for a in (up, down, maint, inactive):
        a.generate_daemon_credentials()
    maint.maintenance_mode = True
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([owner, up, down, maint, inactive, bp])
    db.session.commit()
    ids = {a.name: a.id for a in (up, down, maint, inactive)}
    owner_id, bp_id = owner.id, bp.id

c = app.test_client()

print("Stub-Adapter")
reachability.clear_cache()
r = c.get(f"/api/admin/agents/{ids['up']}/monitoring")
check("Detail: daemon_reachable=true, version=stub",
      r.status_code == 200 and r.json["daemon_reachable"] is True and r.json["daemon_version"] == "stub", r.get_data(as_text=True)[:200])
check("Stub: kein HTTP-Call", not calls)
with app.app_context():
    res = run_preflight_check()
check("Preflight: agents_reachable ok (Stub)", res["checks"].get("agents_reachable") == "ok", str(res["checks"]))

print("Wings-Adapter")
app.config["_RUNNER_ADAPTER_NAME"] = "wings"
behavior.update({
    "up": WingsResponse(success=True, status_code=200, data={"version": "1.11.13", "os": "linux"}),
    "down": WingsResponse(success=False, status_code=None, data=None, error="Wings nicht erreichbar"),
    "maint": WingsResponse(success=False, status_code=None, data=None, error="Timeout bei Wings-Verbindung"),
    "inactive": WingsResponse(success=False, status_code=None, data=None, error="x"),
})
reachability.clear_cache()
calls.clear()
r = c.get(f"/api/admin/agents/{ids['up']}/monitoring")
check("up: reachable + Version", r.json["daemon_reachable"] is True and r.json["daemon_version"] == "1.11.13")
check("Request an /api/system mit Bearer-Token-Agent und 3s Timeout",
      len(calls) == 1 and calls[0][1] == "/api/system" and calls[0][3] == (3, 3) and calls[0][2])
r = c.get(f"/api/admin/agents/{ids['down']}/monitoring")
check("down: reachable=false mit Fehlertext",
      r.json["daemon_reachable"] is False and r.json["daemon_version"] is None and "nicht erreichbar" in r.json["daemon_error"])

calls.clear()
c.get(f"/api/admin/agents/{ids['up']}/monitoring")
c.get(f"/api/admin/agents/{ids['down']}/monitoring")
check("Cache: zweiter Aufruf ohne neuen Request (auch bei Fehlern)", not calls, str(calls))

r = c.get("/api/admin/agents/monitoring")
by = {a["name"]: a for a in r.json}
check("Liste: alle Agents mit daemon_reachable", r.status_code == 200 and all("daemon_reachable" in a for a in by.values()))
check("Liste: up true, down false", by["up"]["daemon_reachable"] is True and by["down"]["daemon_reachable"] is False)
check("Liste: nur uncachte Agents angefragt", {c_[0] for c_ in calls} == {"maint", "inactive"}, str(calls))

# Cache laeuft ab
calls.clear()
for key, (ts, val) in list(reachability._cache.items()):
    reachability._cache[key] = (ts - reachability.CACHE_TTL_SECONDS - 1, val)
c.get(f"/api/admin/agents/{ids['up']}/monitoring")
check("abgelaufener Cache -> neuer Request", len(calls) == 1)

# Token geaendert -> Cache entwertet
calls.clear()
with app.app_context():
    a = db.session.get(Agent, ids["up"])
    a.generate_daemon_credentials()
    db.session.commit()
c.get(f"/api/admin/agents/{ids['up']}/monitoring")
check("neue Credentials -> Cache entwertet", len(calls) == 1)

print("Preflight")
reachability.clear_cache()
with app.app_context():
    res = run_preflight_check()
check("Preflight: agents_reachable = warning", res["checks"].get("agents_reachable") == "warning", str(res["checks"]))
issue = [i for i in res["issues"] if "nicht erreichbar" in i]
check("Issue nennt 'down', nicht Wartungs-/inaktive Agents",
      issue and "down" in issue[0] and "maint" not in issue[0] and "inactive" not in issue[0], str(issue))
warn_res = res
behavior["down"] = WingsResponse(success=True, status_code=200, data={"version": "1.11.13"})
reachability.clear_cache()
with app.app_context():
    res = run_preflight_check()
check("alle erreichbar -> ok", res["checks"].get("agents_reachable") == "ok")
# Der Gesamtstatus der Test-DB ist wegen fehlender Migrationen "pending_upgrade"; entscheidend ist,
# dass ein nicht erreichbarer Agent daran nichts aendert (nur Warnung, kein Fehler)
check("Preflight blockt nicht: compatible/Status wie bei erreichbaren Agents",
      warn_res["compatible"] == res["compatible"] and warn_res["overall_status"] == res["overall_status"]
      and warn_res["overall_status"] != "error", f"{warn_res['overall_status']} vs {res['overall_status']}")
app.config["_RUNNER_ADAPTER_NAME"] = "stub"

print("Instanz-Erstellung ohne freien Endpoint")
body = {"name": "i1", "owner_id": owner_id, "agent_id": ids["up"], "blueprint_id": bp_id}
r = c.post("/api/admin/instances", json=body)
check("kein Endpoint vorhanden -> 409", r.status_code == 409, f"{r.status_code} {r.get_data(as_text=True)[:150]}")
with app.app_context():
    check("keine halbe Instanz gespeichert", Instance.query.count() == 0)
    db.session.add(Endpoint(agent_id=ids["up"], ip="0.0.0.0", port=25565, is_locked=True))
    db.session.commit()
r = c.post("/api/admin/instances", json=body)
check("nur gesperrter Endpoint -> 409", r.status_code == 409)
with app.app_context():
    db.session.add(Endpoint(agent_id=ids["up"], ip="0.0.0.0", port=25566))
    db.session.commit()
r = c.post("/api/admin/instances", json=body)
check("freier Endpoint -> 201", r.status_code == 201, r.get_data(as_text=True)[:150])
r = c.post("/api/admin/instances", json={**body, "name": "i2"})
check("Endpoint jetzt belegt -> 409", r.status_code == 409)
r = c.post("/api/admin/instances", json={**body, "name": "i3", "agent_id": ids["down"]})
check("anderer Agent ohne Endpoints -> 409", r.status_code == 409)

print("Config-Builder ohne Endpoint")


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


handler = ListHandler()
cb_logger = logging.getLogger("app.infrastructure.runner.config_builder")
cb_logger.addHandler(handler)
with app.app_context():
    inst = Instance(name="ohne", owner_id=owner_id, agent_id=ids["up"], blueprint_id=bp_id)
    db.session.add(inst)
    db.session.commit()
    cfg = build_server_config(inst)
cb_logger.removeHandler(handler)
check("allocations.default.port = 0 (kein 25565)", cfg["allocations"]["default"]["port"] == 0, str(cfg["allocations"]["default"]))
check("environment.SERVER_PORT = '0'", cfg["environment"]["SERVER_PORT"] == "0")
check("mappings leer statt Port 0", cfg["allocations"]["mappings"] == {}, str(cfg["allocations"]["mappings"]))
check("Log-Warnung", any(r.levelno == logging.WARNING and "Endpoint" in r.getMessage() for r in handler.records))
with app.app_context():
    inst = Instance.query.filter_by(name="i1").first()
    cfg = build_server_config(inst)
check("mit Endpoint unveraendert (25566)", cfg["allocations"]["default"]["port"] == 25566
      and cfg["environment"]["SERVER_PORT"] == "25566" and cfg["allocations"]["mappings"] == {"0.0.0.0": [25566]})

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
