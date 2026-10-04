"""M69 – Admin schickt eine manuelle Zahlungserinnerung (POST /api/admin/orders/<uuid>/remind)."""

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
from app.i18n import format_datetime
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


def product(price=499, name="Paket"):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": 100, "disk": 500, "cpu": 50,
                                             "price_cents": price, "billing_period_days": 30,
                                             **({"max_instances_per_user": 5} if price == 0 else {})}, headers=AH)
    return r.json["id"]


def new_order(pid, hdr=U1):
    n[0] += 1
    return c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=hdr).json["uuid"]


def pay(ou, ref):
    return c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def remind(ou, hdr=AH):
    return c.post(f"/api/admin/orders/{ou}/remind", headers=hdr)


def user_mails(ou, to="k1@t.local"):
    return [m for m in mail.outbox if m["to"] == to and ou in m["body"]]


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"id": o.id, "end": o.current_period_end, "purpose": o.payment_purpose, "status": o.status}


def manual_events(ou):
    with app.app_context():
        oid = Order.query.filter_by(uuid=ou).first().id
        return [e for e in ActivityLog.query.filter_by(event="order:reminder", subject_id=oid).all()
                if (e.properties or {}).get("kind") == "manual"]


def age_manual_events(ou, hours):
    with app.app_context():
        oid = Order.query.filter_by(uuid=ou).first().id
        for e in ActivityLog.query.filter_by(event="order:reminder", subject_id=oid).all():
            e.created_at = datetime.utcnow() - timedelta(hours=hours)
        db.session.commit()


PID = product()
FREE = product(0, "Gratis")

print("active: Erinnerung vor Laufzeitende")
o1 = new_order(PID)
pay(o1, "p1")
mail.outbox.clear()
r = remind(o1)
st = order(o1)
check("200 mit sent_at (UTC) und kind=expiry_reminder", r.status_code == 200 and r.json["kind"] == "expiry_reminder" and r.json["sent_at"].endswith("+00:00"), str(r.json))
ms = user_mails(o1)
check("Mail an den Kunden mit Laufzeitende, Betrag und Verwendungszweck", len(ms) == 1 and ms[0]["subject"] == "Astra: Die Laufzeit deines Servers endet bald"
      and f"{st['end']:%d.%m.%Y %H:%M} UTC" in ms[0]["body"] and "4,99 EUR" in ms[0]["body"] and f"Verwendungszweck: {st['purpose']}" in ms[0]["body"], str(ms))
ev = manual_events(o1)
check("Activity-Event order:reminder (kind=manual) mit Akteur", len(ev) == 1 and ev[0].actor_id == ids["admin"] and ev[0].properties["mail"] == "expiry_reminder", str(ev and ev[0].properties))

print("Cooldown")
mail.outbox.clear()
r = remind(o1)
check("zweiter Aufruf: 429 reminder_cooldown mit retry_after_seconds", r.status_code == 429 and r.json["code"] == "reminder_cooldown"
      and 86300 <= r.json["retry_after_seconds"] <= 86400 and "error" in r.json, str(r.json))
check("keine zweite Mail, kein zweites Event", not user_mails(o1) and len(manual_events(o1)) == 1)
age_manual_events(o1, 10)
r = remind(o1)
check("nach 10 Stunden: weiter 429, Restzeit ca. 14 h", r.status_code == 429 and 14 * 3600 - 120 <= r.json["retry_after_seconds"] <= 14 * 3600 + 5, str(r.json))
age_manual_events(o1, 25)
r = remind(o1)
check("nach 25 Stunden: wieder erlaubt", r.status_code == 200 and len(user_mails(o1)) == 1)
o2 = new_order(PID)
pay(o2, "p2")
check("andere Bestellung unabhaengig", remind(o2).status_code == 200)

print("Automatische Erinnerungen bleiben unberuehrt")
REM = app.config["BILLING_REMINDER_DAYS"]
end2 = order(o2)["end"]
mail.outbox.clear()
with app.app_context():
    res = run_billing_tick(end2 - timedelta(days=REM) + timedelta(minutes=1))
ms = [m for m in user_mails(o2)]
check("Tick verschickt die automatische Erinnerung trotz manueller", res["reminded"] >= 1 and len(ms) == 1, str(res))
o3 = new_order(PID)
pay(o3, "p3")
end3 = order(o3)["end"]
with app.app_context():
    run_billing_tick(end3 - timedelta(days=REM) + timedelta(minutes=1))
mail.outbox.clear()
check("automatische Erinnerung zaehlt nicht als manuelle: 200", remind(o3).status_code == 200)

print("past_due: Zahlung ueberfaellig mit Restfrist")
o4 = new_order(PID)
pay(o4, "p4")
end4 = order(o4)["end"]
with app.app_context():
    run_billing_tick(end4 + timedelta(hours=1))
check("Vorbedingung past_due", order(o4)["status"] == "past_due")
with app.app_context():
    o = Order.query.filter_by(uuid=o4).first()
    o.past_due_at = datetime.utcnow() - timedelta(days=2)
    db.session.commit()
mail.outbox.clear()
r = remind(o4)
ms = user_mails(o4)
check("kind=past_due, Mail mit verbleibenden 5 Tagen und Verwendungszweck", r.status_code == 200 and r.json["kind"] == "past_due" and len(ms) == 1
      and ms[0]["subject"] == "Astra: Zahlung überfällig – dein Server wurde gesperrt" and "innerhalb von 5 Tagen" in ms[0]["body"]
      and f"Verwendungszweck: {order(o4)['purpose']}" in ms[0]["body"], str(ms))

print("pending_payment: Zahlung noch offen")
o5 = new_order(PID)
mail.outbox.clear()
r = remind(o5)
ms = user_mails(o5)
check("kind=payment_open, Mail mit Betrag und Verwendungszweck", r.status_code == 200 and r.json["kind"] == "payment_open" and len(ms) == 1
      and ms[0]["subject"] == "Astra: Zahlung noch offen" and "4,99 EUR" in ms[0]["body"] and f"Verwendungszweck: {order(o5)['purpose']}" in ms[0]["body"], str(ms))

print("Sprache des Kunden")
with app.app_context():
    db.session.get(User, ids["u1"]).locale = "en"
    db.session.commit()
o6 = new_order(PID)
mail.outbox.clear()
remind(o6)
ms = user_mails(o6)
check("EN: Payment still outstanding mit €4.99", len(ms) == 1 and ms[0]["subject"] == "Astra: Payment still outstanding" and "\u20ac4.99" in ms[0]["body"]
      and f"Payment reference: {order(o6)['purpose']}" in ms[0]["body"], str(ms))
o7 = new_order(PID)
pay(o7, "p7")
mail.outbox.clear()
remind(o7)
ms = user_mails(o7)
check("EN: Erinnerung vor Laufzeitende mit englischem Datum", len(ms) == 1 and ms[0]["subject"] == "Astra: The term of your server ends soon"
      and format_datetime("en", order(o7)["end"]) in ms[0]["body"], str(ms))
with app.app_context():
    db.session.get(User, ids["u1"]).locale = None
    db.session.commit()

print("Nicht erlaubt (409)")
def code(r):
    return (r.status_code, r.json.get("code"))
o_free = new_order(FREE)
check("kostenlose Bestellung: 409 nothing_to_pay", code(remind(o_free)) == (409, "nothing_to_pay"))
o_c = new_order(PID)
pay(o_c, "pc")
c.post(f"/api/client/orders/{o_c}/cancel", headers=U1)
check("gekuendigte aktive Bestellung: 409 cancelled", code(remind(o_c)) == (409, "cancelled"))
o_cancel = new_order(PID)
c.post(f"/api/client/orders/{o_cancel}/cancel", headers=U1)
check("stornierte Bestellung: 409 invalid_status", code(remind(o_cancel)) == (409, "invalid_status"))
o_exp = new_order(PID)
pay(o_exp, "pe")
with app.app_context():
    run_billing_tick(order(o_exp)["end"] + timedelta(hours=1))   # -> past_due
    run_billing_tick(order(o_exp)["end"] + timedelta(days=9))     # Karenzzeit vorbei -> expired
check("beendete Bestellung (expired): 409 invalid_status", order(o_exp)["status"] == "expired" and code(remind(o_exp)) == (409, "invalid_status"), str(order(o_exp)))
with app.app_context():
    o = Order.query.filter_by(uuid=o7).first()
    o.status = "refunded"
    db.session.commit()
check("erstattete Bestellung: 409 invalid_status", code(remind(o7)) == (409, "invalid_status"))
with app.app_context():
    o = Order.query.filter_by(uuid=o6).first()
    o.status = "awaiting_provisioning"
    db.session.commit()
check("bezahlt, aber noch nicht bereitgestellt: 409 invalid_status", code(remind(o6)) == (409, "invalid_status"))
check("409 ohne Cooldown-Eintrag und ohne Mail", not manual_events(o_free) and not manual_events(o_cancel) and not user_mails(o_cancel))
o_ne = new_order(PID)
with app.app_context():
    db.session.get(User, ids["u1"]).email = ""
    db.session.commit()
check("Kunde ohne E-Mail: 409 no_email", code(remind(o_ne)) == (409, "no_email"))
with app.app_context():
    db.session.get(User, ids["u1"]).email = "k1@t.local"
    db.session.commit()
check("danach geht es wieder (kein Cooldown durch den Fehler)", remind(o_ne).status_code == 200)
check("unbekannte Bestellung: 404", remind("gibt-es-nicht").status_code == 404)

print("Rechte")
app.config["ADMIN_GUARD_ENABLED"] = True
o8 = new_order(PID)
check("ohne Anmeldung: 401", c.post(f"/api/admin/orders/{o8}/remind").status_code == 401)
check("Kunde: 403", remind(o8, U1).status_code == 403)
check("Admin: 200", remind(o8).status_code == 200)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
