"""M52 – Billing-Tick stellt bezahlte Bestellungen ohne Instance automatisch bereit."""

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


def paid_order(pid, hdr=U1, ref=None):
    n[0] += 1
    ou = c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=hdr).json["uuid"]
    r = c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref or f"p{n[0]}"}, headers=AH)
    return ou, r


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"status": o.status, "end": o.current_period_end, "paid_at": o.paid_at, "instance_id": o.instance_id,
                "refs": list(o.payment_references or [])}


def events(name):
    with app.app_context():
        return ActivityLog.query.filter_by(event=name).count()


def tick(now=None):
    with app.app_context():
        return run_billing_tick(now=now)


def set_memory(total):
    with app.app_context():
        db.session.get(Agent, ids["agent"]).memory_total = total
        db.session.commit()


big = product(900, "Gross")
small = product(400, "Klein")

print("Kein Platz: bleibt bezahlt und wartet")
o_first, r = paid_order(big)
check("erste Bestellung belegt den Node (active)", r.status_code == 200 and order(o_first)["status"] == "active")
o_wait, r = paid_order(big, ref="wait-1")
check("zweite: 409 und awaiting_provisioning", r.status_code == 409 and order(o_wait)["status"] == "awaiting_provisioning", r.get_data(as_text=True)[:120])
paid_at = order(o_wait)["paid_at"]
check("Zahlung gespeichert, keine Instance", paid_at is not None and order(o_wait)["instance_id"] is None and order(o_wait)["refs"] == ["wait-1"])
failed_events = events("order:provision_failed")
check("ein Event order:provision_failed fuer den ersten Versuch", failed_events == 1)

mail.outbox.clear()
t1 = T0 + timedelta(minutes=5)
res = tick(t1)
check("Tick ohne Platz: nichts bereitgestellt, keine Fehler", res["provisioned"] == 0 and res["errors"] == [], str(res))
res = tick(t1 + timedelta(minutes=5))
check("noch ein Tick: weiterhin nichts", res["provisioned"] == 0 and order(o_wait)["status"] == "awaiting_provisioning")
check("kein weiteres provision_failed-Event pro Tick (kein Spam)", events("order:provision_failed") == failed_events)
check("keine Mail an den Kunden", not [m for m in mail.outbox if o_wait in m["body"]])
check("checked zaehlt wartende Bestellungen mit", res["checked"] >= 2, str(res))
with app.app_context():
    check("keine halbe Instance", Instance.query.filter_by(name=f"s{n[0]}").count() == 0)

print("Platz wird frei: der Tick stellt bereit")
set_memory(4096)
t2 = T0 + timedelta(hours=3)
res = tick(t2)
check("provisioned = 1", res["provisioned"] == 1 and res["errors"] == [], str(res))
o = order(o_wait)
check("Bestellung active mit Instance", o["status"] == "active" and o["instance_id"] is not None)
check("Laufzeit beginnt mit der Bereitstellung (nicht mit der Zahlung)",
      o["end"] == t2 + timedelta(days=30) and o["paid_at"] == paid_at, f"{o['end']} vs {t2}")
check("Zahlungsreferenz unveraendert, kein zweites order:paid", o["refs"] == ["wait-1"] and events("order:paid") == 2)
check("Event order:provisioned einmal", events("order:provisioned") == 1)
mails = [m for m in mail.outbox if o_wait in m["body"]]
check("Mail 'Dein Server ist bereit' mit Verbindungsadresse",
      len(mails) == 1 and mails[0]["subject"] == "Astra: Dein Server ist bereit" and "n1.test:" in mails[0]["body"], str(mails))
with app.app_context():
    inst = db.session.get(Instance, o["instance_id"])
    check("Instance gehoert dem Kunden mit den Ressourcen des Schnappschusses", inst.owner_id == ids["u1"] and inst.memory == 900)
res = tick(t2 + timedelta(minutes=5))
check("naechster Tick: idempotent", res["provisioned"] == 0 and events("order:provisioned") == 1)

print("Reihenfolge und Teilkapazitaet")
set_memory(1024)
with app.app_context():
    used = db.session.query(db.func.sum(Instance.memory)).scalar()
set_memory(used + 500)            # Platz fuer genau eine kleine (400 MB), nicht fuer zwei
a_ou, a_r = paid_order(big, hdr=U1, ref="q-a")   # 900 MB -> passt nicht
b_ou, b_r = paid_order(small, hdr=U2, ref="q-b")  # 400 MB -> passt sofort (active)
check("Vorbedingung: grosse wartet, kleine ist sofort aktiv", order(a_ou)["status"] == "awaiting_provisioning" and order(b_ou)["status"] == "active")
c_ou, c_r = paid_order(small, hdr=U2, ref="q-c")  # 400 MB -> kein Platz mehr
d_ou, d_r = paid_order(small, hdr=U1, ref="q-d")
check("zwei kleine warten", order(c_ou)["status"] == "awaiting_provisioning" and order(d_ou)["status"] == "awaiting_provisioning")
with app.app_context():
    used = db.session.query(db.func.sum(Instance.memory)).scalar()
set_memory(used + 400)            # Platz fuer genau eine 400-MB-Bestellung
res = tick(T0 + timedelta(hours=5))
check("genau eine wartende wird bereitgestellt (oder passt, die aelteste zuerst)", res["provisioned"] == 1, str(res))
check("aelteste passende Zahlung zuerst: c vor d", order(c_ou)["status"] == "active" and order(d_ou)["status"] == "awaiting_provisioning",
      f"c={order(c_ou)['status']} d={order(d_ou)['status']}")
check("die grosse (900 MB) wartet weiter, ohne andere zu blockieren", order(a_ou)["status"] == "awaiting_provisioning")

print("Fehler einzelner Bestellungen blockieren nicht")
set_memory(65536)
real = billing.fulfill_order
state = {"n": 0}


def flaky(order_obj, now=None, log_failure=True):
    state["n"] += 1
    if order_obj.uuid == a_ou:
        raise RuntimeError("Datenbank-Hickser")
    return real(order_obj, now, log_failure)


billing.fulfill_order = flaky
res = tick(T0 + timedelta(hours=6))
billing.fulfill_order = real
check("Fehler wird gemeldet", len(res["errors"]) == 1 and "Hickser" in res["errors"][0]["error"] and res["errors"][0]["order"] == a_ou, str(res))
check("andere wartende Bestellung wurde trotzdem bereitgestellt", order(d_ou)["status"] == "active")
check("fehlerhafte bleibt wartend", order(a_ou)["status"] == "awaiting_provisioning")
res = tick(T0 + timedelta(hours=6, minutes=5))
check("naechster Tick schafft sie", res["provisioned"] == 1 and res["errors"] == [] and order(a_ou)["status"] == "active", str(res))

print("Zusammenspiel mit Admin und Stripe")
set_memory(1024)
with app.app_context():
    used = db.session.query(db.func.sum(Instance.memory)).scalar()
set_memory(used + 100)
e_ou, e_r = paid_order(big, ref="adm-1")
check("wartet", order(e_ou)["status"] == "awaiting_provisioning")
set_memory(65536)
r = c.post(f"/api/admin/orders/{e_ou}/mark-paid", headers=AH)
check("Admin stellt manuell bereit (mark-paid)", r.status_code == 200 and order(e_ou)["status"] == "active")
res = tick(T0 + timedelta(hours=8))
check("Tick danach: nichts doppelt", res["provisioned"] == 0 and order(e_ou)["refs"] == ["adm-1"])
with app.app_context():
    n_inst = Instance.query.filter_by(owner_id=ids["u1"]).count()
set_memory(1024)
with app.app_context():
    used = db.session.query(db.func.sum(Instance.memory)).scalar()
set_memory(used + 100)
# Stripe-Webhook ohne Platz -> awaiting, dann der Tick
app.config.update(PAYMENT_PROVIDER="stripe", STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x")
from app.domain.billing.payments import PaymentEvent
f_ou = c.post("/api/client/orders", json={"product_id": big, "name": "stripe-srv"}, headers=U2).json["uuid"]
with app.app_context():
    res_ev = billing.process_payment_events("stripe", [PaymentEvent("evt_s1", "checkout.session.completed", "paid", order_uuid=f_ou,
                                                                    payment_reference="pi_s1", amount_cents=100, currency="EUR")])
check("Stripe-Zahlung ohne Platz: verbucht, wartet", res_ev[0]["status"] == "processed" and order(f_ou)["status"] == "awaiting_provisioning")
app.config.update(PAYMENT_PROVIDER="manual", STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
set_memory(65536)
res = tick(T0 + timedelta(hours=9))
check("Tick stellt die Stripe-Bestellung bereit", res["provisioned"] == 1 and order(f_ou)["status"] == "active" and order(f_ou)["refs"] == ["pi_s1"], str(res))

print("Nicht betroffene Bestellungen")
pend = c.post("/api/client/orders", json={"product_id": small, "name": "pend"}, headers=U1).json["uuid"]
res = tick(T0 + timedelta(hours=10))
check("pending_payment wird nie bereitgestellt", order(pend)["status"] == "pending_payment" and res["provisioned"] == 0)
c.post(f"/api/client/orders/{pend}/cancel", headers=U1)
check("stornierte Bestellung bleibt storniert", order(pend)["status"] == "cancelled")

print("API zeigt den Zustand")
od = c.get(f"/api/client/orders/{o_wait}", headers=U1).json
check("Kunde sieht aktive Bestellung mit Verbindungsadresse", od["status"] == "active" and od["connection"] and od["connection"]["host"] == "n1.test")
check("current_period_end mit UTC-Suffix", od["current_period_end"].endswith("+00:00") and od["current_period_end"] == iso_utc(t2 + timedelta(days=30)))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
