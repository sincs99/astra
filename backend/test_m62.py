"""M62 – Zahlungsbelege mit fortlaufender Nummer (Grundlage)."""

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


YEAR = datetime.utcnow().year
app.config["INVOICE_SELLER"] = "Beispiel Hosting\nMusterstr. 1\n12345 Musterstadt"
app.config["RECEIPT_FOOTER"] = "Kleinunternehmer ohne USt-Ausweis (Test)"


def product(memory, name, price=499):
    r = c.post("/api/admin/products", json={"name": name, "blueprint_id": ids["bp"], "memory": memory, "disk": 500,
                                             "cpu": 50, "price_cents": price, "billing_period_days": 30,
                                             **({"max_instances_per_user": 3} if price == 0 else {})}, headers=AH)
    return r.json["id"]


def new_order(pid, name=None, hdr=U1):
    n[0] += 1
    return c.post("/api/client/orders", json={"product_id": pid, "name": name or f"s{n[0]}"}, headers=hdr).json["uuid"]


def pay(ou, ref):
    return c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def numbers(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return [r.number for r in Receipt.query.filter_by(order_id=o.id).order_by(Receipt.id).all()]


small = product(300, "Klein")
big = product(9000, "Riesig")
free = product(100, "Gratis", price=0)

print("Nummernformat")
check("Standardformat gueltig", receipts.validate_number_format("AST-{year}-{seq:05d}") is None)
check("eigenes Format gueltig", receipts.validate_number_format("RE{year}/{seq}") is None)
check("ohne {seq}: ungueltig", receipts.validate_number_format("AST-{year}") is not None)
check("unbekanntes Feld: ungueltig", receipts.validate_number_format("{foo}-{seq}") is not None)
check("Attributzugriff: ungueltig", receipts.validate_number_format("{seq.real}") is not None and receipts.validate_number_format("{seq.__class__}") is not None)
check("kaputte Klammer: ungueltig", receipts.validate_number_format("AST-{seq") is not None)
check("zu lang: ungueltig", receipts.validate_number_format("x" * 70 + "{seq}") is not None)
from app.config import ProductionConfig
check("Produktions-Check meldet ungueltiges Format", any("INVOICE_NUMBER_FORMAT" in i for i in (type("C", (ProductionConfig,), {"INVOICE_NUMBER_FORMAT": "{year}"}).validate_production())))
check("Standard besteht den Produktions-Check", not any("INVOICE_NUMBER_FORMAT" in i for i in ProductionConfig.validate_production()))

print("Belege entstehen mit der Zahlung")
o1 = new_order(small, name="Mein <b>Server</b>")
check("Bestellen allein: kein Beleg", numbers(o1) == [])
r = pay(o1, "pi_1")
check("erste Zahlung: Beleg 00001", r.status_code == 200 and numbers(o1) == [f"AST-{YEAR}-00001"], str(numbers(o1)))
r = pay(o1, "pi_1")
check("dieselbe Referenz nochmal: kein zweiter Beleg", numbers(o1) == [f"AST-{YEAR}-00001"])
r = pay(o1, "pi_2")
check("Verlaengerung: Beleg 00002 an derselben Bestellung", numbers(o1) == [f"AST-{YEAR}-00001", f"AST-{YEAR}-00002"], str(numbers(o1)))
o2 = new_order(small)
pay(o2, "pi_3")
check("naechste Bestellung: 00003 (lueckenlos, fortlaufend)", numbers(o2) == [f"AST-{YEAR}-00003"])
o3 = new_order(free)
check("kostenloses Paket: kein Beleg", numbers(o3) == [])
with app.app_context():
    run_billing_tick(datetime.utcnow() + timedelta(days=31))
check("automatische Gratis-Verlaengerung: kein Beleg", numbers(o3) == [])

print("Kein Platz: Zahlung gebucht, Beleg trotzdem")
o4 = new_order(big)
r = pay(o4, "pi_4")
check("409 (kein Platz), aber Beleg 00004", r.status_code == 409 and numbers(o4) == [f"AST-{YEAR}-00004"], str(numbers(o4)))
r = pay(o4, "pi_4")
check("erneuter Versuch: kein zweiter Beleg", numbers(o4) == [f"AST-{YEAR}-00004"])

print("Fehler verbrauchen keine Nummer")
o5 = new_order(small)
with mock.patch.object(receipts, "_number_format", side_effect=RuntimeError("kaputt")):
    r = pay(o5, "pi_5")
check("Beleg-Fehler blockiert die Zahlung nicht", r.status_code == 200 and numbers(o5) == [])
with app.app_context():
    check("Zaehler nach dem Fehler unveraendert (4)", db.session.get(InvoiceCounter, str(YEAR)).last_number == 4)
    rec = receipts.issue_receipt(Order.query.filter_by(uuid=o5).first(), "pi_5")
    rec_number = rec.number if rec else None
check("naechster erfolgreicher Beleg ist 00005: keine Luecke", rec_number == f"AST-{YEAR}-00005", str(rec_number))

print("Jahreswechsel und eigenes Format")
with app.app_context():
    nxt = receipts.issue_receipt(Order.query.filter_by(uuid=o1).first(), "pi_jahr", now=datetime(YEAR + 1, 1, 2, 9, 0)).number
    app.config["INVOICE_NUMBER_FORMAT"] = "RE{year}/{seq}"
    nxt2 = receipts.issue_receipt(Order.query.filter_by(uuid=o1).first(), "pi_format", now=datetime(YEAR + 1, 1, 3)).number
    app.config["INVOICE_NUMBER_FORMAT"] = "{year}"
    fallback = receipts.issue_receipt(Order.query.filter_by(uuid=o1).first(), "pi_kaputt", now=datetime(YEAR + 1, 1, 4)).number
    app.config["INVOICE_NUMBER_FORMAT"] = "AST-{year}-{seq:05d}"
check("neues Jahr beginnt bei 00001", nxt == f"AST-{YEAR + 1}-00001", nxt)
check("eigenes Format RE{year}/{seq}", nxt2 == f"RE{YEAR + 1}/2", nxt2)
check("ungueltiges Format: Standardformat statt Fehler", fallback == f"AST-{YEAR + 1}-00003", fallback)

print("Sichtbarkeit in der Bestellung")
d = c.get(f"/api/client/orders/{o2}", headers=U1).json
check("Kunde sieht receipts mit Nummer, Datum, Betrag", d["receipts"] == [{"number": f"AST-{YEAR}-00003", "issued_at": d["receipts"][0]["issued_at"],
                                                                         "amount_cents": 499, "currency": "EUR", "kind": "invoice"}] and d["receipts"][0]["issued_at"].endswith("+00:00"), str(d["receipts"]))
check("Liste enthaelt receipts je Bestellung", all("receipts" in x for x in c.get("/api/client/orders", headers=U1).json))
check("Admin-Liste enthaelt receipts", all("receipts" in x for x in c.get("/api/admin/orders", headers=AH).json))

print("Beleg abrufen")
r = c.get(f"/api/client/orders/{o1}/receipt", headers=U1)
html_body = r.get_data(as_text=True)
check("HTML ist der Standard, neuester Beleg", r.status_code == 200 and r.mimetype == "text/html" and f"AST-{YEAR + 1}-00003" in html_body, html_body[:200])
r = c.get(f"/api/client/orders/{o1}/receipt?number=AST-{YEAR}-00001", headers=U1)
html_body = r.get_data(as_text=True)
check("?number= waehlt einen Beleg", f"AST-{YEAR}-00001" in html_body and "4,99 EUR" in html_body and "Leistungszeitraum" in html_body)
check("Anbieter, Kunde, Referenz und Fusszeile im Beleg", all(x in html_body for x in ["Beispiel Hosting", "Musterstr. 1", "k1", "k1@t.local", "pi_1", "Kleinunternehmer ohne USt-Ausweis"]))
check("Rechnung ohne USt: Kleinunternehmer-Hinweis (M70)", "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." in html_body and "<h1>Rechnung</h1>" in html_body)
check("Servername ist HTML-escaped", "&lt;b&gt;Server&lt;/b&gt;" in html_body and "<b>Server</b>" not in html_body)
check("Sicherheits-Header", r.headers["X-Content-Type-Options"] == "nosniff" and "default-src 'none'" in r.headers["Content-Security-Policy"]
      and "no-store" in r.headers["Cache-Control"] and "charset=utf-8" in r.headers["Content-Type"])
r = c.get(f"/api/client/orders/{o1}/receipt?format=text&number=AST-{YEAR}-00002", headers=U1)
check("format=text: text/plain mit Nummer und Betrag", r.mimetype == "text/plain" and "Rechnungsnummer: AST-%d-00002" % YEAR in r.get_data(as_text=True)
      and "Betrag: 4,99 EUR" in r.get_data(as_text=True) and "RECHNUNG" in r.get_data(as_text=True))
r = c.get(f"/api/client/orders/{o1}/receipt?format=json&number=AST-{YEAR}-00001", headers=U1)
check("format=json: Felder", r.status_code == 200 and r.json["number"] == f"AST-{YEAR}-00001" and r.json["amount_cents"] == 499
      and r.json["product_name"] == "Klein" and r.json["customer"]["username"] == "k1" and r.json["payment_reference"] == "pi_1", str(r.json))
check("unbekannte Nummer: 404", c.get(f"/api/client/orders/{o1}/receipt?number=AST-0-1", headers=U1).status_code == 404)
check("Bestellung ohne Beleg: 404", c.get(f"/api/client/orders/{o3}/receipt", headers=U1).status_code == 404)
check("fremde Bestellung: 404", c.get(f"/api/client/orders/{o1}/receipt", headers=U2).status_code == 404)
check("unbekannte Bestellung: 404", c.get("/api/client/orders/gibts-nicht/receipt", headers=U1).status_code == 404)
check("ungueltiges Format: 400", c.get(f"/api/client/orders/{o1}/receipt?format=pdf", headers=U1).status_code == 400)
check("ohne Anmeldung: 401", c.get(f"/api/client/orders/{o1}/receipt").status_code == 401)

print("Datenbank")
with app.app_context():
    dup = Receipt(number="X-1", order_id=Order.query.filter_by(uuid=o1).first().id, payment_reference="pi_1", amount_cents=1,
                  currency="EUR", snapshot={})
    db.session.add(dup)
    try:
        db.session.commit()
        unique = False
    except Exception:
        db.session.rollback()
        unique = True
check("pro Bestellung und Zahlung hoechstens ein Beleg (Unique)", unique)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
