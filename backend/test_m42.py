"""M42 – Kapazitaetspruefung und automatische Platzierung."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.agents.placement import capacity_problem, pick_agent, used_resources
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User

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


app = create_app("testing")
with app.app_context():
    db.create_all()
    owner = User(username="own", email="own@t.local")
    owner.set_password("test1234")
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    # small: 2048 MB / 10000 MB / 200 %, 0 % Overalloc
    small = Agent(name="small", fqdn="small.test", memory_total=2048, disk_total=10000, cpu_total=200)
    # big: 8192 MB mit 25 % Overalloc -> 10240 effektiv
    big = Agent(name="big", fqdn="big.test", memory_total=8192, memory_overalloc=25, disk_total=100000, cpu_total=800)
    # open: ohne Limits
    unl = Agent(name="open", fqdn="open.test")
    maint = Agent(name="maint", fqdn="maint.test", memory_total=65536, disk_total=10**6, cpu_total=1600)
    maint.maintenance_mode = True
    inactive = Agent(name="inactive", fqdn="inactive.test", is_active=False, memory_total=65536)
    noep = Agent(name="noep", fqdn="noep.test", memory_total=65536, disk_total=10**6, cpu_total=1600)
    db.session.add_all([owner, bp, small, big, unl, maint, inactive, noep])
    db.session.commit()
    ids = {a.name: a.id for a in (small, big, unl, maint, inactive, noep)}
    for name in ("small", "big", "open", "maint", "inactive"):
        for i in range(8):
            db.session.add(Endpoint(agent_id=ids[name], ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    owner_id, bp_id = owner.id, bp.id

c = app.test_client()


def create(**kw):
    body = {"name": kw.pop("name", "i"), "owner_id": owner_id, "blueprint_id": bp_id, **kw}
    return c.post("/api/admin/instances", json=body)


print("Kapazitaetspruefung (expliziter Agent)")
r = create(name="a", agent_id=ids["small"], memory=1024, disk=2000, cpu=100)
check("passt -> 201", r.status_code == 201, r.get_data(as_text=True)[:150])
r = create(name="b", agent_id=ids["small"], memory=1024, disk=2000, cpu=100)
check("exakt voll (2048/2048 MB) -> 201", r.status_code == 201)
r = create(name="c", agent_id=ids["small"], memory=1, disk=1, cpu=1)
check("RAM voll -> 409 mit Text", r.status_code == 409 and "RAM" in r.json["error"] and "frei" in r.json["error"], r.get_data(as_text=True))
with app.app_context():
    check("abgelehnte Instanz nicht gespeichert", Instance.query.filter_by(name="c").count() == 0)
    check("Endpoint der abgelehnten bleibt frei",
          Endpoint.query.filter_by(agent_id=ids["small"], instance_id=None).count() == 6)
r = create(name="d", agent_id=ids["big"], memory=4096, disk=1000, cpu=100)
r = create(name="e", agent_id=ids["big"], memory=6144, disk=1000, cpu=100)
check("Overalloc zaehlt: 4096+6144 = 10240 effektiv -> 201", r.status_code == 201, r.get_data(as_text=True)[:150])
r = create(name="f", agent_id=ids["big"], memory=1, disk=1, cpu=1)
check("effektiv voll -> 409", r.status_code == 409)
r2 = create(name="h", agent_id=ids["big"], memory=0, disk=999999, cpu=1)
check("Disk-Limit pro Dimension -> 409", r2.status_code == 409 and "Disk" in r2.json["error"], r2.get_data(as_text=True))
r = create(name="u1", agent_id=ids["open"], memory=999999, disk=999999, cpu=9999)
check("Agent ohne Limits (total=0) -> unbegrenzt, 201", r.status_code == 201)
r = create(name="x", agent_id=ids["noep"], memory=1)
check("Kapazitaet ok, aber kein Endpoint -> weiter 409", r.status_code == 409 and "Endpoint" in r.json["error"])

print("capacity_problem / used_resources")
with app.app_context():
    u = used_resources(ids["big"])
    check("used_resources summiert", u["memory"] == 4096 + 6144 and u["instances"] == 2, str(u))
    check("capacity_problem None bei Platz", capacity_problem(db.session.get(Agent, ids["open"]), 10, 10, 10) is None)

print("Automatische Platzierung")
with app.app_context():
    for inst in Instance.query.all():
        ep = Endpoint.query.filter_by(instance_id=inst.id).first()
        if ep:
            ep.instance_id = None
        db.session.delete(inst)
    db.session.commit()
    # small 25 % belegt, big 0 %, open ohne Limits (Last 0)
    db.session.add(Instance(name="vor", owner_id=owner_id, agent_id=ids["small"], blueprint_id=bp_id, memory=512, disk=100, cpu=50))
    db.session.commit()
    chosen = pick_agent(1024, 1000, 100)
check("pick_agent: Agent ohne Limits hat Last 0 -> gewinnt", chosen is not None and chosen.name == "open", getattr(chosen, "name", None))
r = create(name="auto1", agent_id=None, memory=1024, disk=1000, cpu=100)
check("agent_id=null -> 201, Agent gesetzt", r.status_code == 201 and r.json["agent_id"] in ids.values(), r.get_data(as_text=True)[:150])
r = c.post("/api/admin/instances", json={"name": "auto2", "owner_id": owner_id, "blueprint_id": bp_id, "memory": 512})
check("agent_id fehlt komplett -> ebenfalls Auto-Platzierung", r.status_code == 201, r.get_data(as_text=True)[:150])
placed = {r.json["agent_id"]}
check("Auto-Platzierung nie auf Wartung/inaktiv/ohne Endpoint",
      not (placed & {ids["maint"], ids["inactive"], ids["noep"]}), str(placed))

with app.app_context():
    # open-Agent aus dem Rennen nehmen: Last-Vergleich small (25 %) vs big (0 %)
    db.session.get(Agent, ids["open"]).is_active = False
    db.session.commit()
    chosen = pick_agent(1024, 1000, 100)
check("geringste Auslastung nach Platzierung: big statt small", chosen.name == "big", chosen.name)
with app.app_context():
    db.session.add(Instance(name="fuell", owner_id=owner_id, agent_id=ids["big"], blueprint_id=bp_id, memory=9000, disk=100, cpu=50))
    db.session.commit()
    chosen = pick_agent(1024, 1000, 100)
check("big fast voll -> small gewinnt", chosen.name == "small", getattr(chosen, "name", None))
with app.app_context():
    check("nichts passt -> None", pick_agent(99999, 1, 1) is None)
r = create(name="zuviel", agent_id=None, memory=99999)
check("nichts passt -> 409", r.status_code == 409 and "Kein Agent" in r.json["error"], r.get_data(as_text=True))
r = create(name="mitep", agent_id=None, endpoint_id=1)
check("endpoint_id ohne agent_id -> 400", r.status_code == 400)
with app.app_context():
    db.session.get(Agent, ids["open"]).is_active = True
    db.session.commit()

print("Transfer prueft Kapazitaet")
with app.app_context():
    inst = Instance.query.filter_by(name="fuell").first()
    inst_uuid = inst.uuid
r = c.post(f"/api/admin/instances/{inst_uuid}/transfer", json={"target_agent_id": ids["small"]})
check("Transfer auf zu kleinen Agent -> 409", r.status_code == 409 and "RAM" in r.json["error"], r.get_data(as_text=True))
r = c.post(f"/api/admin/instances/{inst_uuid}/transfer", json={"target_agent_id": ids["open"]})
check("Transfer auf Agent ohne Limit -> 200", r.status_code == 200, r.get_data(as_text=True)[:150])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
