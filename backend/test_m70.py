"""M70 – Rechnungen mit Umsatzsteuer, Gutschrift bei Erstattung, Admin-Export."""

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


print("Steuersatz")
from decimal import Decimal
check("parse_vat_rate: 19, 7,5, 0, leer", [str(receipt_service.parse_vat_rate(x, strict=True)) for x in ("19", "7,5", "0", "")] == ["19", "7.5", "0", "0"])
bad = []
for x in ("abc", "-1", "100", "nan", "1e400"):
    try:
        receipt_service.parse_vat_rate(x, strict=True)
    except ValueError:
        bad.append(x)
check("ungueltige Saetze (abc, -1, 100, nan, 1e400) werfen im strikten Modus", bad == ["abc", "-1", "100", "nan", "1e400"], str(bad))
check("nicht strikt: ungueltig gilt als 0", receipt_service.parse_vat_rate("abc") == Decimal(0))
from app.config import ProductionConfig
mk = lambda **kw: type("C", (ProductionConfig,), kw)
check("Produktions-Check meldet ungueltigen VAT_RATE", any("VAT_RATE" in i for i in mk(VAT_RATE="abc").validate_production()))
check("... und akzeptiert 19 und 0", not any("VAT_RATE" in i for i in mk(VAT_RATE="19").validate_production() + mk(VAT_RATE="0").validate_production()))
vs = receipt_service.vat_split
check("Rundung: 499 @19% -> 419 netto, 80 USt", vs(499, Decimal(19)) == (419, 80))
check("Rundung: 1000 @19% -> 840 / 160, 199 @19% -> 167 / 32, 499 @7% -> 466 / 33", vs(1000, Decimal(19)) == (840, 160) and vs(199, Decimal(19)) == (167, 32) and vs(499, Decimal(7)) == (466, 33))
check("kaufmaennisch gerundet (Halbwerte nach oben): 3 @20% -> 2,5 -> 3 netto", vs(3, Decimal(20)) == (3, 0))
check("Satz 0: netto = brutto, USt 0", vs(499, Decimal(0)) == (499, 0))
check("Summe aus den gerundeten Teilen, auch negativ (Gutschrift)", all(sum(vs(g, Decimal(r))) == g for g in (-499, -1, 1, 3, 99, 12345, -12345) for r in (0, 7, 19, "5.5")) and vs(-499, Decimal(19)) == (-419, -80))

print("Rechnung ohne USt (Kleinunternehmer, Standard)")
app.config.update(INVOICE_SELLER="Muster Hosting\nMusterstr. 1\n12345 Musterstadt", RECEIPT_FOOTER="Danke!")
o1, pi1 = paid_order()
d1 = docs_of(o1)
check("eine Rechnung kind=invoice mit Satz 0, netto = brutto, USt 0", len(d1) == 1 and d1[0]["kind"] == "invoice" and d1[0]["vat_rate"] == 0
      and d1[0]["net_cents"] == 499 and d1[0]["vat_cents"] == 0 and d1[0]["gross_cents"] == 499 and d1[0]["amount_cents"] == 499, str(d1))
t = text_of(o1)
check("Text: Titel RECHNUNG, Rechnungsnummer, Betrag, Kleinunternehmer-Hinweis, kein USt-Block", "RECHNUNG" in t and "Rechnungsnummer: " + d1[0]["number"] in t and "Betrag: 4,99 EUR" in t
      and "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." in t and "Nettobetrag" not in t and "Umsatzsteuer " not in t.replace("keine Umsatzsteuer", ""), t)
check("Anbieter und Fusszeile stehen im Dokument", "Muster Hosting" in t and "Musterstr. 1" in t and t.rstrip().endswith("Danke!"))
check("Leistungszeitraum mit Datumsbereich (Beginn bis Ende der bezahlten Periode)", re.search(r"Leistungszeitraum: \d\d\.\d\d\.\d{4} – \d\d\.\d\d\.\d{4} \(UTC\)", t) is not None, t)
check("period_start/period_end in JSON (UTC), Ende = Ende der Laufzeit", d1[0]["period_start"] and d1[0]["period_end"].endswith("+00:00")
      and abs((datetime.fromisoformat(d1[0]["period_end"]) - datetime.fromisoformat(d1[0]["period_start"])).days - 30) <= 1)
check("seller im Schnappschuss (Zeilen, vat_id null)", d1[0]["seller"] == {"lines": ["Muster Hosting", "Musterstr. 1", "12345 Musterstadt"], "vat_id": None})
set_user(locale="en")
t = text_of(o1)
check("EN: INVOICE, Invoice number, Hinweis auf Kleinunternehmer englisch", "INVOICE" in t and "Invoice number: " in t and "small business exemption" in t and not re.search(r"Rechnung|Gemäß", t), t)
set_user(locale=None)
app.config["INVOICE_SMALL_BUSINESS_NOTE"] = "Kleinunternehmer, keine USt (eigener Text)."
check("eigener Kleinunternehmer-Text ersetzt den Standard in beiden Sprachen", "eigener Text" in text_of(o1))
set_user(locale="en")
check("... auch auf Englisch (Betreibertext bleibt)", "eigener Text" in text_of(o1))
set_user(locale=None)
app.config["INVOICE_SMALL_BUSINESS_NOTE"] = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
app.config["INVOICE_SELLER_VAT_ID"] = "DE123456789"
o1b, _ = paid_order()
t = text_of(o1b)
check("USt-IdNr. des Anbieters wird gedruckt (wenn konfiguriert)", "USt-IdNr.: DE123456789" in t and docs_of(o1b)[0]["seller"]["vat_id"] == "DE123456789")
check("aeltere Rechnung behaelt ihren Schnappschuss (ohne USt-IdNr.)", "DE123456789" not in text_of(o1))
app.config["INVOICE_SELLER_VAT_ID"] = ""

print("Rechnung mit 19 % USt")
app.config["VAT_RATE"] = "19"
o2, pi2 = paid_order()
d2 = docs_of(o2)[0]
check("19 %: netto 419, USt 80, brutto 499", (d2["vat_rate"], d2["net_cents"], d2["vat_cents"], d2["gross_cents"]) == (19, 419, 80, 499), str(d2))
t = text_of(o2)
check("Text: Netto-, USt- und Brutto-Zeile, kein Kleinunternehmer-Hinweis, kein 'Betrag'", "Nettobetrag: 4,19 EUR" in t and "Umsatzsteuer 19 %: 0,80 EUR" in t and "Bruttobetrag: 4,99 EUR" in t
      and "§ 19" not in t and "\nBetrag:" not in t, t)
set_user(locale="en")
t = text_of(o2)
check("EN: Net amount, VAT 19%, Gross amount mit Euro-Symbol", "Net amount: \u20ac4.19" in t and "VAT 19%: \u20ac0.80" in t and "Gross amount: \u20ac4.99" in t, t)
set_user(locale=None)
h = text_of(o2, fmt="html")
check("HTML: Tabelle mit denselben Zeilen, escaped", "<th>Nettobetrag</th><td>4,19 EUR</td>" in h and "<h1>Rechnung</h1>" in h and "<script" not in h)
app.config["VAT_RATE"] = "7,5"
o2b, _ = paid_order()
dd = docs_of(o2b)[0]
t = text_of(o2b)
check("Satz mit Dezimalstelle: 7,5 % (499 -> netto 464, USt 35), Anzeige mit Komma", dd["vat_rate"] == 7.5 and (dd["net_cents"], dd["vat_cents"]) == (464, 35) and "Umsatzsteuer 7,5 %" in t, str(dd))
app.config["VAT_RATE"] = "19"
check("aeltere Rechnungen behalten ihren Satz (Schnappschuss), auch wenn VAT_RATE sich aendert", docs_of(o1)[0]["vat_rate"] == 0 and docs_of(o2b)[0]["vat_rate"] == 7.5)

print("Empfaenger (Rechnungsname und -anschrift)")
r = c.patch("/api/client/account", json={"billing_name": "  Erika Mustermann ", "billing_address": "Musterweg 5\n54321 Beispielstadt"}, headers=U1)
check("PATCH: Name und Anschrift gespeichert (getrimmt), im Nutzerobjekt", r.status_code == 200 and r.json["billing_name"] == "Erika Mustermann"
      and r.json["billing_address"] == "Musterweg 5\n54321 Beispielstadt" and c.get("/api/auth/me", headers=U1).json["billing_name"] == "Erika Mustermann")
check("locale bleibt unberuehrt", r.json["locale"] == "de")
o3, _ = paid_order()
t = text_of(o3)
check("Empfaengerblock steht auf der neuen Rechnung vor dem Titel", "Erika Mustermann\nMusterweg 5\n54321 Beispielstadt\n\nRECHNUNG" in t, t)
check("customer_billing im Schnappschuss und JSON", docs_of(o3)[0]["customer_billing"] == {"name": "Erika Mustermann", "address": "Musterweg 5\n54321 Beispielstadt"})
check("aeltere Rechnung bekommt den Empfaenger nicht nachtraeglich", "Mustermann" not in text_of(o2) and docs_of(o2)[0]["customer_billing"] is None)
h = text_of(o3, fmt="html")
check("HTML-Empfaenger ist escaped", "<div>Erika Mustermann</div>" in h)
r = c.patch("/api/client/account", json={"billing_name": "<script>alert(1)</script>"}, headers=U1)
o3b, _ = paid_order()
check("Name mit HTML wird escaped ausgegeben", "&lt;script&gt;" in text_of(o3b, fmt="html") and "<script>alert" not in text_of(o3b, fmt="html"))
check("PATCH: Leerstring und nur Leerzeichen loeschen", c.patch("/api/client/account", json={"billing_name": "", "billing_address": "   "}, headers=U1).json["billing_name"] is None
      and c.get("/api/auth/me", headers=U1).json["billing_address"] is None)
bad = lambda body: c.patch("/api/client/account", json=body, headers=U1)
check("PATCH: Name > 200 Zeichen -> 400 invalid_billing_name", bad({"billing_name": "x" * 201}).status_code == 400 and bad({"billing_name": "x" * 201}).json["code"] == "invalid_billing_name")
check("PATCH: Anschrift > 500 Zeichen -> 400 invalid_billing_address", bad({"billing_address": "x" * 501}).json["code"] == "invalid_billing_address")
check("PATCH: 200 und 500 Zeichen sind erlaubt", bad({"billing_name": "x" * 200, "billing_address": "y" * 500}).status_code == 200)
check("PATCH: kein Text -> 400", bad({"billing_name": 5}).status_code == 400 and bad({"billing_address": ["a"]}).status_code == 400)
check("PATCH ohne bekannte Felder -> 400", bad({"foo": 1}).status_code == 400 and bad({}).status_code == 400)
check("PATCH nur locale wie bisher", bad({"locale": "en"}).json["locale"] == "en" and bad({"locale": "de"}).json["locale"] == "de")
set_user(billing_name=None, billing_address=None)

print("Leistungszeitraum bei Verlaengerung und Wartezeit")
o4, pi4 = paid_order()
c.post(f"/api/admin/orders/{o4}/mark-paid", json={"payment_reference": "renew-1"}, headers=AH)
d4 = docs_of(o4)
first_end = datetime.fromisoformat(d4[0]["period_end"])
check("Verlaengerung: Zeitraum beginnt am Ende der vorherigen Periode, 30 Tage lang", len(d4) == 2 and datetime.fromisoformat(d4[1]["period_start"]) == first_end
      and (datetime.fromisoformat(d4[1]["period_end"]) - first_end).days == 30, str(d4[1]))
with app.app_context():
    db.session.get(Agent, ids["agent"]).memory_total = 100
    db.session.commit()
n[0] += 1
ou = c.post("/api/client/orders", json={"product_id": PID, "name": "wait"}, headers=U1).json["uuid"]
post({"id": "cs_w", "object": "checkout.session", "payment_status": "paid", "payment_intent": "pi_wait", "amount_total": 499, "currency": "eur",
      "metadata": {"order_uuid": ou}, "client_reference_id": ou}, "checkout.session.completed")
dw = docs_of(ou)
check("wartende Bereitstellung: Rechnung ohne Zeitraum, Text 'Tage ab Bereitstellung'", len(dw) == 1 and dw[0]["period_start"] is None and dw[0]["period_end"] is None
      and "Leistungszeitraum: 30 Tage ab Bereitstellung" in text_of(ou), text_of(ou))
with app.app_context():
    db.session.get(Agent, ids["agent"]).memory_total = 100000
    db.session.commit()

print("Gutschrift bei Erstattung")
o5, pi5 = paid_order()
inv = docs_of(o5)[0]
refund_event(pi5, 100, "evt_p1")
cn = docs_of(o5, "credit_note")
check("Teilerstattung 100: Gutschrift mit negativen Betraegen (19 %: netto -84, USt -16), verweist auf die Rechnung", len(cn) == 1 and cn[0]["gross_cents"] == -100 and cn[0]["amount_cents"] == -100
      and (cn[0]["net_cents"], cn[0]["vat_cents"]) == (-84, -16) and cn[0]["vat_rate"] == 19 and cn[0]["references_number"] == inv["number"], str(cn))
seq_inv = int(inv["number"].split("-")[-1])
check("eigene Nummer aus demselben Zaehler (direkt nach der Rechnung)", int(cn[0]["number"].split("-")[-1]) == seq_inv + 1, f"{inv['number']} {cn[0]['number']}")
t = text_of(o5, cn[0]["number"])
check("Text: Titel GUTSCHRIFT / STORNORECHNUNG, 'zu Rechnung Nr.', negative Betraege, Zeitraum der Rechnung", "GUTSCHRIFT / STORNORECHNUNG" in t and f"zu Rechnung Nr. {inv['number']}" in t
      and "Bruttobetrag: -1,00 EUR" in t and "Nettobetrag: -0,84 EUR" in t and "Umsatzsteuer 19 %: -0,16 EUR" in t and "Gutschriftnummer: " + cn[0]["number"] in t and "Leistungszeitraum" in t, t)
check("Gutschrift hat keinen Verwendungszweck und keine 'refund:'-Referenz im Dokument", "Verwendungszweck" not in t and "refund:" not in t, t)
set_user(locale="en")
t = text_of(o5, cn[0]["number"])
check("EN: Credit note, 'for invoice no.', Minus vor dem Euro-Symbol", "CREDIT NOTE" in t and f"for invoice no. {inv['number']}" in t and "Gross amount: -\u20ac1.00" in t, t)
set_user(locale=None)
refund_event(pi5, 100, "evt_p1")
check("gleiche Ereignis-ID nochmal: keine zweite Gutschrift (idempotent)", len(docs_of(o5, "credit_note")) == 1)
refund_event(pi5, 300, "evt_p2")
cn = docs_of(o5, "credit_note")
check("zweite Teilerstattung (kumuliert 300): Gutschrift nur ueber den Rest (200)", len(cn) == 2 and cn[1]["gross_cents"] == -200, str([x["gross_cents"] for x in cn]))
refund_event(pi5, 499, "evt_full")
cn = docs_of(o5, "credit_note")
check("Vollerstattung (499): Gutschrift ueber den Rest (199), Summe = Rechnung", len(cn) == 3 and cn[2]["gross_cents"] == -199 and sum(x["gross_cents"] for x in cn) == -499, str([x["gross_cents"] for x in cn]))
refund_event(pi5, 499, "evt_again")
check("weiteres Ereignis nach voller Gutschrift: keine weitere Gutschrift", len(docs_of(o5, "credit_note")) == 3)
with app.app_context():
    from app.domain.activity.models import ActivityLog
    props = [e.properties for e in ActivityLog.query.filter_by(event="order:refunded").all()]
check("Activity-Properties enthalten credit_note", any(p.get("credit_note") == cn[0]["number"] for p in props))
check("Rechnung bleibt unveraendert (kein Storno der Rechnung selbst)", doc(inv["number"])["gross_cents"] == 499 and doc(inv["number"])["kind"] == "invoice")
check("Kunde sieht Gutschriften in der Bestellung (kind), Standardabruf liefert die Rechnung", [x["kind"] for x in c.get(f"/api/client/orders/{o5}", headers=U1).json["receipts"]] == ["invoice"] + ["credit_note"] * 3
      and "RECHNUNG" in text_of(o5) and "GUTSCHRIFT" not in text_of(o5))
o6, pi6 = paid_order()
r = refund_event("pi_unbekannt", 499, "evt_x")
check("Erstattung ohne passende Bestellung: keine Gutschrift, kein Fehler", r.status_code == 200)
with app.app_context():
    Receipt.query.filter_by(order_id=Order.query.filter_by(uuid=o6).first().id).delete()
    db.session.commit()
r = refund_event(pi6, 499, "evt_noinv")
check("Zahlung ohne Rechnung (z.B. vor M62): Erstattung wird verarbeitet, keine Gutschrift", r.status_code == 200 and docs_of(o6) == [])

print("Altbestand (Belege vor M70 ohne Steuerfelder)")
o7, _ = paid_order()
with app.app_context():
    row = Receipt.query.filter_by(order_id=Order.query.filter_by(uuid=o7).first().id).first()
    row.snapshot = {k: v for k, v in row.snapshot.items() if k in ("product_name", "instance_name", "billing_period_days", "customer")}
    db.session.commit()
    legacy_number = row.number
t = text_of(o7)
check("rendert weiter als Zahlungsbeleg mit Hinweis 'keine Rechnung im Sinne des UStG'", "ZAHLUNGSBELEG" in t and "Belegnummer: " + legacy_number in t and "keine Rechnung im Sinne des Umsatzsteuergesetzes" in t and "Laufzeit: 30 Tage" in t, t)
check("HTML rendert auch", "<h1>Zahlungsbeleg</h1>" in text_of(o7, fmt="html"))
dj = doc(legacy_number)
check("JSON: Steuerfelder null, brutto vorhanden, kind invoice", dj["vat_rate"] is None and dj["net_cents"] is None and dj["vat_cents"] is None and dj["gross_cents"] == 499 and dj["kind"] == "invoice")
set_user(locale="en")
check("EN-Altbeleg: 'PAYMENT RECEIPT'", "PAYMENT RECEIPT" in text_of(o7))
set_user(locale=None)

print("Admin: Rechnungsliste und CSV")
def inv_list(q=""):
    return c.get("/api/admin/invoices" + q, headers=AH)
today = datetime.utcnow().date()
r = inv_list()
nums = [d["number"] for d in r.json]
check("Standard: laufender Monat als JSON, alle bisherigen Dokumente", r.status_code == 200 and isinstance(r.json, list) and len(nums) >= 10 and legacy_number in nums and cn[0]["number"] in nums)
keys = {"number", "kind", "issued_at", "order_uuid", "username", "net_cents", "vat_cents", "vat_rate", "gross_cents", "currency", "payment_reference", "references_number"}
check("Felder je Dokument", all(set(d) == keys for d in r.json))
by = {d["number"]: d for d in r.json}
check("Rechnung: Steuerfelder, order_uuid, username", by[inv["number"]]["order_uuid"] == o5 and by[inv["number"]]["username"] == "k1" and by[inv["number"]]["net_cents"] == 419 and by[inv["number"]]["vat_rate"] == 19)
check("Gutschrift: negativ, kind, references_number", by[cn[0]["number"]]["kind"] == "credit_note" and by[cn[0]["number"]]["gross_cents"] < 0 and by[cn[0]["number"]]["references_number"] == inv["number"])
check("Altbeleg: net/vat/vat_rate null", (by[legacy_number]["net_cents"], by[legacy_number]["vat_cents"], by[legacy_number]["vat_rate"]) == (None, None, None) and by[legacy_number]["gross_cents"] == 499)
check("aelteste zuerst", [d["issued_at"] for d in r.json] == sorted(d["issued_at"] for d in r.json))
with app.app_context():
    old = Receipt.query.filter_by(number=inv["number"]).first()
    old.issued_at = datetime(2026, 3, 31, 23, 59, 59)
    old2 = Receipt.query.filter_by(number=legacy_number).first()
    old2.issued_at = datetime(2026, 4, 1, 0, 0, 0)
    db.session.commit()
r = inv_list("?from=2026-03-31&to=2026-03-31")
check("from/to einschliesslich (31.03. 23:59:59 ist drin)", [d["number"] for d in r.json] == [inv["number"]])
r = inv_list("?from=2026-04-01&to=2026-04-01")
check("1.4. 00:00:00 gehoert zum 1.4., nicht zum 31.3.", [d["number"] for d in r.json] == [legacy_number])
check("nur from: bis Monatsende dieses Monats", all(d["issued_at"][:7] == "2026-04" for d in inv_list("?from=2026-04-01").json) and legacy_number in [d["number"] for d in inv_list("?from=2026-04-01").json])
check("leerer Zeitraum: leere Liste", inv_list("?from=2020-01-01&to=2020-01-31").json == [])
r = inv_list("?from=2026-04-01&to=2026-04-30&format=csv")
raw = r.get_data()
check("CSV: UTF-8 mit BOM, text/csv, Dateiname rechnungen-2026-04.csv", raw.startswith(b"\xef\xbb\xbf") and r.mimetype == "text/csv" and 'filename="rechnungen-2026-04.csv"' in r.headers["Content-Disposition"]
      and r.headers["Content-Disposition"].startswith("attachment"), str(r.headers))
rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
check("CSV: Semikolon, Kopfzeile mit allen Spalten plus net/vat/gross", rows[0] == ["number", "kind", "issued_at", "order_uuid", "username", "net_cents", "vat_cents", "vat_rate",
                                                                               "gross_cents", "currency", "payment_reference", "references_number", "net", "vat", "gross"], str(rows[0]))
check("CSV: Zeile des Altbelegs (leere Steuerfelder, Brutto 4,99 mit Komma)", rows[1][0] == legacy_number and rows[1][5:8] == ["", "", ""] and rows[1][8] == "499" and rows[1][-1] == "4,99" and rows[1][9] == "EUR", str(rows[1]))
with app.app_context():
    cnote = Receipt.query.filter_by(number=cn[0]["number"]).first()
    cnote.issued_at = datetime(2026, 4, 2, 12, 0, 0)
    db.session.commit()
    User.query.get(ids["u1"]).username = "=HYPERLINK(\"http://x\")"
    db.session.commit()
rows = list(csv.reader(io.StringIO(inv_list("?from=2026-04-01&to=2026-04-30&format=csv").get_data().decode("utf-8-sig")), delimiter=";"))
cn_row = [r_ for r_ in rows if r_[0] == cn[0]["number"]][0]
check("CSV: Gutschrift mit negativen Zahlen (-100; Dezimal -0,84 / -0,16 / -1,00), Verweis auf die Rechnung", cn_row[1] == "credit_note" and cn_row[8] == "-100"
      and cn_row[-3:] == ["-0,84", "-0,16", "-1,00"] and cn_row[11] == inv["number"], str(cn_row))
check("CSV: Formeln in Textspalten entschaerft (Benutzername beginnt mit ')", cn_row[4].startswith("'=HYPERLINK"), str(cn_row))
with app.app_context():
    User.query.get(ids["u1"]).username = "k1"
    db.session.commit()
r = inv_list("?from=2026-03-01&to=2026-04-30&format=csv")
check("Zeitraum ueber mehrere Monate: Dateiname mit Datumsbereich", 'filename="rechnungen-2026-03-01_2026-04-30.csv"' in r.headers["Content-Disposition"])
r = inv_list(f"?format=csv")
check("CSV ohne Parameter: aktueller Monat im Dateinamen", f'filename="rechnungen-{today:%Y-%m}.csv"' in r.headers["Content-Disposition"])
check("ungueltiges Datum -> 400 invalid_date", inv_list("?from=gestern").status_code == 400 and inv_list("?from=gestern").json["code"] == "invalid_date" and inv_list("?to=2026-13-01").json["code"] == "invalid_date")
check("from nach to -> 400 invalid_range", inv_list("?from=2026-05-01&to=2026-04-01").json["code"] == "invalid_range")
check("Zeitraum > 366 Tage -> 400 range_too_large", inv_list("?from=2025-01-01&to=2026-04-01").json["code"] == "range_too_large" and inv_list("?from=2025-04-01&to=2026-04-01").status_code == 200)
check("format ungueltig -> 400 invalid_format", inv_list("?format=xml").json["code"] == "invalid_format")
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Anmeldung 401, Kunde 403, Admin 200", c.get("/api/admin/invoices").status_code == 401 and c.get("/api/admin/invoices", headers=U1).status_code == 403
      and c.get("/api/admin/invoices", headers=AH).status_code == 200)
app.config["ADMIN_GUARD_ENABLED"] = False

print("Umsatzstatistik")
with app.app_context():
    for d in Receipt.query.all():
        d.issued_at = datetime.utcnow()
    legacy = Receipt.query.filter_by(number=legacy_number).first()
    db.session.commit()
    rs = revenue_stats(30)
    invoices = Receipt.query.filter_by(kind="invoice").all()
    exp_gross = sum(d.amount_cents for d in invoices)
    with_tax = [d for d in invoices if "net_cents" in (d.snapshot or {})]
    exp_net, exp_vat = sum(d.snapshot["net_cents"] for d in with_tax), sum(d.snapshot["vat_cents"] for d in with_tax)
    n_credit = Receipt.query.filter_by(kind="credit_note").count()
check("by_currency = Summe der Rechnungen (brutto), Gutschriften zaehlen nicht", rs["by_currency"] == {"EUR": exp_gross} and n_credit >= 3, str(rs))
check("net_by_currency und vat_by_currency (nur Belege mit Steuerfeldern)", rs["net_by_currency"] == {"EUR": exp_net} and rs["vat_by_currency"] == {"EUR": exp_vat}
      and exp_net + exp_vat == exp_gross - legacy.amount_cents, f"{rs} {exp_net} {exp_vat} {exp_gross}")
check("Zaehler nur aus Rechnungen", rs["paid_count"] + rs["renewals_count"] == len(invoices))
check("API liefert die Felder", c.get("/api/admin/stats/revenue", headers=AH).json["vat_by_currency"] == {"EUR": exp_vat})

print("Migration")
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    dbp = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{dbp}", "RUNNER_ADAPTER": "stub", "FLASK_APP": "app:create_app"}
    run = lambda *a: subprocess.run([sys.executable, "-m", "flask", "db", *a], env=env, capture_output=True, text=True, cwd=cwd)
    up = run("upgrade")
    cols = lambda t: {r_[1] for r_ in sqlite3.connect(dbp).execute(f"pragma table_info({t})")}
    has = (cols("receipts") >= {"kind", "references_id"}, cols("users") >= {"billing_name", "billing_address"})
    fk = [r_ for r_ in sqlite3.connect(dbp).execute("pragma foreign_key_list(receipts)") if r_[3] == "references_id"]
    down = run("downgrade", "x4s5t6u7v8w9")
    gone = (not (cols("receipts") & {"kind", "references_id"}), not (cols("users") & {"billing_name", "billing_address"}))
    up2 = run("upgrade")
    heads = run("heads")
check("Kette bis zum Head, Spalten und Fremdschluessel vorhanden", up.returncode == 0 and has == (True, True) and len(fk) == 1, up.stderr[-300:])
check("Downgrade auf M68 entfernt alle vier Spalten", down.returncode == 0 and gone == (True, True), down.stderr[-300:])
check("erneutes Upgrade und genau ein Head", up2.returncode == 0 and heads.stdout.count("(head)") == 1)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
