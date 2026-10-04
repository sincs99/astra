"""M63 – Umsatzstatistik GET /api/admin/stats/revenue (auf Basis der Belege, Erstattungen getrennt)."""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.billing.models import Receipt
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order
from app.domain.billing.service import run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.infrastructure import mail
from app.domain.activity.models import ActivityLog
from app.domain.billing.models import Receipt
from unittest import mock
import json, subprocess, sqlite3, tempfile
from app.domain.billing import receipts
from app.domain.billing.models import Receipt, InvoiceCounter
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


def product(memory, name, price, currency="EUR"):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": memory, "disk": 500,
                                             "cpu": 50, "price_cents": price, "currency": currency, "billing_period_days": 30,
                                             **({"max_instances_per_user": 3} if price == 0 else {})}, headers=AH)
    return r.json["id"]


def new_order(pid, hdr=U1):
    n[0] += 1
    return c.post("/api/client/orders", json={"product_id": pid, "name": f"s{n[0]}"}, headers=hdr).json["uuid"]


def pay(ou, ref):
    return c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def stats(q=""):
    return c.get("/api/admin/stats/revenue" + q, headers=AH)


def backdate(order_uuid, days, ref=None):
    """Datiert die Belege einer Bestellung (optional nur den zur Referenz) zurueck."""
    with app.app_context():
        oid = Order.query.filter_by(uuid=order_uuid).first().id
        q = Receipt.query.filter_by(order_id=oid)
        if ref:
            q = q.filter_by(payment_reference=ref)
        for rc in q.all():
            rc.issued_at = datetime.utcnow() - timedelta(days=days)
        db.session.commit()


small = product(300, "Klein", 499)
mid = product(300, "Mittel", 1000)
usd = product(300, "Dollar", 250, "USD")
free = product(100, "Gratis", 0)

print("Leer")
r = stats()
check("ohne Zahlungen: leere Summen, Standard 30 Tage", r.status_code == 200 and r.json["days"] == 30 and r.json["by_currency"] == {}
      and r.json["paid_count"] == 0 and r.json["renewals_count"] == 0 and r.json["refunded_cents_by_currency"] == {}, str(r.json))
check("since mit UTC-Suffix", r.json["since"].endswith("+00:00"))
check("Vorzeitraum leer (M66)", r.json["prev_by_currency"] == {} and r.json["prev_paid_count"] == 0
      and r.json["prev_renewals_count"] == 0 and r.json["prev_since"] < r.json["since"], str(r.json))

print("Zahlungen (Belege)")
o1 = new_order(small); pay(o1, "p1")
o2 = new_order(mid); pay(o2, "p2")
o3 = new_order(usd); pay(o3, "p3")
o4 = new_order(free)
pay(o1, "p1-renew")     # Verlaengerung (499)
pay(o1, "p1-renew")     # Wiederholung: kein zweiter Beleg, zaehlt nicht doppelt
r = stats().json
check("Summen je Waehrung (499+1000+499 EUR, 250 USD)", r["by_currency"] == {"EUR": 1998, "USD": 250}, str(r))
check("3 Erstzahlungen, 1 Verlaengerung", r["paid_count"] == 3 and r["renewals_count"] == 1, str(r))
with app.app_context():
    run_billing_tick(datetime.utcnow() + timedelta(days=31))
check("Gratis-Paket und Gratis-Auto-Verlaengerung zaehlen nicht", stats().json["by_currency"] == {"EUR": 1998, "USD": 250})

print("Zeitraum")
backdate(o2, 40)
r = stats().json
check("Beleg von vor 40 Tagen faellt aus den 30 Tagen", r["by_currency"] == {"EUR": 998, "USD": 250} and r["paid_count"] == 2, str(r))
check("M66: er liegt im Vorzeitraum (30 bis 60 Tage)", r["prev_by_currency"] == {"EUR": 1000} and r["prev_paid_count"] == 1
      and r["prev_renewals_count"] == 0, str(r))
check("M66: days=20 hat ihn weder im Zeitraum noch im Vorzeitraum", stats("?days=20").json["prev_by_currency"] == {})
check("M66: days=60 hat einen leeren Vorzeitraum", stats("?days=60").json["prev_by_currency"] == {})
r = stats("?days=60").json
check("days=60 enthaelt ihn wieder", r["by_currency"]["EUR"] == 1998 and r["paid_count"] == 3 and r["days"] == 60, str(r))
backdate(o1, 3, ref="p1-renew")
r = stats("?days=2").json
check("days=2: nur Belege der letzten 2 Tage", r["renewals_count"] == 0 and r["paid_count"] == 2, str(r))
check("days=7: Verlaengerung von vor 3 Tagen zaehlt", stats("?days=7").json["renewals_count"] == 1)
backdate(o1, 20, ref="p1")
backdate(o1, 40, ref="p1-renew")
r = stats("?days=30").json
check("Erstzahlung im Zeitraum, Verlaengerung davor: paid 2 (o1, o3), renewals 0", r["paid_count"] == 2 and r["renewals_count"] == 0, str(r))
check("Verlaengerung im Zeitraum, Erstzahlung davor: zaehlt als Verlaengerung", (backdate(o1, 20, ref="p1-renew"), backdate(o1, 40, ref="p1"),
      stats("?days=30").json["renewals_count"] == 1 and stats("?days=30").json["paid_count"] == 1)[-1])

print("Erstattungen getrennt")
with app.app_context():
    from app.domain.activity.service import log_event
    oid3 = Order.query.filter_by(uuid=o3).first().id
    log_event(event="order:refunded", actor_id=None, subject_id=oid3, subject_type="order",
              properties={"refunded_cents": 100, "amount_cents": 250, "currency": "USD", "full": False})
    log_event(event="order:refunded", actor_id=None, subject_id=oid3, subject_type="order",
              properties={"amount_cents": 250, "currency": "USD", "full": True})
    log_event(event="order:refunded", actor_id=None, subject_id=oid3, subject_type="order", properties={"full": True})  # ohne Betrag: ignoriert
r = stats().json
check("Erstattungen je Waehrung (100 + 250 USD), nicht verrechnet", r["refunded_cents_by_currency"] == {"USD": 350} and r["by_currency"]["USD"] == 250, str(r))
with app.app_context():
    for e in ActivityLog.query.filter_by(event="order:refunded").all():
        e.created_at = datetime.utcnow() - timedelta(days=100)
    db.session.commit()
check("alte Erstattungen ausserhalb des Zeitraums zaehlen nicht", stats().json["refunded_cents_by_currency"] == {})

print("M73: Erstattungen aus Gutschriften")
with app.app_context():
    from app.domain.billing.receipts import issue_credit_note
    from app.domain.billing.models import Receipt
    ordr = Order.query.filter_by(uuid=o3).first()
    inv3 = Receipt.query.filter_by(order_id=ordr.id, kind="invoice").first()
    # Stripe meldet kumuliert: erst 100, dann 250 -> Gutschriften 100 + 150, Events beider tragen `credit_note`
    n1 = issue_credit_note(ordr, inv3, 100, "evt_c1")
    n2 = issue_credit_note(ordr, inv3, 250, "evt_c2")
    for ev_amount, n in ((100, n1), (250, n2)):
        log_event(event="order:refunded", actor_id=None, subject_id=ordr.id, subject_type="order",
                  properties={"refunded_cents": ev_amount, "amount_cents": 250, "currency": "USD", "credit_note": n.number})
    log_event(event="order:refunded", actor_id=None, subject_id=ordr.id, subject_type="order",
              properties={"refunded_cents": 40, "amount_cents": 250, "currency": "USD", "credit_note": None})
r = stats().json
check("kumulierte Teilerstattungen zaehlen nur den Zuwachs (100 + 150 = 250 USD, nicht 350)",
      r["refunded_cents_by_currency"] == {"USD": 250}, str(r["refunded_cents_by_currency"]))
check("Gutschriften zaehlen nicht in by_currency", r["by_currency"]["USD"] == 250)
with app.app_context():
    for n in Receipt.query.filter_by(kind="credit_note").all():
        n.issued_at = datetime.utcnow() - timedelta(days=100)
    db.session.commit()
check("alte Gutschriften ausserhalb des Zeitraums zaehlen nicht", stats().json["refunded_cents_by_currency"] == {})

print("Eingabe und Rechte")
check("days=abc: 400", stats("?days=abc").status_code == 400)
check("days=0: 400", stats("?days=0").status_code == 400)
check("days=366: 400", stats("?days=366").status_code == 400)
check("days=365: ok", stats("?days=365").status_code == 200)
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Anmeldung: 401", c.get("/api/admin/stats/revenue").status_code == 401)
check("Kunde: 403", c.get("/api/admin/stats/revenue", headers=U1).status_code == 403)
check("Admin: 200", c.get("/api/admin/stats/revenue", headers=AH).status_code == 200)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
