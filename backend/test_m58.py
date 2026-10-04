"""M58 – Aktive Admin-Benachrichtigung (Mail/Webhook, Entprellen, Entwarnung, Zahlungsprobleme, CLI)."""

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
import json, logging, subprocess, tempfile
from unittest import mock
from app.domain.billing.payments import PaymentEvent
from app.domain.system import alerts
from app.domain.system.models import SystemState
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


WEBHOOK = "https://discord.test/api/webhooks/123/SECRETTOKEN"
D = timedelta


def product(memory, name):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": memory, "disk": 500,
                                             "cpu": 50, "price_cents": 100, "billing_period_days": 30}, headers=AH)
    return r.json["id"]


def paid(pid, ref):
    n[0] += 1
    ou = c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=U1).json["uuid"]
    return ou, c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def ops_mails():
    return [m for m in mail.outbox if m["to"] == "ops@t.local"]


def run_checks(now=None):
    with app.app_context():
        return alerts.check_alerts(now)


def set_state(key, value):
    with app.app_context():
        s = db.session.get(SystemState, key)
        if s is None:
            db.session.add(SystemState(key=key, value=value))
        else:
            s.value = value
        db.session.commit()


def fresh_tick(at=None):
    set_state("billing_tick", {"last_run_at": iso_utc(at or datetime.utcnow()), "summary": {"errors": []}})


def state_value(key):
    with app.app_context():
        return dict(db.session.get(SystemState, key).value)


def backdate_wait(hours):
    with app.app_context():
        o = Order.query.filter_by(uuid=o_wait).first()
        o.paid_at = datetime.utcnow() - timedelta(hours=hours)
        db.session.commit()


big = product(900, "Gross")
paid(big, "a0")
o_wait, r = paid(big, "a1")  # kein Platz -> wartet
check("zweite Bestellung wartet", r.status_code == 409)
backdate_wait(30)
set_state("billing_tick", {"last_run_at": iso_utc(datetime.utcnow()), "summary": {"errors": []}})  # Tick laeuft

print("Nichts konfiguriert")
mail.outbox.clear()
with mock.patch.object(alerts.requests, "post") as post:
    res = run_checks()
check("ohne Kanal: nichts versendet, Zustand wird trotzdem bewertet", not mail.outbox and not post.called
      and res["waiting_orders"] == "suppressed", str(res))

print("Mail-Kanal")
app.config["ADMIN_ALERT_EMAIL"] = "ops@t.local, zweiter@t.local"
mail.outbox.clear()
res = run_checks()
check("Stoerung: Mail an beide Adressen", res["waiting_orders"] == "alert" and len(ops_mails()) == 1
      and len([m for m in mail.outbox if m["to"] == "zweiter@t.local"]) == 1, str(res))
check("Text nennt Anzahl und Stunden", "30.0 Stunden" in ops_mails()[0]["body"] and "1 bezahlte" in ops_mails()[0]["body"])
mail.outbox.clear()
res = run_checks()
check("zweiter Lauf: entprellt, keine Mail", res["waiting_orders"] == "suppressed" and not mail.outbox, str(res))
mail.outbox.clear()
fresh_tick(datetime.utcnow() + D(minutes=300))
res = run_checks(datetime.utcnow() + D(minutes=300))
check("vor Ablauf des Cooldowns (360 min): weiter still", not mail.outbox, str(res))
fresh_tick(datetime.utcnow() + D(minutes=361))
res = run_checks(datetime.utcnow() + D(minutes=361))
check("nach dem Cooldown: Erinnerung", len(ops_mails()) == 1, str(res))
fresh_tick()  # Tick laeuft wieder normal

print("Entwarnung")
with app.app_context():
    db.session.get(Agent, ids["agent"]).memory_total = 4096
    db.session.commit()
    run_billing_tick()  # stellt die wartende Bestellung bereit; Alerts laufen am Ende des Ticks
ms = ops_mails()
check("Entwarnung einmalig nach Bereitstellung", len([m for m in ms if "Entwarnung" in m["subject"]]) == 1, str([m["subject"] for m in ms]))
mail.outbox.clear()
run_checks()
check("danach keine weitere Entwarnung", not ops_mails())
backdate_wait(0)

print("Entwarnung abschaltbar")
set_state("alert:waiting_orders", {"active": True, "last_sent_at": iso_utc(datetime.utcnow())})
app.config["ADMIN_ALERT_RECOVERY"] = False
mail.outbox.clear()
run_checks()
check("ADMIN_ALERT_RECOVERY=false: Zustand zurueckgesetzt, keine Mail", not ops_mails()
      and not state_value("alert:waiting_orders")["active"])
app.config["ADMIN_ALERT_RECOVERY"] = True

print("Billing-Tick ausgefallen")
mail.outbox.clear()
set_state("billing_tick", {"last_run_at": iso_utc(datetime.utcnow() - D(hours=2)), "summary": {"errors": []}})
with app.app_context():
    run_billing_tick()
subs = [m["subject"] for m in ops_mails()]
check("laufender Tick meldet den Ausfall und danach die Entwarnung",
      "Astra: Billing-Tick läuft nicht" in subs and "Astra: Entwarnung – Billing-Tick läuft nicht" in subs, str(subs))
check("Ausfall-Mail nennt die Dauer", any("vor 120 Minuten" in m["body"] or "vor 119 Minuten" in m["body"] for m in ops_mails()))

print("Fehler im Tick")
mail.outbox.clear()
with app.app_context():
    from app.domain.billing.service import _record_tick
    _record_tick({"errors": [{"order": "x", "error": "Boom"}]}, datetime.utcnow())
res = run_checks()
check("Fehler im letzten Tick: Alert", res["billing_errors"] == "alert" and any("Billing-Tick mit Fehlern" in m["subject"] for m in ops_mails()), str(res))
with app.app_context():
    _record_tick({"errors": []}, datetime.utcnow())
mail.outbox.clear()
run_checks()
check("sauberer Tick: Entwarnung", any("Entwarnung" in m["subject"] and "Fehlern" in m["subject"] for m in ops_mails()))

print("Webhook-Kanal")
app.config["ADMIN_ALERT_EMAIL"] = ""
app.config["ADMIN_ALERT_WEBHOOK_URL"] = WEBHOOK
with mock.patch.object(alerts.requests, "post") as post:
    post.return_value.status_code = 204
    with app.app_context():
        res = alerts.send_admin_alert("Astra: Titel", "Text")
    kwargs = post.call_args.kwargs
check("JSON-POST an die URL mit content/text/subject", post.call_args.args[0] == WEBHOOK and "Astra: Titel" in kwargs["json"]["content"]
      and kwargs["json"]["text"] == kwargs["json"]["content"] and kwargs["json"]["subject"] == "Astra: Titel" and kwargs["timeout"] <= 10
      and res == {"email": None, "webhook": True}, str(res))
with mock.patch.object(alerts.requests, "post") as post:
    post.return_value.status_code = 500
    with app.app_context():
        res = alerts.send_admin_alert("a", "b")
check("HTTP 500: webhook=False, keine Ausnahme", res["webhook"] is False)
records = []
class H(logging.Handler):
    def emit(self, rec): records.append(rec.getMessage())
h = H(); logging.getLogger("app.domain.system.alerts").addHandler(h)
with mock.patch.object(alerts.requests, "post", side_effect=RuntimeError(f"boom {WEBHOOK}")):
    with app.app_context():
        res = alerts.send_admin_alert("a", "b")
logging.getLogger("app.domain.system.alerts").removeHandler(h)
check("Netzwerkfehler: webhook=False, URL/Token nicht im Log", res["webhook"] is False and records and not any("SECRETTOKEN" in x for x in records), str(records))
with mock.patch.object(alerts.requests, "post") as post:
    post.return_value.status_code = 200
    with app.app_context():
        alerts.send_admin_alert("a", "x" * 5000)
check("langer Text wird auf 1900 Zeichen gekuerzt", len(post.call_args.kwargs["json"]["content"]) <= 1900)

print("Zahlungsprobleme")
set_state("alert:payment:x", {})
app.config["ADMIN_ALERT_WEBHOOK_URL"] = ""
app.config["ADMIN_ALERT_EMAIL"] = "ops@t.local"
ou = c.post("/api/client/orders", json={"product_id": big, "name": "pay1"}, headers=U1).json["uuid"]
mail.outbox.clear()
with app.app_context():
    ev = PaymentEvent("evt_a", "checkout.session.completed", "paid", order_uuid=ou, payment_reference="pi_1", amount_cents=1, currency="EUR")
    res = billing.process_payment_events("stripe", [ev])
check("mismatch: Event gespeichert und Admin-Mail", res[0]["status"] == "mismatch" and len(ops_mails()) == 1
      and "weicht" in ops_mails()[0]["subject"] and ou in ops_mails()[0]["body"] and "evt_a" in ops_mails()[0]["body"], str(ops_mails()))
mail.outbox.clear()
with app.app_context():
    ev2 = PaymentEvent("evt_b", "checkout.session.completed", "paid", order_uuid=ou, payment_reference="pi_2", amount_cents=2, currency="EUR")
    billing.process_payment_events("stripe", [ev2])
    billing.process_payment_events("stripe", [ev])  # Wiederzustellung: Duplikat
check("zweites mismatch derselben Bestellung und Duplikat: keine weitere Mail", not ops_mails())
# unapplied: stornierte Bestellung
ou2 = c.post("/api/client/orders", json={"product_id": big, "name": "pay2"}, headers=U1).json["uuid"]
c.post(f"/api/client/orders/{ou2}/cancel", headers=U1)
mail.outbox.clear()
with app.app_context():
    ev3 = PaymentEvent("evt_c", "checkout.session.completed", "paid", order_uuid=ou2, payment_reference="pi_3", amount_cents=100, currency="EUR")
    res = billing.process_payment_events("stripe", [ev3])
check("unapplied: Admin-Mail", res[0]["status"] == "unapplied" and len(ops_mails()) == 1 and "nicht verbucht" in ops_mails()[0]["subject"])
# Mailfehler stoert die Verarbeitung nicht
ou3 = c.post("/api/client/orders", json={"product_id": big, "name": "pay3"}, headers=U1).json["uuid"]
with mock.patch("app.infrastructure.mail.send_mail", side_effect=RuntimeError("smtp down")):
    with app.app_context():
        ev4 = PaymentEvent("evt_d", "checkout.session.completed", "paid", order_uuid=ou3, payment_reference="pi_4", amount_cents=5, currency="EUR")
        res = billing.process_payment_events("stripe", [ev4])
check("Mailfehler: Ereignis trotzdem verarbeitet", res[0]["status"] == "mismatch")
mail.outbox.clear()
with app.app_context():
    ok_ev = PaymentEvent("evt_e", "checkout.session.completed", "paid", order_uuid=ou3, payment_reference="pi_5", amount_cents=100, currency="EUR")
    res = billing.process_payment_events("stripe", [ok_ev])
check("normale Zahlung: keine Admin-Mail", res[0]["status"] == "processed" and not ops_mails())

print("CLI")
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    base = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{tmp}/t.db", "RUNNER_ADAPTER": "stub"}
    base.pop("ADMIN_ALERT_EMAIL", None); base.pop("ADMIN_ALERT_WEBHOOK_URL", None)
    subprocess.run([sys.executable, "-c", "from app import create_app;from app.extensions import db;a=create_app()\n"
                    "with a.app_context(): db.create_all()"], env=base, capture_output=True, check=True, cwd=cwd)
    none = subprocess.run([sys.executable, "cli.py", "alert-test"], env=base, capture_output=True, text=True, cwd=cwd)
    chk = subprocess.run([sys.executable, "cli.py", "alert-check"], env=base, capture_output=True, text=True, cwd=cwd)
    bad = subprocess.run([sys.executable, "cli.py", "alert-test"], env={**base, "ADMIN_ALERT_WEBHOOK_URL": "http://127.0.0.1:9/x"},
                         capture_output=True, text=True, cwd=cwd)
check("alert-test ohne Kanal: Exit 1 mit Hinweis", none.returncode == 1 and "Kein Kanal" in none.stdout, none.stdout + none.stderr[-200:])
check("alert-check: Exit 0, JSON mit den Ausloesern", chk.returncode == 0 and set(json.loads(chk.stdout.splitlines()[-1])) ==
      {"billing_tick", "billing_errors", "waiting_orders"}, chk.stdout + chk.stderr[-200:])
check("alert-test mit unerreichbarem Webhook: Exit 1", bad.returncode == 1 and '"webhook": false' in bad.stdout, bad.stdout + bad.stderr[-200:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
