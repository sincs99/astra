"""M49 – Alle Zeitstempel in API-Antworten sind UTC mit Zeitzonen-Suffix."""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.utils.timeutil import iso_utc
from app.domain.agents.models import Agent
from app.domain.backups.models import Backup
from app.domain.blueprints.models import Blueprint
from app.domain.collaborators.models import Collaborator
from app.domain.databases.models import Database, DatabaseProvider
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.routines.models import Action, Routine
from app.domain.users.models import User
from app.domain.webhooks.models import Webhook

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


print("Helfer iso_utc")
check("None -> None", iso_utc(None) is None)
check("naiv gilt als UTC", iso_utc(datetime(2026, 10, 3, 12, 0, 0)) == "2026-10-03T12:00:00+00:00")
check("mit Mikrosekunden", iso_utc(datetime(2026, 10, 3, 12, 0, 0, 123456)) == "2026-10-03T12:00:00.123456+00:00")
check("aware UTC bleibt UTC", iso_utc(datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)) == "2026-10-03T12:00:00+00:00")
check("aware andere Zone wird nach UTC umgerechnet",
      iso_utc(datetime(2026, 10, 3, 14, 0, tzinfo=timezone(timedelta(hours=2)))) == "2026-10-03T12:00:00+00:00")
check("Ergebnis ist vom Browser als UTC lesbar (ISO mit Offset)",
      datetime.fromisoformat(iso_utc(datetime(2026, 1, 1, 0, 0))).utcoffset() == timedelta(0))

app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    owner = User(username="own", email="own@t.local")
    collab = User(username="col", email="col@t.local")
    for u in (admin, owner, collab):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", last_seen_at=datetime(2026, 10, 3, 10, 0, 0))
    agent.generate_daemon_credentials()
    agent.maintenance_mode = True
    agent.maintenance_started_at = datetime(2026, 10, 3, 9, 0, 0)
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    provider = DatabaseProvider(name="p", host="db.test")
    db.session.add_all([admin, owner, collab, agent, bp, provider])
    db.session.commit()
    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565)
    db.session.add(ep)
    # zweiter, normaler Agent fuer die automatische Platzierung der Bestellung (der erste steht in Wartung)
    agent2 = Agent(name="n2", fqdn="n2.test")
    agent2.generate_daemon_credentials()
    db.session.add(agent2)
    db.session.commit()
    db.session.add(Endpoint(agent_id=agent2.id, ip="0.0.0.0", port=25600))
    db.session.commit()
    inst = Instance(name="i", owner_id=owner.id, agent_id=agent.id, blueprint_id=bp.id, primary_endpoint_id=ep.id,
                    installed_at=datetime(2026, 10, 3, 8, 0, 0), suspended_at=datetime(2026, 10, 3, 9, 30, 0))
    db.session.add(inst)
    db.session.commit()
    ep.instance_id = inst.id
    db.session.add_all([
        Backup(instance_id=inst.id, name="bk", is_successful=True, completed_at=datetime(2026, 10, 3, 7, 0, 0)),
        Database(instance_id=inst.id, provider_id=provider.id, db_name="d", username="u", password="x"),
        Collaborator(instance_id=inst.id, user_id=collab.id, permissions=["file.read"]),
    ])
    r = Routine(instance_id=inst.id, name="rt", last_run_at=datetime(2026, 10, 3, 6, 0, 0),
                next_run_at=datetime(2026, 10, 3, 18, 0, 0))
    db.session.add(r)
    db.session.commit()
    db.session.add(Action(routine_id=r.id, sequence=1, action_type="power", payload={"action": "restart"}))
    db.session.commit()
    ids = dict(admin=admin.id, owner=owner.id, agent=agent.id, bp=bp.id, inst=inst.id, uuid=inst.uuid,
               provider=provider.id, ep=ep.id, routine=r.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["owner"])}

# Bestellung, Produkt, Webhook, SSH-Key, API-Key anlegen (ueber die API, wie echte Daten)
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50,
                                         "price_cents": 100}, headers=AH)
pid = r.json["id"]
r = c.post("/api/client/orders", json={"product_id": pid, "name": "ord"}, headers=OH)
order_uuid = r.json["uuid"]
c.post(f"/api/admin/orders/{order_uuid}/mark-paid", json={"payment_reference": "ref"}, headers=AH)
c.post("/api/admin/webhooks", json={"url": "https://example.com/hook", "events": ["instance:created"]}, headers=AH)
c.post("/api/auth/api-keys", json={"name": "k"}, headers=OH)

ISO_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
TZ_OK = re.compile(r"(Z|[+-]\d{2}:\d{2})$")
seen = {"total": 0}
bad = []


def scan(node, path, where):
    if isinstance(node, dict):
        for k, v in node.items():
            scan(v, f"{path}.{k}", where)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan(v, f"{path}[{i}]", where)
    elif isinstance(node, str) and ISO_LIKE.match(node):
        seen["total"] += 1
        if not TZ_OK.search(node):
            bad.append(f"{where} {path} = {node}")


param_values = {"agent_id": ids["agent"], "instance_id": ids["inst"], "blueprint_id": ids["bp"], "product_id": pid,
                "uuid": ids["uuid"], "provider_id": ids["provider"], "routine_id": ids["routine"], "user_id": ids["owner"],
                "endpoint_id": ids["ep"]}
print("Alle GET-Routen (Admin, Client, Auth) durchsuchen")
visited = 0
skipped = []
with app.app_context():
    rules = [r for r in app.url_map.iter_rules()
             if "GET" in r.methods and r.rule.startswith(("/api/admin", "/api/client", "/api/auth", "/ops", "/health"))]
for rule in sorted(rules, key=lambda r: r.rule):
    path = rule.rule
    ok = True
    for arg in rule.arguments:
        if arg in param_values:
            path = re.sub(r"<(?:\w+:)?" + arg + ">", str(param_values[arg]), path)
        else:
            ok = False
    if not ok:
        skipped.append(rule.rule)
        continue
    hdr = AH if path.startswith("/api/admin") else OH
    resp = c.get(path, headers=hdr)
    if resp.status_code == 200 and resp.is_json:
        visited += 1
        scan(resp.get_json(), "", path)
check(f"viele Routen abgefragt ({visited}, uebersprungen: {len(skipped)})", visited >= 25, str(skipped[:10]))
check(f"viele Zeitstempel geprueft ({seen['total']})", seen["total"] >= 40)
check("jeder Zeitstempel endet auf Z oder +hh:mm", not bad, "; ".join(bad[:8]))

print("Stichprobe je Modell (naive DB-Werte)")
with app.app_context():
    samples = {
        "User": User.query.first().to_dict()["created_at"],
        "Agent": db.session.get(Agent, ids["agent"]).to_dict()["last_seen_at"],
        "Blueprint": db.session.get(Blueprint, ids["bp"]).to_dict()["created_at"],
        "Instance": db.session.get(Instance, ids["inst"]).to_dict()["installed_at"],
        "Endpoint": db.session.get(Endpoint, ids["ep"]).to_dict()["created_at"],
        "Backup": Backup.query.first().to_dict()["completed_at"],
        "Database": Database.query.first().to_dict()["created_at"],
        "Collaborator": Collaborator.query.first().to_dict()["created_at"],
        "Routine": db.session.get(Routine, ids["routine"]).to_dict()["next_run_at"],
        "Action": Action.query.first().to_dict()["created_at"],
    }
for name, value in samples.items():
    check(f"{name}: {value}", isinstance(value, str) and value.endswith("+00:00"))
check("Wert bleibt derselbe (keine Zeitverschiebung)", samples["Agent"] == "2026-10-03T10:00:00+00:00", samples["Agent"])
mine = [i for i in c.get("/api/admin/instances", headers=AH).json if i["uuid"] == ids["uuid"]][0]
check("Instance.suspended_at ohne Verschiebung", mine["suspended_at"] == "2026-10-03T09:30:00+00:00", str(mine["suspended_at"]))

print("Billing: Ereignisdaten und Bestellung")
o = c.get(f"/api/admin/orders/{order_uuid}", headers=AH).json
check("Order paid_at/current_period_end mit Suffix", o["paid_at"].endswith("+00:00") and o["current_period_end"].endswith("+00:00"))
from app.domain.activity.models import ActivityLog
with app.app_context():
    props = [str(e.properties) for e in ActivityLog.query.filter(ActivityLog.event.like("order:%")).all()]
check("Bestellereignisse enthalten keine Zeitstempel ohne Suffix", not any(re.search(r"\d{4}-\d\d-\d\dT[\d:.]+'", p) for p in props), str(props[:3]))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
