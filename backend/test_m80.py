"""M80 – Mehrere Endpoints pro Instanz (zuweisen, entfernen, primaer wechseln), Endpoint bei Instance-Anlage."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
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


app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    owner = User(username="own", email="own@t.local")
    other = User(username="oth", email="oth@t.local")
    for u in (admin, owner, other):
        u.set_password("test1234")
    bp = Blueprint(name="vrising", docker_image="img", startup_command="run")
    a1 = Agent(name="n1", fqdn="n1.t.local", memory_total=8192, disk_total=100000, cpu_total=800)
    a2 = Agent(name="n2", fqdn="n2.t.local", memory_total=8192, disk_total=100000, cpu_total=800)
    db.session.add_all([admin, owner, other, bp, a1, a2])
    db.session.commit()
    ids = dict(admin=admin.id, owner=owner.id, bp=bp.id, a1=a1.id, a2=a2.id)
c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["owner"])}


def mk_endpoints(agent_id, start, n, ip="0.0.0.0"):
    r = c.post(f"/api/admin/agents/{agent_id}/endpoints/bulk", json={"ip": ip, "port_start": start, "port_end": start + n - 1}, headers=AH)
    assert r.status_code == 201, r.get_data(as_text=True)
    return [e["id"] for e in r.json["endpoints"]]


E1 = mk_endpoints(ids["a1"], 9876, 6)     # 9876 .. 9881 auf Agent 1
E2 = mk_endpoints(ids["a2"], 9876, 2)     # Agent 2


def create(name, agent="a1", **extra):
    return c.post("/api/admin/instances", json={"name": name, "owner_id": ids["owner"], "blueprint_id": ids["bp"], "agent_id": ids[agent],
                                                 "memory": 512, "disk": 1000, "cpu": 50, **extra}, headers=AH)


def env_and_alloc(uuid):
    with app.app_context():
        cfg = build_server_config(Instance.query.filter_by(uuid=uuid).first())
    return cfg["environment"], cfg["allocations"]


def ep_row(eid):
    with app.app_context():
        e = db.session.get(Endpoint, eid)
        return None if e is None else (e.instance_id, e.agent_id)


def instance_id(uuid):
    with app.app_context():
        return Instance.query.filter_by(uuid=uuid).first().id


print("POST /api/admin/instances mit endpoint_id (Punkt 2)")
r = create("vr1", endpoint_id=E1[2])
check("201", r.status_code == 201, r.get_data(as_text=True)[:200])
check("primary_endpoint_id = uebergebener Endpoint", r.json["primary_endpoint_id"] == E1[2], str(r.json["primary_endpoint_id"]))
check("connection.port ist der Port des Endpoints (9878)", r.json["connection"]["port"] == 9878 and r.json["connection"]["address"] == "n1.t.local:9878", str(r.json["connection"]))
check("kein Alias-Feld endpoint_id in der Antwort", "endpoint_id" not in r.json)
VR = r.json
check("endpoints.instance_id ist gesetzt", ep_row(E1[2]) == (VR["id"], ids["a1"]), str(ep_row(E1[2])))
check("endpoints enthaelt genau den einen primaeren Endpoint", VR["endpoints"] == [{"id": E1[2], "ip": "0.0.0.0", "port": 9878, "is_primary": True}], str(VR["endpoints"]))
r = create("vr0")
check("ohne endpoint_id: niedrigster freier Port, primary_endpoint_id gesetzt", r.status_code == 201 and r.json["connection"]["port"] == 9876 and r.json["primary_endpoint_id"] == E1[0], str(r.json["connection"]))
AUTO = r.json
r = create("vr-bad", endpoint_id=E2[0])
check("Endpoint eines anderen Agents bei der Anlage -> 400", r.status_code == 400, str(r.status_code))
r = create("vr-bad2", endpoint_id=E1[2])
check("bereits belegter Endpoint bei der Anlage -> 409", r.status_code == 409, str(r.status_code))

U = VR["uuid"]
print("Endpoint zuweisen")
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E1[3]}, headers=AH)
check("201 mit Instanz-Dict", r.status_code == 201 and r.json["uuid"] == U, r.get_data(as_text=True)[:200])
check("endpoints: primaerer zuerst, dann nach Port",
      [(e["port"], e["is_primary"]) for e in r.json["endpoints"]] == [(9878, True), (9879, False)], str(r.json["endpoints"]))
check("primary_endpoint_id und connection bleiben", r.json["primary_endpoint_id"] == E1[2] and r.json["connection"]["port"] == 9878)
check("Antwort: Wings-Sync und Neustart-Hinweis", r.json["sync"]["success"] is True and r.json["restart_required"] is True, str(r.json.get("sync")))
check("endpoints.instance_id gesetzt", ep_row(E1[3])[0] == VR["id"])
with app.app_context():
    synced = ActivityLog.query.filter_by(event="instance:synced", subject_id=VR["id"]).count()
    added = ActivityLog.query.filter_by(event="instance:endpoint_added", subject_id=VR["id"]).count()
check("Sync zu Wings wurde ausgeloest (instance:synced) und das Zuweisen protokolliert", synced >= 1 and added == 1, f"{synced} {added}")
env, alloc = env_and_alloc(U)
check("Config-Builder: beide Ports in allocations.mappings", sorted(alloc["mappings"]["0.0.0.0"]) == [9878, 9879], str(alloc))
check("Config-Builder: default = primaerer Port, SERVER_PORT = primaerer Port", alloc["default"]["port"] == 9878 and env["SERVER_PORT"] == "9878")

print("Zuweisen: Fehlerfaelle")
check("ohne Body -> 400", c.post(f"/api/admin/instances/{U}/endpoints", headers=AH).status_code == 400)
check("ohne endpoint_id -> 400", c.post(f"/api/admin/instances/{U}/endpoints", json={}, headers=AH).status_code == 400)
check("endpoint_id Text -> 400", c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": "13"}, headers=AH).status_code == 400)
check("endpoint_id true -> 400", c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": True}, headers=AH).status_code == 400)
check("endpoint_id null -> 400", c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": None}, headers=AH).status_code == 400)
check("unbekannter Endpoint -> 404", c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": 99999}, headers=AH).status_code == 404)
check("unbekannte Instance -> 404", c.post("/api/admin/instances/gibt-es-nicht/endpoints", json={"endpoint_id": E1[4]}, headers=AH).status_code == 404)
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E2[0]}, headers=AH)
check("Endpoint eines anderen Agents -> 409", r.status_code == 409 and ep_row(E2[0])[0] is None, r.get_data(as_text=True))
with app.app_context():
    db.session.get(Endpoint, E1[4]).is_locked = True
    db.session.commit()
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E1[4]}, headers=AH)
check("gesperrter Endpoint -> 409", r.status_code == 409 and ep_row(E1[4])[0] is None, r.get_data(as_text=True))
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": AUTO["primary_endpoint_id"]}, headers=AH)
check("Endpoint einer anderen Instanz -> 409 (bleibt dort)", r.status_code == 409 and ep_row(AUTO["primary_endpoint_id"])[0] == AUTO["id"], r.get_data(as_text=True))
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E1[3]}, headers=AH)
check("schon dieser Instanz zugeordnet -> 409", r.status_code == 409)
with app.app_context():
    inst = Instance.query.filter_by(uuid=U).first()
    inst.status = "transferring"
    db.session.commit()
check("waehrend eines Transfers -> 409", c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E1[5]}, headers=AH).status_code == 409 and ep_row(E1[5])[0] is None)
with app.app_context():
    inst = Instance.query.filter_by(uuid=U).first()
    inst.status = None
    db.session.commit()

print("Primaeren Endpoint wechseln")
r = c.patch(f"/api/admin/instances/{U}/endpoints/{E1[5]}/primary", headers=AH)
check("nicht zugeordneter Endpoint -> 404", r.status_code == 404, r.get_data(as_text=True))
r = c.patch(f"/api/admin/instances/{U}/endpoints/{AUTO['primary_endpoint_id']}/primary", headers=AH)
check("Endpoint einer anderen Instanz -> 404", r.status_code == 404)
check("unbekannte Instance -> 404", c.patch(f"/api/admin/instances/gibt-es-nicht/endpoints/{E1[3]}/primary", headers=AH).status_code == 404)
r = c.patch(f"/api/admin/instances/{U}/endpoints/{E1[3]}/primary", headers=AH)
check("200: Endpoint 9879 ist primaer", r.status_code == 200 and r.json["primary_endpoint_id"] == E1[3], r.get_data(as_text=True)[:200])
check("connection wechselt auf 9879", r.json["connection"]["port"] == 9879 and r.json["connection"]["address"] == "n1.t.local:9879", str(r.json["connection"]))
check("endpoints: neuer primaerer zuerst", [(e["port"], e["is_primary"]) for e in r.json["endpoints"]] == [(9879, True), (9878, False)], str(r.json["endpoints"]))
check("Sync und Neustart-Hinweis", r.json["sync"]["success"] is True and r.json["restart_required"] is True)
env, alloc = env_and_alloc(U)
check("SERVER_PORT und default.port wechseln, beide Ports bleiben gemappt", env["SERVER_PORT"] == "9879" and alloc["default"]["port"] == 9879 and sorted(alloc["mappings"]["0.0.0.0"]) == [9878, 9879])
r = c.patch(f"/api/admin/instances/{U}/endpoints/{E1[3]}/primary", headers=AH)
check("erneut dieselbe Auswahl: 200 ohne Aenderung, kein Sync/Neustart", r.status_code == 200 and r.json["sync"] is None and r.json["restart_required"] is False)

print("Endpoint entfernen")
r = c.delete(f"/api/admin/instances/{U}/endpoints/{E1[3]}", headers=AH)
check("primaerer Endpoint -> 409", r.status_code == 409 and ep_row(E1[3])[0] == VR["id"], r.get_data(as_text=True))
check("nicht zugeordneter Endpoint -> 404", c.delete(f"/api/admin/instances/{U}/endpoints/{E1[5]}", headers=AH).status_code == 404)
check("Endpoint einer anderen Instanz -> 404 (bleibt dort)", c.delete(f"/api/admin/instances/{U}/endpoints/{AUTO['primary_endpoint_id']}", headers=AH).status_code == 404
      and ep_row(AUTO["primary_endpoint_id"])[0] == AUTO["id"])
check("unbekannte Instance -> 404", c.delete(f"/api/admin/instances/gibt-es-nicht/endpoints/{E1[2]}", headers=AH).status_code == 404)
r = c.delete(f"/api/admin/instances/{U}/endpoints/{E1[2]}", headers=AH)
check("sekundaerer Endpoint 9878: 200, Instanz-Dict mit nur noch einem Endpoint", r.status_code == 200 and [e["port"] for e in r.json["endpoints"]] == [9879], r.get_data(as_text=True)[:200])
check("Endpoint ist frei (instance_id NULL), aber nicht geloescht", ep_row(E1[2]) == (None, ids["a1"]), str(ep_row(E1[2])))
check("Sync und Neustart-Hinweis", r.json["sync"]["success"] is True and r.json["restart_required"] is True)
env, alloc = env_and_alloc(U)
check("Mappings nur noch 9879", alloc["mappings"]["0.0.0.0"] == [9879], str(alloc["mappings"]))
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": E1[2]}, headers=AH)
check("freigegebener Endpoint kann wieder zugewiesen werden", r.status_code == 201)
with app.app_context():
    removed = ActivityLog.query.filter_by(event="instance:endpoint_removed", subject_id=VR["id"]).count()
    prim = ActivityLog.query.filter_by(event="instance:endpoint_primary", subject_id=VR["id"]).count()
check("Entfernen und Primaer-Wechsel sind protokolliert", removed == 1 and prim == 1, f"{removed} {prim}")

print("Mehrere Ports ueber verschiedene IPs und Anzeige")
ipeps = mk_endpoints(ids["a1"], 30000, 1, ip="10.0.0.5")
r = c.post(f"/api/admin/instances/{U}/endpoints", json={"endpoint_id": ipeps[0]}, headers=AH)
env, alloc = env_and_alloc(U)
check("Mappings je IP", r.status_code == 201 and sorted(alloc["mappings"]["10.0.0.5"]) == [30000] and sorted(alloc["mappings"]["0.0.0.0"]) == [9878, 9879], str(alloc["mappings"]))
c.delete(f"/api/admin/instances/{U}/endpoints/{ipeps[0]}", headers=AH)

print("Client- und Admin-Listen enthalten endpoints")
one = c.get(f"/api/client/instances/{U}", headers=OH)
check("GET /api/client/instances/<uuid>: endpoints", one.status_code == 200 and [e["port"] for e in one.json["endpoints"]] == [9879, 9878], str(one.json.get("endpoints")))
lst = c.get("/api/client/instances", headers=OH).json
check("GET /api/client/instances (Liste): endpoints je Instance", all("endpoints" in i for i in lst) and next(i for i in lst if i["uuid"] == U)["endpoints"][0]["is_primary"] is True)
adm = c.get("/api/admin/instances", headers=AH).json
check("GET /api/admin/instances (Liste): endpoints je Instance", all("endpoints" in i for i in adm) and len(next(i for i in adm if i["uuid"] == U)["endpoints"]) == 2)

print("Instanz loeschen gibt alle Endpoints frei")
d = c.delete(f"/api/admin/instances/{U}", headers=AH)
check("Instanz geloescht", d.status_code == 200, d.get_data(as_text=True)[:200])
check("beide Endpoints sind frei und existieren noch", ep_row(E1[2]) == (None, ids["a1"]) and ep_row(E1[3]) == (None, ids["a1"]), f"{ep_row(E1[2])} {ep_row(E1[3])}")

print("Rechte")
app.config["ADMIN_GUARD_ENABLED"] = True
U2 = AUTO["uuid"]
check("POST ohne Anmeldung -> 401", c.post(f"/api/admin/instances/{U2}/endpoints", json={"endpoint_id": E1[5]}).status_code == 401)
check("POST als Kunde -> 403", c.post(f"/api/admin/instances/{U2}/endpoints", json={"endpoint_id": E1[5]}, headers=OH).status_code == 403)
check("DELETE als Kunde -> 403", c.delete(f"/api/admin/instances/{U2}/endpoints/{AUTO['primary_endpoint_id']}", headers=OH).status_code == 403)
check("PATCH als Kunde -> 403", c.patch(f"/api/admin/instances/{U2}/endpoints/{AUTO['primary_endpoint_id']}/primary", headers=OH).status_code == 403)
check("Admin darf weiterhin", c.post(f"/api/admin/instances/{U2}/endpoints", json={"endpoint_id": E1[5]}, headers=AH).status_code == 201)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
