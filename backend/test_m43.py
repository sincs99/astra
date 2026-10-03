"""M43 – Instance loeschen (Admin und Owner) inkl. Aufraeumen abhaengiger Daten."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.backups.models import Backup
from app.domain.blueprints.models import Blueprint
from app.domain.collaborators.models import Collaborator
from app.domain.databases.models import Database, DatabaseProvider
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.instances.service import delete_instance, get_runner, set_runner
from app.domain.routines.models import Action, Routine
from app.domain.users.models import User
from app.domain.webhooks.event_catalog import is_valid_webhook_event
from app.infrastructure.runner.protocol import RunnerResponse
from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

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


N_EP = 12
app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    owner = User(username="own", email="own@t.local")
    collab = User(username="col", email="col@t.local")
    other = User(username="oth", email="oth@t.local")
    for u in (admin, owner, collab, other):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test")
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    provider = DatabaseProvider(name="p", host="db.test")
    db.session.add_all([admin, owner, collab, other, agent, bp, provider])
    db.session.commit()
    for i in range(N_EP):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, owner=owner.id, collab=collab.id, other=other.id,
               agent=agent.id, bp=bp.id, provider=provider.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["owner"])}


def new_instance(name):
    r = c.post("/api/admin/instances", json={"name": name, "owner_id": ids["owner"],
                                             "agent_id": ids["agent"], "blueprint_id": ids["bp"]})
    assert r.status_code == 201, r.get_data(as_text=True)
    with app.app_context():
        inst = Instance.query.filter_by(name=name).first()
        inst.status = None  # bereit
        db.session.commit()
        return inst.id, inst.uuid


def add_children(inst_id):
    with app.app_context():
        db.session.add(Backup(instance_id=inst_id, name="bk", is_successful=True, is_locked=True))
        db.session.add(Database(instance_id=inst_id, provider_id=ids["provider"], db_name="d1", username="u1", password="x"))
        db.session.add(Collaborator(instance_id=inst_id, user_id=ids["collab"], permissions=["file.read"]))
        r = Routine(instance_id=inst_id, name="rt")
        db.session.add(r)
        db.session.flush()
        db.session.add(Action(routine_id=r.id, sequence=1, action_type="power", payload={"action": "restart"}))
        db.session.commit()


def counts(inst_id):
    with app.app_context():
        return {
            "instance": Instance.query.filter_by(id=inst_id).count(),
            "backups": Backup.query.filter_by(instance_id=inst_id).count(),
            "databases": Database.query.filter_by(instance_id=inst_id).count(),
            "collaborators": Collaborator.query.filter_by(instance_id=inst_id).count(),
            "routines": Routine.query.filter_by(instance_id=inst_id).count(),
            "actions": Action.query.count(),
            "endpoints_used": Endpoint.query.filter_by(instance_id=inst_id).count(),
        }


check("Event instance:deleted ist ein gueltiges Webhook-Event", is_valid_webhook_event("instance:deleted"))

print("Admin loescht")
iid, uuid = new_instance("adm-del")
add_children(iid)
before = counts(iid)
check("Vorbedingung: Daten vorhanden", before["backups"] == 1 and before["databases"] == 1 and before["routines"] == 1
      and before["collaborators"] == 1 and before["endpoints_used"] == 1, str(before))
r = c.delete(f"/api/admin/instances/{uuid}", headers=AH)
check("DELETE -> 200", r.status_code == 200 and r.json["uuid"] == uuid, r.get_data(as_text=True)[:200])
check("runner_cleanup ok (Stub)", r.json.get("runner_cleanup") == "ok")
after = counts(iid)
check("Instance und abhaengige Daten weg", after == {"instance": 0, "backups": 0, "databases": 0, "collaborators": 0,
                                                 "routines": 0, "actions": 0, "endpoints_used": 0}, str(after))
with app.app_context():
    check("Endpoint wieder frei (alle Endpoints frei)", Endpoint.query.filter_by(instance_id=None).count() == N_EP)
    check("Endpoint-Zeilen bleiben erhalten", Endpoint.query.count() == N_EP)
    ev = ActivityLog.query.filter_by(event="instance:deleted").first()
    check("Activity instance:deleted mit Name/UUID", ev is not None and uuid in str(ev.properties) and ev.subject_id == iid, str(ev and ev.properties))
    check("Activity-Historie der Instance bleibt", ActivityLog.query.filter_by(subject_id=iid, event="instance:created").count() == 1)
check("erneutes DELETE -> 404", c.delete(f"/api/admin/instances/{uuid}", headers=AH).status_code == 404)
r = c.post("/api/admin/instances", json={"name": "wieder", "owner_id": ids["owner"], "agent_id": ids["agent"], "blueprint_id": ids["bp"]})
check("freigegebener Endpoint wiederverwendbar", r.status_code == 201)
print("Laufende Vorgaenge")
for status in ("provisioning", "reinstalling", "restoring", "transferring"):
    iid2, uuid2 = new_instance(f"busy-{status}")
    with app.app_context():
        db.session.get(Instance, iid2).status = status
        db.session.commit()
    r = c.delete(f"/api/admin/instances/{uuid2}", headers=AH)
    check(f"Status {status} -> 409", r.status_code == 409 and status in r.json["error"], r.get_data(as_text=True)[:120])
    check(f"Status {status}: Instance bleibt", counts(iid2)["instance"] == 1)
r = c.delete(f"/api/admin/instances/{uuid2}", json={"force": True}, headers=AH)
check("force=true erzwingt Loeschen (transferring)", r.status_code == 200 and r.json["forced"] is True)
r = c.delete(f"/api/admin/instances/{new_instance('force-str')[1]}", json={"force": "yes"}, headers=AH)
check("force nur als echtes true (String 'yes' zaehlt nicht)", r.status_code == 200 and r.json["forced"] is False)

print("Runner-Fehler (best effort)")


class FailingRunner(StubRunnerAdapter):
    def delete_instance(self, agent, instance):
        raise RuntimeError("Node weg")

    def delete_backup(self, agent, instance, backup):
        return RunnerResponse(success=False, message="x")


with app.app_context():
    old_runner = get_runner()
set_runner(FailingRunner())
iid3, uuid3 = new_instance("runner-down")
add_children(iid3)
r = c.delete(f"/api/admin/instances/{uuid3}", headers=AH)
check("Runner faellt aus -> Panel loescht trotzdem (200)", r.status_code == 200, r.get_data(as_text=True)[:150])
check("runner_cleanup = failed gemeldet", r.json.get("runner_cleanup") == "failed")
check("Panel-Daten trotzdem weg", counts(iid3)["instance"] == 0 and counts(iid3)["backups"] == 0)
with app.app_context():
    ev = ActivityLog.query.filter_by(event="instance:deleted").order_by(ActivityLog.id.desc()).first()
    check("Activity vermerkt runner_cleanup=failed", "failed" in str(ev.properties))
set_runner(old_runner)

print("Owner loescht")
iid4, uuid4 = new_instance("own-del")
name4 = "own-del"
add_children(iid4)
check("ohne Login -> 401", c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4}).status_code == 401)
r = c.delete(f"/api/client/instances/{uuid4}", headers=OH)
check("ohne confirm -> 400", r.status_code == 400)
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": "falsch"}, headers=OH)
check("falsches confirm -> 400", r.status_code == 400)
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4.upper()}, headers=OH)
check("confirm ist case-sensitiv -> 400", r.status_code == 400)
check("nach Fehlversuchen noch da", counts(iid4)["instance"] == 1)
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4}, headers={"X-User-Id": str(ids["other"])})
check("fremder Nutzer -> 404", r.status_code == 404)
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4}, headers={"X-User-Id": str(ids["collab"])})
check("Collaborator darf nicht loeschen -> 404", r.status_code == 404)
check("weiterhin da", counts(iid4)["instance"] == 1)
with app.app_context():
    inst = db.session.get(Instance, iid4)
    inst.status = "suspended"
    db.session.commit()
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4}, headers=OH)
check("suspendiert -> 409 (Admin-Sperre)", r.status_code == 409)
with app.app_context():
    db.session.get(Instance, iid4).status = None
    db.session.commit()
r = c.delete(f"/api/client/instances/{uuid4}", json={"confirm": name4}, headers=OH)
check("Owner mit confirm -> 200", r.status_code == 200, r.get_data(as_text=True)[:150])
check("alles weg", counts(iid4)["instance"] == 0 and counts(iid4)["databases"] == 0 and counts(iid4)["routines"] == 0)
iid5, uuid5 = new_instance("busy-own")
with app.app_context():
    db.session.get(Instance, iid5).status = "provisioning"
    db.session.commit()
r = c.delete(f"/api/client/instances/{uuid5}", json={"confirm": "busy-own", "force": True}, headers=OH)
check("Owner kann force nicht nutzen (provisioning -> 409)", r.status_code == 409)

print("Admin-Guard")
iid6, uuid6 = new_instance("guard")
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Login -> 401", c.delete(f"/api/admin/instances/{uuid6}").status_code == 401)
check("normaler Nutzer -> 403", c.delete(f"/api/admin/instances/{uuid6}", headers=OH).status_code == 403)
check("Admin -> 200", c.delete(f"/api/admin/instances/{uuid6}", headers=AH).status_code == 200)
app.config["ADMIN_GUARD_ENABLED"] = False

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
