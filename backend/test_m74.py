"""M74 – Schweiz-Tauglichkeit: INVOICE_COUNTRY, MWST-Beschriftung, Hinweise je Land, CHF-Format."""

import csv
import hashlib
import io
import re
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
from app.domain.billing.models import Order, PaymentEvent, Receipt
from app.domain.billing import receipts as receipt_service
from app.domain.billing.service import revenue_stats
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
PAY = {"cents": 499, "cur": "eur"}


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
              "amount_total": PAY["cents"], "currency": PAY["cur"], "metadata": {"order_uuid": ou}, "client_reference_id": ou},
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


def doc(number):
    with app.app_context():
        d = Receipt.query.filter_by(number=number).first()
        return d.to_dict() if d else None


def docs_of(ou, kind=None):
    with app.app_context():
        oid = Order.query.filter_by(uuid=ou).first().id
        q = Receipt.query.filter_by(order_id=oid)
        if kind:
            q = q.filter_by(kind=kind)
        return [d.to_dict() for d in q.order_by(Receipt.id).all()]


def text_of(ou, number=None, fmt="text"):
    q = f"?format={fmt}" + (f"&number={number}" if number else "")
    return c.get(f"/api/client/orders/{ou}/receipt{q}", headers=U1).get_data(as_text=True)


def refund_event(pi, total, event_id, full=None):
    full = (total >= 499) if full is None else full
    return post({"id": f"ch_{pi}", "object": "charge", "payment_intent": pi, "amount": 499, "currency": "eur",
                 "amount_refunded": total, "refunded": full, "metadata": {}}, "charge.refunded", event_id)


def set_user(**kw):
    with app.app_context():
        u = User.query.get(ids["u1"])
        for k, v in kw.items():
            setattr(u, k, v)
        db.session.commit()



from datetime import datetime as _dt
from app.i18n import format_money
from app.domain.billing import service as billing

def docs_of(ou, kind=None):
    with app.app_context():
        oid = Order.query.filter_by(uuid=ou).first().id
        q = Receipt.query.filter_by(order_id=oid)
        if kind:
            q = q.filter_by(kind=kind)
        return [d.to_dict() for d in q.order_by(Receipt.id).all()]


def text_of(ou, number=None, fmt="text"):
    q = f"?format={fmt}" + (f"&number={number}" if number else "")
    return c.get(f"/api/client/orders/{ou}/receipt{q}", headers=U1).get_data(as_text=True)



def set_user(**kw):
    with app.app_context():
        u = User.query.get(ids["u1"])
        for k, v in kw.items():
            setattr(u, k, v)
        db.session.commit()



app.config.update(INVOICE_SELLER="Einzelfirma Muster\nBahnhofstr. 1\n8000 Zuerich", INVOICE_SELLER_VAT_ID="CHE-123.456.789 MWST")

print("Betragsformat CHF")
check("DE: CHF 1'234.56", format_money("de", 123456, "CHF") == "CHF 1'234.56", format_money("de", 123456, "CHF"))
check("DE: Millionen und kleine Betraege", format_money("de", 123456789, "CHF") == "CHF 1'234'567.89" and format_money("de", 5, "CHF") == "CHF 0.05")
check("DE: negativ (Gutschrift)", format_money("de", -123456, "CHF") == "-CHF 1'234.56", format_money("de", -123456, "CHF"))
check("EN: CHF 1,234.56", format_money("en", 123456, "CHF") == "CHF 1,234.56" and format_money("en", -50, "CHF") == "-CHF 0.50")
check("unbekannte/fehlende Locale: wie Deutsch", format_money(None, 123456, "CHF") == "CHF 1'234.56")
check("EUR/USD unveraendert", format_money("de", 123456, "EUR") == "1.234,56 EUR" and format_money("en", 123456, "EUR") == "\u20ac1,234.56"
      and format_money("en", 123456, "USD") == "$1,234.56" and format_money("de", -5, "EUR") == "-0,05 EUR")

print("Produktions-Check")
from app.config import ProductionConfig
mk = lambda **kw: type("C", (ProductionConfig,), kw)
check("Standard ist DE und besteht den Check", ProductionConfig.INVOICE_COUNTRY == "DE" and not any("INVOICE_COUNTRY" in i for i in ProductionConfig.validate_production()))
check("CH besteht den Check", not any("INVOICE_COUNTRY" in i for i in mk(INVOICE_COUNTRY="CH").validate_production()))
bad = [i for i in mk(INVOICE_COUNTRY="AT").validate_production() if "INVOICE_COUNTRY" in i]
check("unbekanntes Land ist KRITISCH", len(bad) == 1 and bad[0].startswith("KRITISCH"), str(bad))

print("Deutschland (Standard)")
set_user(locale=None)
o_de, _ = paid_order()
d_de = docs_of(o_de)[0]
t = text_of(o_de)
check("country=DE im Schnappschuss", d_de["country"] == "DE", str(d_de))
check("DE: Hinweis nach Paragraph 19 UStG, USt-IdNr.-Beschriftung, Euro-Format", "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." in t
      and "USt-IdNr.: CHE-123.456.789 MWST" in t and "Betrag: 4,99 EUR" in t and "MWST" not in t.replace("CHE-123.456.789 MWST", ""), t)
set_user(locale="en")
t = text_of(o_de)
check("DE/EN: englischer Standardhinweis", "section 19 of the German VAT Act" in t and "VAT ID: " in t and "Swiss" not in t, t)
set_user(locale=None)

print("Schweiz")
app.config["INVOICE_COUNTRY"] = "CH"
r = c.post("/api/admin/products", json={"name": "PCH", "blueprint_id": ids["bp"], "memory": 512, "disk": 1000, "cpu": 50,
                                         "price_cents": 123456, "billing_period_days": 30, "currency": "CHF"}, headers=AH)
check("Produkt in CHF", r.status_code == 201 and r.json["currency"] == "CHF", str(r.json))
PID_CHF = r.json["id"]
PID_EUR = PID
PID = PID_CHF
PAY.update(cents=123456, cur="chf")
o_ch, _ = paid_order()
PID = PID_EUR
d_ch = docs_of(o_ch, "invoice")[0]
check("country=CH und Betrag in CHF im Dokument", d_ch["country"] == "CH" and d_ch["currency"] == "CHF" and d_ch["amount_cents"] == 123456, str(d_ch))
set_user(locale="de")
t = text_of(o_ch)
check("CH/DE: Hinweis nach MWSTG", "Nicht mehrwertsteuerpflichtig (Art. 10 Abs. 2 lit. a MWSTG)" in t and "§ 19" not in t and "UStG" not in t, t)
check("CH/DE: MWST-Nr.-Zeile mit Nummer unveraendert (nur Anzeige)", "MWST-Nr.: CHE-123.456.789 MWST" in t and "USt-IdNr." not in t, t)
check("CH/DE: Betrag CHF 1'234.56", "Betrag: CHF 1'234.56" in t, t)
h = text_of(o_ch, fmt="html")
check("CH/DE: HTML mit Hinweis, MWST-Nr. und Betrag", "Art. 10 Abs. 2 lit. a MWSTG" in h and "MWST-Nr.: CHE-123.456.789 MWST" in h and "CHF 1&#x27;234.56" in h.replace("'", "&#x27;") , h[:2000])
set_user(locale="en")
t = text_of(o_ch)
check("CH/EN: Hinweis englisch, VAT no., CHF 1,234.56", "Not subject to Swiss VAT (Art. 10 para. 2 lit. a VAT Act)" in t and "VAT no.: CHE-123.456.789 MWST" in t
      and "Amount: CHF 1,234.56" in t and "§ 19" not in t, t)
set_user(locale=None)
app.config["INVOICE_SMALL_BUSINESS_NOTE"] = "Eigener Hinweis."
check("expliziter Text gewinnt in CH, in beiden Sprachen", "Eigener Hinweis." in text_of(o_ch) and (set_user(locale="en"), "Eigener Hinweis." in text_of(o_ch))[1])
set_user(locale=None)
app.config["INVOICE_SMALL_BUSINESS_NOTE"] = ""
check("leer = Standard je Land (CH)", "MWSTG" in text_of(o_ch))
check("der alte deutsche Standardtext in der Config zaehlt wie leer (CH liefert MWSTG)",
      (app.config.__setitem__("INVOICE_SMALL_BUSINESS_NOTE", "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."), "MWSTG" in text_of(o_ch))[1])
app.config["INVOICE_SMALL_BUSINESS_NOTE"] = ""

print("Schweiz mit MWST-Pflicht")
app.config["VAT_RATE"] = "8.1"
PID = PID_CHF
o_v, _ = paid_order()
PID = PID_EUR
PAY.update(cents=499, cur="eur")
d_v = docs_of(o_v, "invoice")[0]
check("Satz 8.1 gilt fuer die Rechnung: netto 114'205, MWST 9'251 (1'234.56 brutto)", d_v["vat_rate"] == 8.1 and d_v["net_cents"] + d_v["vat_cents"] == 123456
      and d_v["vat_cents"] == 9251, str(d_v))
set_user(locale="de")
t = text_of(o_v)
check("CH/DE: Zeilen MWST 8,1 % und Nettobetrag/Bruttobetrag in CHF, kein Kleinunternehmer-Hinweis",
      "MWST 8,1 %: CHF 92.51" in t and "Nettobetrag: CHF 1'142.05" in t and "Bruttobetrag: CHF 1'234.56" in t and "Umsatzsteuer" not in t and "MWSTG" not in t, t)
set_user(locale="en")
t = text_of(o_v)
check("CH/EN: VAT 8.1%", "VAT 8.1%: CHF 92.51" in t and "Net amount: CHF 1,142.05" in t, t)
set_user(locale=None)
app.config["VAT_RATE"] = "0"

print("Gutschrift in der Schweiz")
refund_pi = None
with app.app_context():
    order = Order.query.filter_by(uuid=o_ch).first()
    inv = Receipt.query.filter_by(order_id=order.id, kind="invoice").first()
    note = receipt_service.issue_credit_note(order, inv, 123456, "evt_ch_refund")
    number = note.number
check("Gutschrift uebernimmt country=CH", doc(number)["country"] == "CH", str(doc(number)))
set_user(locale="de")
t = text_of(o_ch, number)
check("Gutschrift: negativer CHF-Betrag, MWSTG-Hinweis, MWST-Nr.", "Betrag: -CHF 1'234.56" in t and "MWSTG" in t and "MWST-Nr.: CHE-123.456.789 MWST" in t, t)
set_user(locale=None)

print("Aenderung des Landes aendert alte Belege nicht")
app.config["INVOICE_COUNTRY"] = "DE"
t = text_of(o_ch)
check("CH-Rechnung bleibt nach Wechsel auf DE eine CH-Rechnung (Hinweis, Beschriftung)", "MWSTG" in t and "MWST-Nr." in t and "§ 19" not in t, t)
app.config["INVOICE_COUNTRY"] = "CH"

print("Altbestand ohne country-Feld gilt als Deutschland")
with app.app_context():
    rec = Receipt.query.filter_by(number=d_de["number"]).first()
    snap = dict(rec.snapshot)
    snap.pop("country")
    rec.snapshot = snap
    db.session.commit()
check("Beleg ohne country wird mit DE-Texten gerendert, auch wenn die Config CH ist", "§ 19 UStG" in text_of(o_de) and "USt-IdNr." in text_of(o_de))

print("Mail mit CHF-Betrag")
with app.app_context():
    order = Order.query.filter_by(uuid=o_ch).first()
    mail.outbox.clear()
    user = User.query.get(ids["u1"])
    user.locale = None
    db.session.commit()
    billing._mail_order(order, "expiry_reminder", end=_dt(2026, 1, 1), price_cents=123456)
    de_body = mail.outbox[-1]["body"]
    user.locale = "en"
    db.session.commit()
    billing._mail_order(order, "expiry_reminder", end=_dt(2026, 1, 1), price_cents=123456)
    en_body = mail.outbox[-1]["body"]
check("Mail DE: CHF 1'234.56", "CHF 1'234.56" in de_body, de_body)
check("Mail EN: CHF 1,234.56", "CHF 1,234.56" in en_body, en_body)
set_user(locale=None)

print("CSV-Export: Betraege bleiben reine Zahlen")
raw = c.get("/api/admin/invoices?format=csv", headers=AH).get_data().decode("utf-8-sig")
rows = list(csv.DictReader(io.StringIO(raw), delimiter=";"))
row = next((x for x in rows if x["number"] == d_ch["number"]), None)
check("CSV: CHF-Betrag bleibt reine Zahl (gross_cents 123456, gross 1234,56, kein Hochkomma, keine Waehrung im Feld)",
      row is not None and row["gross_cents"] == "123456" and row["gross"] == "1234,56" and row["currency"] == "CHF" and "'" not in raw, str(row))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
