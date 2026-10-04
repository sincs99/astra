"""M54 – Bestaetigungsmails bei Zahlung, Verlaengerung und Bereitstellung."""

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


def product(memory, name, price=100):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": memory, "disk": 500,
                                             "cpu": 50, "price_cents": price, "billing_period_days": 30,
                                             **({"max_instances_per_user": 3} if price == 0 else {})}, headers=AH)
    return r.json["id"]


def new_order(pid, hdr=U1):
    n[0] += 1
    return c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=hdr).json["uuid"]


def pay(ou, ref):
    return c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def mails_for(ou):
    return [m for m in mail.outbox if ou in m["body"]]


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"status": o.status, "end": o.current_period_end}


big = product(900, "Gross")
free = product(100, "Gratis", price=0)

print("Erste Zahlung mit Platz")
o1 = new_order(big)
check("Bestellen allein verschickt keine Mail", not mails_for(o1))
mail.outbox.clear()
r = pay(o1, "a1")
ms = mails_for(o1)
check("Zahlung: genau eine Mail 'Server ist bereit'", r.status_code == 200 and len(ms) == 1 and ms[0]["subject"] == "Astra: Dein Server ist bereit", str(ms))
check("Mail an den Kunden, nennt Zahlung und Adresse", ms[0]["to"] == "k1@t.local" and "Zahlung ist eingegangen" in ms[0]["body"]
      and "n1.test:" in ms[0]["body"], ms[0]["body"])
pay(o1, "a1")
check("gleiche Referenz nochmal: keine zweite Mail", len(mails_for(o1)) == 1)

print("Verlaengerung")
mail.outbox.clear()
r = pay(o1, "a2")
ms = mails_for(o1)
end = order(o1)["end"]
check("Verlaengerung: Mail mit neuem Ende", len(ms) == 1 and "verlängert" in ms[0]["subject"] and f"{end:%d.%m.%Y}" in ms[0]["body"], str(ms))
pay(o1, "a2")
check("wiederholte Referenz (No-op): keine weitere Mail", len(mails_for(o1)) == 1)

print("Kein Platz")
o2 = new_order(big)
mail.outbox.clear()
r = pay(o2, "b1")
ms = mails_for(o2)
check("409, aber Mail 'Zahlung eingegangen' mit Hinweis auf Wartezeit", r.status_code == 409 and len(ms) == 1
      and ms[0]["subject"] == "Astra: Zahlung eingegangen" and "kein Platz" in ms[0]["body"], str(ms))
mail.outbox.clear()
r = pay(o2, "b1")
check("erneuter Versuch ohne Platz: keine weitere Mail", r.status_code == 409 and not mails_for(o2))
with app.app_context():
    db.session.get(Agent, ids["agent"]).memory_total = 4096
    db.session.commit()
r = pay(o2, "b1")
ms = mails_for(o2)
check("Admin stellt bereit: Mail 'Server ist bereit'", r.status_code == 200 and len(ms) == 1
      and ms[0]["subject"] == "Astra: Dein Server ist bereit", str(ms))

print("Gratis-Paket")
mail.outbox.clear()
o3 = new_order(free)
check("Gratis-Bestellung: aktiv, keine Zahlungsmail", order(o3)["status"] == "active" and not mails_for(o3))

print("Mail-Fehler stoppt die Zahlung nicht")
o4 = new_order(big)
orig = mail.send_mail
def boom(*a, **k):
    raise RuntimeError("smtp down")
mail.send_mail = boom
try:
    r = pay(o4, "d1")
finally:
    mail.send_mail = orig
check("Zahlung trotz Mailfehler verbucht", r.status_code == 200 and order(o4)["status"] == "active")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
