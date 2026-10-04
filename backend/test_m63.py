"""M63 – Umsatzstatistik GET /api/admin/stats/revenue."""

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
from app.domain.activity.models import ActivityLog
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


def backdate(event, days, order_uuid=None):
    """Datiert die Ereignisse eines Typs (optional einer Bestellung) zurueck."""
    with app.app_context():
        q = ActivityLog.query.filter_by(event=event)
        if order_uuid:
            q = q.filter_by(subject_id=Order.query.filter_by(uuid=order_uuid).first().id)
        for e in q.all():
            e.created_at = datetime.utcnow() - timedelta(days=days)
        db.session.commit()


small = product(300, "Klein", 499)
mid = product(300, "Mittel", 1000)
usd = product(300, "Dollar", 250, "USD")
free = product(100, "Gratis", 0)

print("Leer")
r = stats()
check("ohne Zahlungen: leere Summen, Standard 30 Tage", r.status_code == 200 and r.json["days"] == 30 and r.json["by_currency"] == {}
      and r.json["paid_count"] == 0 and r.json["renewals_count"] == 0 and r.json["refunded_count"] == 0, str(r.json))
check("since mit UTC-Suffix", r.json["since"].endswith("+00:00"))

print("Zahlungen")
o1 = new_order(small); pay(o1, "p1")
o2 = new_order(mid); pay(o2, "p2")
o3 = new_order(usd); pay(o3, "p3")
o4 = new_order(free)
pay(o1, "p1-renew")     # Verlaengerung (499)
pay(o1, "p1-renew")     # Wiederholung: zaehlt nicht doppelt
r = stats().json
check("Summen je Waehrung (499+1000+499 EUR, 250 USD)", r["by_currency"] == {"EUR": 1998, "USD": 250}, str(r))
check("3 Erstzahlungen, 1 Verlaengerung", r["paid_count"] == 3 and r["renewals_count"] == 1, str(r))
with app.app_context():
    run_billing_tick(datetime.utcnow() + timedelta(days=31))
check("Gratis-Paket und Gratis-Auto-Verlaengerung zaehlen nicht", stats().json["by_currency"] == {"EUR": 1998, "USD": 250})

print("Zeitraum")
backdate("order:paid", 40, o2)
r = stats().json
check("Zahlung vor 40 Tagen faellt aus den 30 Tagen", r["by_currency"] == {"EUR": 998, "USD": 250} and r["paid_count"] == 2, str(r))
r = stats("?days=60").json
check("days=60 enthaelt sie wieder", r["by_currency"]["EUR"] == 1998 and r["paid_count"] == 3 and r["days"] == 60, str(r))
backdate("order:renewed", 3, o1)
check("days=2: nur Ereignisse der letzten 2 Tage", stats("?days=2").json["renewals_count"] == 0 and stats("?days=2").json["paid_count"] == 2)
check("days=7: Verlaengerung von vor 3 Tagen zaehlt", stats("?days=7").json["renewals_count"] == 1)

print("Erstattungen")
with app.app_context():
    from app.domain.activity.service import log_event
    log_event(event="order:refunded", actor_id=None, subject_id=Order.query.filter_by(uuid=o3).first().id, subject_type="order")
check("refunded_count zaehlt, zieht aber nichts ab", stats().json["refunded_count"] == 1 and stats().json["by_currency"]["USD"] == 250)

print("Eingabe und Rechte")
check("days=abc: 400", stats("?days=abc").status_code == 400)
check("days=0: 400", stats("?days=0").status_code == 400)
check("days=99999: 400", stats("?days=99999").status_code == 400)
check("days=3650: ok", stats("?days=3650").status_code == 200)
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Anmeldung: 401", c.get("/api/admin/stats/revenue").status_code == 401)
check("Kunde: 403", c.get("/api/admin/stats/revenue", headers=U1).status_code == 403)
check("Admin: 200", c.get("/api/admin/stats/revenue", headers=AH).status_code == 200)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
