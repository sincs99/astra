"""M39 – Endpoint-Bulk-Anlage und Instance-Verbindungsadresse."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from sqlalchemy import event

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
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
app.config["ADMIN_GUARD_ENABLED"] = True

with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    admin.set_password("test1234")
    owner = User(username="own", email="own@t.local")
    owner.set_password("test1234")
    agent = Agent(name="n1", fqdn="node1.example.com")
    agent.generate_daemon_credentials()
    other = Agent(name="n2", fqdn="node2.example.com")
    other.generate_daemon_credentials()
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([admin, owner, agent, other, bp])
    db.session.commit()
    admin_id, owner_id, agent_id, other_id, bp_id = admin.id, owner.id, agent.id, other.id, bp.id

c = app.test_client()
H = {"X-User-Id": str(admin_id)}
url = lambda aid=agent_id: f"/api/admin/agents/{aid}/endpoints/bulk"

print("Bulk-Anlage")
r = c.post(url(), json={"ip": "0.0.0.0", "port_start": 25565, "port_end": 25569}, headers=H)
check("5 Ports -> 201", r.status_code == 201 and r.json["created"] == 5 and r.json["skipped"] == 0, r.get_data(as_text=True)[:200])
check("endpoints enthaelt neue", [e["port"] for e in r.json["endpoints"]] == list(range(25565, 25570)))
r = c.post(url(), json={"ip": "0.0.0.0", "port_start": 25567, "port_end": 25572}, headers=H)
check("ueberlappend: 3 neu, 3 uebersprungen", r.json["created"] == 3 and r.json["skipped"] == 3)
r = c.post(url(), json={"ip": "0.0.0.0", "port_start": 25565, "port_end": 25572}, headers=H)
check("alles vorhanden -> 200, created 0", r.status_code == 200 and r.json["created"] == 0 and r.json["skipped"] == 8)
r = c.post(url(), json={"port_start": 25565, "port_end": 25565}, headers=H)
check("ip Standard 0.0.0.0", r.json["skipped"] == 1)
r = c.post(url(), json={"ip": "10.0.0.5", "port_start": 25565, "port_end": 25565}, headers=H)
check("andere IP = neuer Endpoint", r.json["created"] == 1)
r = c.post(url(other_id), json={"port_start": 25565, "port_end": 25565}, headers=H)
check("anderer Agent unabhaengig", r.json["created"] == 1)
r = c.post(url(), json={"port_start": 1, "port_end": 1000}, headers=H)
check("genau 1000 Ports erlaubt", r.status_code == 201 and r.json["created"] == 1000, str(r.status_code))
with app.app_context():
    check("in DB gespeichert", Endpoint.query.filter_by(agent_id=agent_id).count() == 1009,
          str(Endpoint.query.filter_by(agent_id=agent_id).count()))
    check("keine Duplikate", db.session.query(Endpoint.ip, Endpoint.port, Endpoint.agent_id).count()
          == db.session.query(Endpoint.ip, Endpoint.port, Endpoint.agent_id).distinct().count())

print("Validierung")
bad = [
    ({"port_start": 1, "port_end": 1001}, "1001 Ports"),
    ({"port_start": 30, "port_end": 20}, "start > end"),
    ({"port_start": 0, "port_end": 10}, "start 0"),
    ({"port_start": 1, "port_end": 65536}, "end 65536"),
    ({"port_start": "1", "port_end": 5}, "String"),
    ({"port_start": True, "port_end": 5}, "bool"),
    ({"port_start": 1}, "port_end fehlt"),
    ({"ip": "kein-ip", "port_start": 1, "port_end": 2}, "ungueltige IP"),
]
for body, label in bad:
    check(f"{label} -> 400", c.post(url(), json=body, headers=H).status_code == 400)
check("unbekannter Agent -> 404", c.post(url(99999), json={"port_start": 1, "port_end": 2}, headers=H).status_code == 404)
check("ohne Login -> 401", c.post(url(), json={"port_start": 1, "port_end": 2}).status_code == 401)
check("65535 als Obergrenze ok", c.post(url(), json={"port_start": 65535, "port_end": 65535}, headers=H).status_code == 201)

print("Verbindungsadresse")
with app.app_context():
    ep = Endpoint.query.filter_by(agent_id=agent_id, port=25565, ip="0.0.0.0").first()
    inst = Instance(name="mit", owner_id=owner_id, agent_id=agent_id, blueprint_id=bp_id, primary_endpoint_id=ep.id)
    inst2 = Instance(name="ohne", owner_id=owner_id, agent_id=agent_id, blueprint_id=bp_id)
    db.session.add_all([inst, inst2])
    db.session.commit()
    ep.instance_id = inst.id
    db.session.commit()
    uuid1, uuid2 = inst.uuid, inst2.uuid

r = c.get("/api/admin/instances", headers=H)
by = {i["name"]: i for i in r.json}
check("connection gesetzt", by["mit"]["connection"] == {
    "host": "node1.example.com", "ip": "0.0.0.0", "port": 25565, "sftp_port": 2022,
    "address": "node1.example.com:25565"}, str(by["mit"]["connection"]))
check("ohne Endpoint -> null", by["ohne"]["connection"] is None)
oh = {"X-User-Id": str(owner_id)}
r = c.get("/api/client/instances", headers=oh)
by = {i["name"]: i for i in r.json}
check("Client-Liste: connection", by["mit"]["connection"]["address"] == "node1.example.com:25565" and by["ohne"]["connection"] is None, r.get_data(as_text=True)[:200])
r = c.get(f"/api/client/instances/{uuid1}", headers=oh)
check("Client-Detail: connection", r.status_code == 200 and r.json["connection"]["port"] == 25565)
check("Client-Detail: sftp_port fuer Nicht-Admin", r.json["connection"]["sftp_port"] == 2022)
with app.app_context():
    a = db.session.get(Agent, agent_id)
    a.daemon_sftp = 2222
    db.session.commit()
r = c.get(f"/api/client/instances/{uuid1}", headers=oh)
check("sftp_port folgt dem Agent (2222)", r.json["connection"]["sftp_port"] == 2222)

print("Keine Query pro Instanz in Listen")
with app.app_context():
    for i in range(10):
        db.session.add(Instance(name=f"x{i}", owner_id=owner_id, agent_id=other_id, blueprint_id=bp_id))
    db.session.commit()
    counts = []
    engine = db.engine
    def counter(*a, **k):
        counts.append(1)
    event.listen(engine, "before_cursor_execute", counter)
    app.test_client().get("/api/admin/instances", headers=H)
    n_admin = len(counts)
    counts.clear()
    app.test_client().get("/api/client/instances", headers=oh)
    n_client = len(counts)
    event.remove(engine, "before_cursor_execute", counter)
print(f"  (Queries admin={n_admin}, client={n_client})")
check("Admin-Liste Queries konstant (<= 8 bei 13 Instanzen)", n_admin <= 8, str(n_admin))
check("Client-Liste Queries konstant (<= 12 bei 13 Instanzen)", n_client <= 12, str(n_client))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
