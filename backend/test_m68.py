"""M68 – payment_events speichert Betrag und Waehrung des Anbieter-Ereignisses und gibt sie im Admin-Endpunkt aus."""

import hashlib
import sqlite3
import subprocess
import tempfile
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


def events(status=None):
    q = "?limit=500" + (f"&status={status}" if status else "")
    return {e["event_id"]: e for e in c.get("/api/admin/payment-events" + q, headers=AH).json}


def row_amount(event_id):
    e = events().get(event_id)
    return (e["amount_cents"], e["currency"]) if e else None


print("Zahlung")
o1, pi1 = paid_order()  # Event "evt_1" der Hilfsfunktion: 499 EUR
first = [k for k in events()][0]
check("bezahltes Ereignis: Betrag und Waehrung (499 EUR) in der Liste", row_amount(first) == (499, "EUR"), str(events()))
check("API-Felder amount_cents und currency vorhanden", all({"amount_cents", "currency"} <= set(e) for e in events().values()))

print("Abweichender Betrag (mismatch)")
n[0] += 1
ou = c.post("/api/client/orders", json={"product_id": PID, "name": "mm"}, headers=U1).json["uuid"]
post({"id": "cs_mm", "object": "checkout.session", "payment_status": "paid", "payment_intent": "pi_mm", "amount_total": 100,
      "currency": "eur", "metadata": {"order_uuid": ou}, "client_reference_id": ou}, "checkout.session.completed", "evt_mm")
check("mismatch speichert den tatsaechlich gezahlten Betrag (nicht den erwarteten)", row_amount("evt_mm") == (100, "EUR") and events()["evt_mm"]["status"] == "mismatch")

print("Erstattungen und Streit")
o2, pi2 = paid_order()
refund(pi2, full=False, event_id="evt_part")
check("Teilerstattung: erstatteter Betrag (100), Waehrung", row_amount("evt_part") == (100, "EUR"), str(events().get("evt_part")))
refund(pi2, full=True, event_id="evt_full")
check("Vollerstattung: erstatteter Betrag (499)", row_amount("evt_full") == (499, "EUR"))
o3, pi3 = paid_order()
dispute(pi3, "created", event_id="evt_dp")
check("Streit: Betrag der angefochtenen Zahlung", row_amount("evt_dp") == (499, "EUR"))

print("Ereignisse ohne Betrag")
r = post({"id": "in_1", "object": "invoice"}, "invoice.created", "evt_ign")
check("ignoriertes Ereignis: amount_cents und currency sind null", events()["evt_ign"]["status"] == "ignored" and row_amount("evt_ign") == (None, None), str(events().get("evt_ign")))
r = post({"id": "cs_np", "object": "checkout.session", "payment_status": "unpaid", "payment_intent": "pi_np", "amount_total": 999,
          "currency": "eur", "metadata": {}}, "checkout.session.completed", "evt_unpaid")
check("noch nicht bezahlte Sitzung: ignoriert, ohne Betrag", row_amount("evt_unpaid") == (None, None))
r = refund("pi_unbekannt", event_id="evt_unk")
check("Erstattung ohne passende Bestellung: ignoriert, Betrag trotzdem festgehalten", events()["evt_unk"]["status"] == "ignored" and row_amount("evt_unk") == (499, "EUR"))

print("Altbestand und Wiederzustellung")
with app.app_context():
    row = PaymentEvent.query.filter_by(event_id=first).first()
    row.amount_cents = None
    row.currency = None
    db.session.commit()
check("Altbestand (NULL) bleibt NULL, solange nichts nachgezogen wird", row_amount(first) == (None, None))
with app.app_context():
    stale = PaymentEvent(event_id="evt_stale", provider="stripe", event_type="checkout.session.completed", order_uuid=None, status="received")
    db.session.add(stale)
    db.session.commit()
    from app.domain.billing import service as billing
    from app.domain.billing.payments import PaymentEvent as ProviderEvent
    billing.process_payment_events("stripe", [ProviderEvent("evt_stale", "checkout.session.completed", "paid", order_uuid="nix",
                                                            payment_reference="pi_x", amount_cents=777, currency="EUR")])
check("Wiederzustellung eines unfertigen Altereignisses (received, ohne Betrag) zieht den Betrag nach", row_amount("evt_stale") == (777, "EUR"))
r = events("mismatch")
check("Filter nach Status funktioniert weiter", set(r) == {"evt_mm"})

print("Migration")
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    dbp = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{dbp}", "RUNNER_ADAPTER": "stub", "FLASK_APP": "app:create_app"}
    subprocess.run([sys.executable, "-c", "from app import create_app;from app.extensions import db;a=create_app()\nwith a.app_context(): db.create_all()"],
                   env=env, check=True, capture_output=True, cwd=cwd)
    con = sqlite3.connect(dbp)
    con.execute("alter table payment_events drop column amount_cents")
    con.execute("alter table payment_events drop column currency")
    con.execute("insert into payment_events (event_id, provider, status) values ('evt_alt', 'stripe', 'processed')")
    con.commit()
    run = lambda *a: subprocess.run([sys.executable, "-m", "flask", "db", *a], env=env, capture_output=True, text=True, cwd=cwd)
    stamp = run("stamp", "w3r4s5t6u7v8")
    up = run("upgrade")
    cols = {r[1] for r in sqlite3.connect(dbp).execute("pragma table_info(payment_events)")}
    keep = sqlite3.connect(dbp).execute("select event_id, amount_cents, currency from payment_events").fetchall()
    up2 = run("upgrade")
    down = run("downgrade", "w3r4s5t6u7v8")
    cols_down = {r[1] for r in sqlite3.connect(dbp).execute("pragma table_info(payment_events)")}
    heads = run("heads")
check("stamp + upgrade ok, Spalten vorhanden, Altzeile unveraendert (NULL)", stamp.returncode == 0 and up.returncode == 0
      and {"amount_cents", "currency"} <= cols and keep == [("evt_alt", None, None)], up.stderr[-300:])
check("zweites upgrade (Inspector-Guard) ok", up2.returncode == 0)
check("downgrade entfernt beide Spalten", down.returncode == 0 and not ({"amount_cents", "currency"} & cols_down), down.stderr[-300:])
check("genau ein Migrations-Head", heads.stdout.count("(head)") == 1, heads.stdout[-100:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
