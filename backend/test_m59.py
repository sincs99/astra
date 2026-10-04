"""M59 – Stripe-Erstattungen und Zahlungsstreitigkeiten (charge.refunded, charge.dispute.created/closed)."""

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.billing.models import Order, PaymentEvent
from app.domain.billing.service import run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.infrastructure import mail
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


SECRET = "whsec_test_secret"
app = create_app("testing")
app.config.update(PAYMENT_PROVIDER="stripe", STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET=SECRET,
                  ADMIN_ALERT_EMAIL="ops@t.local")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    u1 = User(username="k1", email="k1@t.local")
    for u in (admin, u1):
        u.set_password("test1234")
    bp = Blueprint(name="mc", docker_image="img", startup_command="run")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=8192, disk_total=100000, cpu_total=800)
    db.session.add_all([admin, u1, bp, agent])
    db.session.commit()
    for i in range(20):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, bp=bp.id, agent=agent.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 512, "disk": 1000, "cpu": 50,
                                         "price_cents": 499, "billing_period_days": 30}, headers=AH)
PID = r.json["id"]
n = [0]
seq = [0]


def sign(payload: bytes):
    ts = int(time.time())
    return f"t={ts},v1=" + hmac.new(SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()


def post(obj, etype, event_id=None):
    seq[0] += 1
    body = json.dumps({"id": event_id or f"evt_{seq[0]}", "object": "event", "type": etype, "api_version": "2024-06-20",
                       "created": int(time.time()), "livemode": False, "data": {"object": obj}}).encode()
    return c.post("/api/payments/stripe", data=body, content_type="application/json", headers={"Stripe-Signature": sign(body)})


def paid_order(pi=None):
    """Bestellung anlegen und per Stripe-Webhook bezahlen. Rueckgabe (order_uuid, payment_intent)."""
    n[0] += 1
    pi = pi or f"pi_{n[0]}"
    ou = c.post("/api/client/orders", json={"product_id": PID, "name": f"s{n[0]}"}, headers=U1).json["uuid"]
    r = post({"id": f"cs_{n[0]}", "object": "checkout.session", "payment_status": "paid", "payment_intent": pi,
              "amount_total": 499, "currency": "eur", "metadata": {"order_uuid": ou}, "client_reference_id": ou},
             "checkout.session.completed")
    assert r.status_code == 200, r.get_data(as_text=True)
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        report_install(c, Instance.query.get(o.instance_id).uuid, True)
    return ou, pi


def refund(pi, full=True, event_id=None, meta=None):
    return post({"id": f"ch_{pi}", "object": "charge", "payment_intent": pi, "amount": 499, "currency": "eur",
                 "amount_refunded": 499 if full else 100, "refunded": full, "metadata": meta or {}}, "charge.refunded", event_id)


def dispute(pi, kind="created", status="needs_response", event_id=None):
    return post({"id": f"dp_{pi}", "object": "dispute", "charge": f"ch_{pi}", "payment_intent": pi, "amount": 499,
                 "currency": "eur", "status": status, "reason": "fraudulent"}, f"charge.dispute.{kind}", event_id)


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        inst = db.session.get(Instance, o.instance_id) if o.instance_id else None
        return {"status": o.status, "disputed": o.disputed_at is not None, "refunded_at": o.refunded_at,
                "past_due_at": o.past_due_at, "end": o.current_period_end, "instance_id": o.instance_id,
                "inst_status": inst.status if inst else None, "inst_reason": inst.suspended_reason if inst else None,
                "dict": o.to_dict()}


def events(name):
    with app.app_context():
        return ActivityLog.query.filter_by(event=name).count()


def pe(event_id):
    with app.app_context():
        e = PaymentEvent.query.filter_by(event_id=event_id).first()
        return (e.status, e.detail) if e else None


def user_mails(ou):
    return [m for m in mail.outbox if m["to"] == "k1@t.local" and ou in m["body"]]


def ops_mails():
    return [m for m in mail.outbox if m["to"] == "ops@t.local"]


print("Volle Erstattung")
o1, pi1 = paid_order()
check("Ausgangslage: aktiv, Instance laeuft", order(o1)["status"] == "active" and order(o1)["inst_status"] is None)
mail.outbox.clear()
r = refund(pi1, event_id="evt_ref_1")
o = order(o1)
check("Webhook 200", r.status_code == 200, r.get_data(as_text=True))
check("Status refunded, refunded_at und Karenzbeginn gesetzt", o["status"] == "refunded" and o["refunded_at"] and o["past_due_at"], str(o))
check("Instance gesperrt mit Grund, nicht geloescht", o["inst_status"] == "suspended" and o["inst_reason"] == "Zahlung erstattet" and o["instance_id"])
check("Payment-Event processed mit Detail", pe("evt_ref_1")[0] == "processed" and "erstattet" in pe("evt_ref_1")[1], str(pe("evt_ref_1")))
check("Activity-Event order:refunded", events("order:refunded") == 1)
check("Kunde bekommt Mail", len(user_mails(o1)) == 1 and "erstattet" in user_mails(o1)[0]["subject"])
check("Admin-Alert (M58)", len(ops_mails()) == 1 and "Zahlung erstattet" in ops_mails()[0]["subject"] and o1 in ops_mails()[0]["body"], str(ops_mails()))
check("API: refunded_at, scheduled_deletion_at, disputed=false", o["dict"]["status"] == "refunded" and o["dict"]["refunded_at"].endswith("+00:00")
      and o["dict"]["scheduled_deletion_at"] and o["dict"]["disputed"] is False)
mail.outbox.clear()
r = refund(pi1, event_id="evt_ref_1")
check("gleiche Event-ID nochmal: Duplikat, keine zweite Wirkung", r.status_code == 200 and events("order:refunded") == 1 and not mail.outbox)
r = refund(pi1, event_id="evt_ref_1b")
check("neue Event-ID, schon erstattet: kein zweites Mal", order(o1)["status"] == "refunded" and not user_mails(o1)
      and events("order:refunded") == 1 and "bereits" in pe("evt_ref_1b")[1])
r = c.post(f"/api/admin/orders/{o1}/mark-paid", json={"payment_reference": "x"}, headers=AH)
check("mark-paid auf erstatteter Bestellung: 409", r.status_code == 409)
r = c.post(f"/api/client/orders/{o1}/cancel", headers=U1)
check("Kunde kuendigt erstattete Bestellung: 409", r.status_code == 409)

print("Karenzzeit und Loeschung im Tick")
grace = app.config["BILLING_GRACE_DAYS"]
now = datetime.utcnow()
with app.app_context():
    res = run_billing_tick(now + timedelta(days=grace - 1))
check("innerhalb der Karenzzeit: bleibt erstattet und gesperrt", order(o1)["status"] == "refunded" and order(o1)["inst_status"] == "suspended", str(res))
mail.outbox.clear()
with app.app_context():
    res = run_billing_tick(now + timedelta(days=grace, minutes=1))
check("nach der Karenzzeit: Instance geloescht, Bestellung expired", order(o1)["status"] == "expired" and order(o1)["instance_id"] is None and res["expired"] >= 1, str(res))
check("Mail 'Server beendet' nennt die Erstattung", any("Zahlung erstattet" in m["body"] for m in user_mails(o1)), str([m["body"] for m in user_mails(o1)]))

print("Teilerstattung und aeltere Zahlung")
o2, pi2 = paid_order()
mail.outbox.clear()
r = refund(pi2, full=False)
check("Teilerstattung: Bestellung bleibt aktiv, Instance laeuft", order(o2)["status"] == "active" and order(o2)["inst_status"] is None)
check("Event order:refunded (full=false) und Admin-Alert, keine Kundenmail", events("order:refunded") == 2 and len(ops_mails()) == 1 and not user_mails(o2))
r = c.post(f"/api/admin/orders/{o2}/mark-paid", json={"payment_reference": "pi_renew_2"}, headers=AH)
check("Verlaengerung verbucht", r.status_code == 200)
r = refund(pi2, full=True)
check("Vollerstattung der AELTEREN Zahlung beendet den Dienst nicht", order(o2)["status"] == "active" and order(o2)["inst_status"] is None)
r = refund("pi_renew_2", full=True)
check("Vollerstattung der letzten Zahlung (Referenz aus mark-paid): refunded", order(o2)["status"] == "refunded" and order(o2)["inst_status"] == "suspended")

print("Zuordnung")
o3, pi3 = paid_order()
r = refund("pi_unbekannt", event_id="evt_unknown")
check("unbekannte Zahlung: ignored mit Hinweis", r.status_code == 200 and pe("evt_unknown")[0] == "ignored" and "nicht gefunden" in pe("evt_unknown")[1])
r = post({"id": "ch_x", "object": "charge", "payment_intent": "pi_nope", "amount": 499, "currency": "eur",
          "amount_refunded": 499, "refunded": True, "metadata": {"order_uuid": o3}}, "charge.refunded", "evt_by_meta")
check("Zuordnung ersatzweise ueber metadata.order_uuid", order(o3)["status"] == "active" and pe("evt_by_meta")[0] == "processed")
check("... aber nur die letzte Zahlung zaehlt: andere Referenz = kein Dienstende", order(o3)["inst_status"] is None)

print("Bereits beendete Bestellung")
o4, pi4 = paid_order()
c.post(f"/api/client/orders/{o4}/cancel", headers=U1)
with app.app_context():
    run_billing_tick(datetime.utcnow() + timedelta(days=40))
    run_billing_tick(datetime.utcnow() + timedelta(days=40))
check("Vorbedingung: Bestellung expired", order(o4)["status"] == "expired", str(order(o4)["status"]))
r = refund(pi4, event_id="evt_ended")
check("Erstattung zu beendeter Bestellung: processed, Status bleibt expired", pe("evt_ended")[0] == "processed" and order(o4)["status"] == "expired")

print("Zahlungsstreit")
o5, pi5 = paid_order()
mail.outbox.clear()
r = dispute(pi5, "created", event_id="evt_dp_1")
o = order(o5)
check("dispute.created: disputed, Instance gesperrt, Status bleibt active", o["disputed"] and o["inst_status"] == "suspended"
      and o["inst_reason"] == "Zahlung angefochten" and o["status"] == "active", str(o))
check("Event order:disputed und Admin-Alert", events("order:disputed") == 1 and len(ops_mails()) == 1 and "Zahlungsstreit eröffnet" in ops_mails()[0]["subject"])
check("API: disputed=true", o["dict"]["disputed"] is True)
r = dispute(pi5, "created", event_id="evt_dp_1")
check("Wiederzustellung: keine zweite Wirkung", events("order:disputed") == 1)
r = dispute(pi5, "closed", status="won", event_id="evt_dp_2")
o = order(o5)
check("dispute.closed (gewonnen): Flag weg, Instance entsperrt, Status active", not o["disputed"] and o["inst_status"] is None and o["status"] == "active", str(o))
check("Event order:disputed (Ergebnis) und Admin-Entwarnung-Info", events("order:disputed") == 2 and pe("evt_dp_2")[0] == "processed")

o6, pi6 = paid_order()
dispute(pi6, "created", event_id="evt_dp_3")
mail.outbox.clear()
dispute(pi6, "closed", status="lost", event_id="evt_dp_4")
o = order(o6)
check("dispute.closed (verloren): wie erstattet, Instance bleibt gesperrt, Karenzzeit", o["status"] == "refunded" and o["inst_status"] == "suspended"
      and o["past_due_at"] and o["disputed"])
check("Kunde bekommt keine Fehlinformation: Mail nennt 'erstattet' nicht, Admin wird informiert", len(ops_mails()) == 1 and "verloren" in ops_mails()[0]["subject"], str(ops_mails()))

print("Bestehende Sperre bleibt")
o7, pi7 = paid_order()
with app.app_context():
    from app.domain.instances.service import suspend_instance
    inst = db.session.get(Instance, Order.query.filter_by(uuid=o7).first().instance_id)
    suspend_instance(inst, ids["admin"], "Missbrauch")
refund(pi7)
check("Admin-Sperre nicht ueberschrieben, Bestellung trotzdem refunded", order(o7)["status"] == "refunded" and order(o7)["inst_reason"] == "Missbrauch")

print("Dispute gewonnen hebt nur die eigene Sperre auf")
o8, pi8 = paid_order()
with app.app_context():
    inst = db.session.get(Instance, Order.query.filter_by(uuid=o8).first().instance_id)
    suspend_instance(inst, ids["admin"], "Missbrauch")
dispute(pi8, "created")
dispute(pi8, "closed", status="won")
check("Admin-Sperre bleibt nach gewonnenem Streit", order(o8)["inst_status"] == "suspended" and order(o8)["inst_reason"] == "Missbrauch" and not order(o8)["disputed"])

print("Webhook-Katalog und Migration")
from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS
check("Events im Webhook-Katalog", "order:refunded" in WEBHOOK_EVENTS and "order:disputed" in WEBHOOK_EVENTS)
from alembic.config import Config
from alembic.script import ScriptDirectory
cfg = Config()
cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "migrations"))
sd = ScriptDirectory.from_config(cfg)
check("genau ein Migrations-Head: s9n0o1p2q3r4", sd.get_heads() == ["s9n0o1p2q3r4"], str(sd.get_heads()))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
