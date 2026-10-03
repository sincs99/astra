"""M51 – Stub-Runner schliesst die Installation synchron ab (Wings bleibt asynchron per Callback)."""

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
from app.domain.instances.service import get_runner, set_runner
from app.domain.users.models import User
from app.infrastructure.runner.protocol import RunnerResponse
from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter
from app.infrastructure.runner.wings_http import WingsResponse
from test_helpers import report_install

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
    own = User(username="own", email="own@t.local")
    for u in (admin, own):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test")
    agent2 = Agent(name="n2", fqdn="n2.test")
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([admin, own, agent, agent2, bp])
    db.session.commit()
    for i in range(12):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
        db.session.add(Endpoint(agent_id=agent2.id, ip="0.0.0.0", port=26565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, own=own.id, agent=agent.id, agent2=agent2.id, bp=bp.id)
    default_runner = get_runner()

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["own"])}
n = [0]


def create(**kw):
    n[0] += 1
    body = {"name": f"i{n[0]}", "owner_id": ids["own"], "agent_id": ids["agent"], "blueprint_id": ids["bp"], **kw}
    r = c.post("/api/admin/instances", json=body, headers=AH)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.json


def events(instance_id, name):
    with app.app_context():
        return ActivityLog.query.filter_by(subject_id=instance_id, event=name).count()


class AsyncRunner(StubRunnerAdapter):
    """Wie Wings: nimmt den Auftrag an, Ergebnis kommt spaeter per Callback."""

    def create_instance(self, agent, instance):
        return RunnerResponse(success=True, message="angenommen")


print("Stub: Erstellung ist sofort fertig")
check("Standard-Runner in den Tests ist der Stub", isinstance(default_runner, StubRunnerAdapter))
inst = create()
check("Antwort: status null (ready), installed_at gesetzt", inst["status"] is None and inst["installed_at"] is not None, str(inst["status"]))
check("Event instance:install_completed genau einmal", events(inst["id"], "instance:install_completed") == 1)
check("kein Fehler-Event", events(inst["id"], "instance:install_failed") == 0)
installed_at = inst["installed_at"]
with app.app_context():
    r = report_install(c, inst["uuid"], True)
check("spaeterer Install-Callback ist idempotent (204)", r.status_code == 204)
now = c.get("/api/admin/instances", headers=AH).json
mine = [i for i in now if i["uuid"] == inst["uuid"]][0]
check("installed_at bleibt unveraendert, kein zweites Event", mine["installed_at"] == installed_at and events(inst["id"], "instance:install_completed") == 1)

print("Stub: Bestellung liefert sofort einen fertigen Server")
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50, "price_cents": 100}, headers=AH)
pid = r.json["id"]
ou = c.post("/api/client/orders", json={"product_id": pid, "name": "ord"}, headers=OH).json["uuid"]
r = c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": "x"}, headers=AH)
check("Bestellung aktiv, Instance sofort ready", r.status_code == 200 and r.json["status"] == "active" and r.json["instance_status"] is None, str(r.json.get("instance_status")))

print("Stub: Reinstall ist sofort fertig")
r = c.post(f"/api/client/instances/{inst['uuid']}/reinstall", headers=OH)
check("Reinstall -> 200, Status ready", r.status_code == 200 and r.json["status"] is None, r.get_data(as_text=True))
check("Events: Reinstall gestartet und abgeschlossen",
      events(inst["id"], "instance:reinstall_started") == 1 and events(inst["id"], "instance:reinstall_completed") == 1)
mine = [i for i in c.get("/api/admin/instances", headers=AH).json if i["uuid"] == inst["uuid"]][0]
check("installed_at bleibt vom ersten Install", mine["installed_at"] == installed_at)
r = c.post(f"/api/client/instances/{inst['uuid']}/reinstall", headers=OH)
check("erneuter Reinstall funktioniert (kein haengender Status)", r.status_code == 200)

print("Stub: Transfer ist sofort fertig")
r = c.post(f"/api/admin/instances/{inst['uuid']}/transfer", json={"target_agent_id": ids["agent2"]}, headers=AH)
check("Transfer -> 200, Status ready, neuer Agent", r.status_code == 200 and r.json["status"] is None and r.json["agent_id"] == ids["agent2"], r.get_data(as_text=True)[:200])
check("Event Transfer abgeschlossen", events(inst["id"], "instance.transfer.completed") == 1)

print("Asynchroner Runner (wie Wings): bleibt bis zum Callback offen")
with app.app_context():
    set_runner(AsyncRunner())
a = create()
check("Erstellung: status provisioning, kein installed_at", a["status"] == "provisioning" and a["installed_at"] is None)
check("kein install_completed-Event vor dem Callback", events(a["id"], "instance:install_completed") == 0)
r = c.delete(f"/api/admin/instances/{a['uuid']}", headers=AH)
check("laufende Installation kann nicht geloescht werden (409)", r.status_code == 409)
with app.app_context():
    check("Install-Callback schliesst ab", report_install(c, a["uuid"], True).status_code == 204)
done = [i for i in c.get("/api/admin/instances", headers=AH).json if i["uuid"] == a["uuid"]][0]
check("danach ready mit installed_at", done["status"] is None and done["installed_at"] is not None)
r = c.post(f"/api/client/instances/{a['uuid']}/reinstall", headers=OH)
check("Reinstall: status reinstalling", r.status_code == 200 and r.json["status"] == "reinstalling")
with app.app_context():
    report_install(c, a["uuid"], True)
check("Reinstall-Callback schliesst ab", [i for i in c.get("/api/admin/instances", headers=AH).json if i["uuid"] == a["uuid"]][0]["status"] is None)

print("Nur genau completed=True zaehlt")
for label, data in (("completed=False", {"completed": False}), ("completed='true' (String)", {"completed": "true"}),
                    ("completed=1", {"completed": 1}), ("data=None", None), ("anderes Feld", {"done": True})):
    class R(StubRunnerAdapter):
        def create_instance(self, agent, instance, _d=data):
            return RunnerResponse(success=True, message="ok", data=_d)
    with app.app_context():
        set_runner(R())
    x = create()
    check(f"{label}: bleibt provisioning", x["status"] == "provisioning", str(x["status"]))
class Failing(StubRunnerAdapter):
    def create_instance(self, agent, instance):
        return RunnerResponse(success=False, message="kaputt", data={"completed": True})
with app.app_context():
    set_runner(Failing())
x = create()
check("Fehler mit completed=True: provision_failed (Fehler gewinnt)", x["status"] == "provision_failed")
class Raising(StubRunnerAdapter):
    def create_instance(self, agent, instance):
        raise RuntimeError("Node weg")
with app.app_context():
    set_runner(Raising())
x = create()
check("Runner-Exception: provision_failed", x["status"] == "provision_failed")

print("Wings-Adapter liefert nie completed")


class FakeHttp:
    def __init__(self, data):
        self.data = data

    def post(self, agent, path, payload=None, params=None):
        return WingsResponse(success=True, status_code=202, data=self.data)


wings = WingsRunnerAdapter()
with app.app_context():
    ag = db.session.get(Agent, ids["agent"])
    inst_obj = Instance.query.filter_by(uuid=a["uuid"]).first()
    for body in ({"completed": True, "uuid": "x"}, {"uuid": "x"}, None):
        wings._http = FakeHttp(body)
        resp = wings.create_instance(ag, inst_obj)
        check(f"Wings-Antwort {body}: kein 'completed' im Ergebnis", resp.success and not (isinstance(resp.data, dict) and "completed" in resp.data), str(resp.data))
    wings._http = FakeHttp({"completed": True})
    set_runner(wings)
# ueber den Service: auch eine boesartige/versehentliche Wings-Antwort schliesst nichts ab
x = create()
check("Service mit Wings-Adapter und completed=True in der Antwort: bleibt provisioning", x["status"] == "provisioning", str(x["status"]))
with app.app_context():
    set_runner(default_runner)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
