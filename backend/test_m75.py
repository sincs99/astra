"""M75 – Markenname SITE_NAME in Mails, Absender, Belegkopf und Admin-Alerts."""

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




from app.domain.system import alerts
from app.i18n import tr, site_name
from app.infrastructure.mail import from_header, send_mail
from app.i18n.messages import MESSAGES
import app.i18n.messages as _m

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




def subjects():
    return [m["subject"] for m in mail.outbox]


app.config.update(INVOICE_SELLER="Muster Hosting\nMusterstr. 1")
print("Standard (SITE_NAME nicht gesetzt)")
with app.app_context():
    check("Default ist Astra", app.config["SITE_NAME"] == "Astra" and site_name() == "Astra")
with app.app_context():
    for loc in ("de", "en"):
        bad = [k for k, v in MESSAGES[loc].items() if k.endswith(".subject") and tr(loc, k) != v.replace("{site}", "Astra")]
        check(f"{loc}: alle Betreffe wie bisher 'Astra: ...'", not bad and all(tr(loc, k).startswith("Astra: ") for k in MESSAGES[loc] if k.endswith(".subject")), str(bad))
    check("keine Betreff-Vorlage ohne Platzhalter {site}", all("{site}" in v for loc in ("de", "en") for k, v in MESSAGES[loc].items() if k.endswith(".subject")))
    mail.outbox.clear()
    app.config.update(MAIL_FROM="shop@example.test")
    send_mail(app, "k1@t.local", "x", "y")
    check("Absender Standard: Astra <shop@example.test>", mail.outbox[-1]["from"] == "Astra <shop@example.test>", mail.outbox[-1]["from"])
o_def, _ = paid_order()
t = text_of(o_def)
check("Belegkopf ohne Markenzeile (Standard unveraendert), Anbieter wie konfiguriert", t.startswith("Muster Hosting\n") and "site_name" not in docs_of(o_def)[0], t[:200])

print("SITE_NAME=Astrahost")
app.config.update(SITE_NAME="Astrahost", INVOICE_SELLER="Einzelfirma Muster\nBahnhofstr. 1\n8000 Zuerich")
with app.app_context():
    check("alle Betreffe beginnen mit 'Astrahost: ' (DE und EN)", all(tr(loc, k).startswith("Astrahost: ") and "Astra:" not in tr(loc, k)
          for loc in ("de", "en") for k in MESSAGES[loc] if k.endswith(".subject")))
    check("Betreff-Beispiel DE/EN", tr("de", "mail.verify.subject") == "Astrahost: E-Mail-Adresse bestätigen" and tr("en", "mail.verify.subject") == "Astrahost: Confirm your email address")
    check("Texte ohne Betreff bleiben (kein 'Astra' im Mailtext ersetzt)", tr("de", "mail.verify.body", username="u", hours=1, link="L").count("Astrahost") == 0)
mail.outbox.clear()
r = c.post("/api/auth/password-reset/request", json={"email": "k1@t.local"})
app.config["REGISTRATION_ENABLED"] = True
r2 = c.post("/api/auth/register", json={"username": "neu", "email": "neu@t.local", "password": "test12345"})
check("echte Mails (Reset/Registrierung) tragen den Markennamen", mail.outbox and all(s.startswith("Astrahost: ") for s in subjects()), str(subjects()))
check("Absender Astrahost <shop@example.test>", all(m["from"] == "Astrahost <shop@example.test>" for m in mail.outbox), str([m["from"] for m in mail.outbox]))
app.config["MAIL_FROM_NAME"] = "Astrahost Support"
with app.app_context():
    check("MAIL_FROM_NAME gewinnt", from_header(app) == "Astrahost Support <shop@example.test>", from_header(app))
    app.config["MAIL_FROM"] = "Bestellungen <b@example.test>"
    check("MAIL_FROM mit eigenem Namen bleibt unveraendert", from_header(app) == "Bestellungen <b@example.test>")
    app.config["MAIL_FROM"] = "shop@example.test"
    app.config["MAIL_FROM_NAME"] = "Schr\u00f6der & Co"
    check("Umlaute im Absendernamen: gueltiger Header", "shop@example.test" in from_header(app) and "Schr" in from_header(app))
    app.config["MAIL_FROM_NAME"] = "Zeile\r\nBcc: x@y.z"
    fh = from_header(app)
    check("Zeilenumbrueche im Absendernamen werden entschaerft", "\n" not in fh and "\r" not in fh, repr(fh))
app.config["MAIL_FROM_NAME"] = ""
app.config["SITE_NAME"] = "Astrahost\nBcc: evil@x.y"
with app.app_context():
    check("Zeilenumbruch in SITE_NAME: Betreff einzeilig", "\n" not in tr("de", "mail.verify.subject") and site_name() == "Astrahost Bcc: evil@x.y", site_name())
    app.config["SITE_NAME"] = "x" * 100
    check("zu langer Name wird auf 60 Zeichen gekappt", len(site_name()) == 60)
app.config["SITE_NAME"] = "Astrahost"

print("Billing-Mails")
with app.app_context():
    from app.domain.billing import service as billing
    order = Order.query.filter_by(uuid=o_def).first()
    mail.outbox.clear()
    billing._mail_order(order, "expiry_reminder", end=datetime(2026, 1, 1), price_cents=499)
check("Bestellmail: Betreff Astrahost", subjects() == ["Astrahost: Die Laufzeit deines Servers endet bald"], str(subjects()))

print("Belegkopf")
o_b, _ = paid_order()
d = docs_of(o_b, "invoice")[0]
t = text_of(o_b)
check("Schnappschuss merkt den Markennamen", d["site_name"] == "Astrahost", str(d))
check("Text: erste Zeile Astrahost, danach der Anbieter", t.startswith("Astrahost\nEinzelfirma Muster\nBahnhofstr. 1\n"), t[:200])
h = text_of(o_b, fmt="html")
check("HTML: Markenzeile im Kopf", "<div>Astrahost</div><div>Einzelfirma Muster</div>" in h, h[:1500])
check("aeltere Rechnung (ohne Markennamen) bleibt unveraendert", text_of(o_def).startswith("Muster Hosting\n"))
app.config["INVOICE_SELLER"] = "Astrahost\nBahnhofstr. 1"
o_c, _ = paid_order()
check("Anbieterzeile gleich dem Markennamen: keine doppelte Zeile", text_of(o_c).startswith("Astrahost\nBahnhofstr. 1\n"), text_of(o_c)[:100])
with app.app_context():
    order = Order.query.filter_by(uuid=o_b).first()
    inv = Receipt.query.filter_by(order_id=order.id, kind="invoice").first()
    note = receipt_service.issue_credit_note(order, inv, 499, "evt_m75").number
app.config["SITE_NAME"] = "Andere Marke"
check("Gutschrift uebernimmt den Markennamen der Rechnung, nicht der aktuellen Konfiguration",
      text_of(o_b, note).startswith("Astrahost\n") and "Andere Marke" not in text_of(o_b, note))
check("Rechnung bleibt nach Namenswechsel unveraendert", text_of(o_b).startswith("Astrahost\n"))
app.config["SITE_NAME"] = "Astrahost"

print("Admin-Alerts")
app.config.update(ADMIN_ALERT_EMAIL="ops@t.local", ADMIN_ALERT_WEBHOOK_URL="")
with app.app_context():
    mail.outbox.clear()
    alerts.send_admin_alert(f"{site_name()}: Test", "x")
    alerts.alert_payment_problem("ou-1", "refunded", "d", "evt-1")
    out = [m["subject"] for m in mail.outbox]
check("Alert-Betreff mit Markennamen", out and all(s.startswith("Astrahost: ") for s in out), str(out))
with app.app_context():
    import inspect
    src_alerts = inspect.getsource(alerts)
check("keine fest verdrahteten 'Astra: ' Betreffe mehr im Alert-Modul", '"Astra: ' not in src_alerts and "'Astra: '" not in src_alerts)

print("Produktions-Check")
from app.config import ProductionConfig
mk = lambda **kw: type("C", (ProductionConfig,), kw)
issues = lambda **kw: [i for i in mk(**kw).validate_production() if "SITE_NAME" in i or "MAIL_FROM_NAME" in i]
check("Standard und 60 Zeichen bestehen", not issues() and not issues(SITE_NAME="x" * 60))
check("61 Zeichen: KRITISCH", len(issues(SITE_NAME="x" * 61)) == 1 and issues(SITE_NAME="x" * 61)[0].startswith("KRITISCH"))
check("Zeilenumbruch im Namen: KRITISCH", len(issues(SITE_NAME="a\nb")) == 1)
check("MAIL_FROM_NAME zu lang: KRITISCH", len(issues(MAIL_FROM_NAME="y" * 61)) == 1)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
