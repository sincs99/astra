"""M56 – Warnung bei lange wartenden bezahlten Bestellungen (Status-Endpunkt und Preflight)."""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order
from app.domain.billing.service import run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.infrastructure import mail
from app.utils.timeutil import iso_utc

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
    u1 = User(username="k1", email="k1@t.local")
    u2 = User(username="k2", email="k2@t.local")
    for u in (admin, u1, u2):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=1024, disk_total=100000, cpu_total=400)
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([admin, u1, u2, agent, bp])
    db.session.commit()
    for i in range(10):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, agent=agent.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
U2 = {"X-User-Id": str(ids["u2"])}
T0 = datetime.utcnow()
n = [0]


def product(memory, name):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": memory, "disk": 500,
                                             "cpu": 50, "price_cents": 100, "billing_period_days": 30}, headers=AH)
    return r.json["id"]


def paid(pid, ref):
    n[0] += 1
    ou = c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=U1).json["uuid"]
    return ou, c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def status():
    return c.get("/api/admin/billing/status", headers=AH).json


def preflight():
    from app.domain.system import upgrade_service as us
    with app.app_context():
        return us.run_preflight_check()


print("Ohne wartende Bestellungen")
aw = status()["awaiting_provisioning"]
check("count 0, kein Alter, nicht zu lange", aw["count"] == 0 and aw["oldest_paid_at"] is None and aw["oldest_wait_hours"] is None
      and aw["waiting_too_long"] is False and aw["warn_after_hours"] == 24, str(aw))
check("Preflight: billing_waiting_orders ok", preflight()["checks"]["billing_waiting_orders"] == "ok")

print("Bestellung wartet")
big = product(900, "Gross")
paid(big, "w0")
o_wait, r = paid(big, "w1")
check("zweite Bestellung wartet (409)", r.status_code == 409)
aw = status()["awaiting_provisioning"]
check("frisch: count 1, Alter ~0, keine Warnung", aw["count"] == 1 and aw["oldest_wait_hours"] < 1 and aw["waiting_too_long"] is False, str(aw))
check("oldest_paid_at mit UTC-Suffix", aw["oldest_paid_at"].endswith("+00:00"))
check("Preflight weiter ok", preflight()["checks"]["billing_waiting_orders"] == "ok")

print("Wartet zu lange")
with app.app_context():
    o = Order.query.filter_by(uuid=o_wait).first()
    o.paid_at = datetime.utcnow() - timedelta(hours=30)
    db.session.commit()
aw = status()["awaiting_provisioning"]
check("30 Stunden: waiting_too_long", aw["waiting_too_long"] is True and 29.5 <= aw["oldest_wait_hours"] <= 30.5, str(aw))
pf = preflight()
check("Preflight: warning mit Stunden", pf["checks"]["billing_waiting_orders"] == "warning"
      and any("30" in i and "Kapazitaet" in i for i in pf["issues"]), str(pf["issues"]))
app.config["BILLING_WAIT_WARN_HOURS"] = 48
check("Schwelle 48 Stunden: keine Warnung", status()["awaiting_provisioning"]["waiting_too_long"] is False
      and preflight()["checks"]["billing_waiting_orders"] == "ok")
app.config["BILLING_WAIT_WARN_HOURS"] = 24

print("Bereitstellung beendet die Warnung")
with app.app_context():
    db.session.get(Agent, ids["agent"]).memory_total = 4096
    db.session.commit()
with app.app_context():
    run_billing_tick()
aw = status()["awaiting_provisioning"]
check("nach dem Tick: nichts wartet mehr, Preflight ok", aw["count"] == 0 and aw["waiting_too_long"] is False
      and preflight()["checks"]["billing_waiting_orders"] == "ok")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
