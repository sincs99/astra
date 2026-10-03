"""M48 – Zahlungsanbieter: Manual/Stripe, Checkout, Webhook (Signatur, Idempotenz), ohne echte Stripe-Aufrufe."""

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

import stripe

from app import create_app
from app.config import ProductionConfig
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order, PaymentEvent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
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
app.config.update(FRONTEND_URL="https://panel.example")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    u1 = User(username="k1", email="k1@t.local")
    u2 = User(username="k2", email="k2@t.local")
    for u in (admin, u1, u2):
        u.set_password("test1234")
    bp = Blueprint(name="mc", docker_image="img", startup_command="run")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=4096, disk_total=100000, cpu_total=400)
    db.session.add_all([admin, u1, u2, bp, agent])
    db.session.commit()
    for i in range(10):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, bp=bp.id, agent=agent.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
U2 = {"X-User-Id": str(ids["u2"])}
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 512, "disk": 1000, "cpu": 50,
                                         "price_cents": 499, "billing_period_days": 30}, headers=AH)
PID = r.json["id"]
n = [0]


def new_order(hdr=U1, product=PID):
    n[0] += 1
    r = c.post("/api/client/orders", json={"product_id": product, "name": f"s{n[0]}"}, headers=hdr)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.json["uuid"]


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"status": o.status, "end": o.current_period_end, "refs": list(o.payment_references or []),
                "instance_id": o.instance_id, "paid_at": o.paid_at}


def event_body(order_uuid, event_id="evt_1", etype="checkout.session.completed", pi="pi_1", amount=499,
               currency="eur", payment_status="paid", extra_meta=None):
    obj = {"id": f"cs_{event_id}", "object": "checkout.session", "payment_status": payment_status,
           "payment_intent": pi, "amount_total": amount, "currency": currency,
           "metadata": {"order_uuid": order_uuid, **(extra_meta or {})}, "client_reference_id": order_uuid}
    return json.dumps({"id": event_id, "object": "event", "type": etype, "api_version": "2024-06-20",
                       "created": int(time.time()), "livemode": False, "data": {"object": obj}}).encode()


def sign(payload: bytes, secret=SECRET, ts=None):
    ts = int(time.time()) if ts is None else ts
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def webhook(payload, header="auto"):
    h = {"Stripe-Signature": sign(payload)} if header == "auto" else ({"Stripe-Signature": header} if header else {})
    return c.post("/api/payments/stripe", data=payload, content_type="application/json", headers=h)


def use_stripe():
    app.config.update(PAYMENT_PROVIDER="stripe", STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET=SECRET)


def events_named(name):
    with app.app_context():
        return ActivityLog.query.filter_by(event=name).count()


print("Manual (Standard)")
check("Standard-Anbieter ist manual", app.config["PAYMENT_PROVIDER"] == "manual")
o_manual = new_order()
r = c.post(f"/api/client/orders/{o_manual}/checkout", headers=U1)
check("Checkout mit manual -> 409 mit Ueberweisungs-Hinweis und code=manual",
      r.status_code == 409 and "Ueberweisung" in r.json["error"] and r.json["code"] == "manual", r.get_data(as_text=True))
check("billing-info: manual, kein Online-Zahlen", c.get("/api/client/billing-info").json == {"payment_provider": "manual", "online_payment": False})
r = webhook(event_body(o_manual))
check("Webhook mit manual -> 404", r.status_code == 404)

print("Stripe: Checkout")
use_stripe()
check("billing-info: stripe", c.get("/api/client/billing-info").json == {"payment_provider": "stripe", "online_payment": True})
o1 = new_order()
fake_session = mock.Mock(url="https://checkout.stripe.test/c/pay_123")
with mock.patch.object(stripe.checkout.Session, "create", return_value=fake_session) as create:
    r = c.post(f"/api/client/orders/{o1}/checkout", headers=U1)
check("Checkout -> 200 mit checkout_url", r.status_code == 200 and r.json == {"checkout_url": "https://checkout.stripe.test/c/pay_123"}, r.get_data(as_text=True))
kw = create.call_args.kwargs
check("mode=payment, Schluessel aus der Konfiguration", kw["mode"] == "payment" and kw["api_key"] == "sk_test_x")
li = kw["line_items"][0]
check("Betrag und Waehrung aus der Bestellung (Cent, klein)", li["price_data"]["unit_amount"] == 499 and li["price_data"]["currency"] == "eur" and li["quantity"] == 1)
check("Metadaten order_uuid an Session und PaymentIntent",
      kw["metadata"] == {"order_uuid": o1} and kw["payment_intent_data"]["metadata"] == {"order_uuid": o1} and kw["client_reference_id"] == o1)
check("success/cancel-URL aus FRONTEND_URL", kw["success_url"] == f"https://panel.example/orders?paid={o1}"
      and kw["cancel_url"] == f"https://panel.example/orders?cancelled={o1}")
check("Kunden-E-Mail vorbelegt", kw["customer_email"] == "k1@t.local")
check("ohne Login -> 401", c.post(f"/api/client/orders/{o1}/checkout").status_code == 401)
check("fremde Bestellung -> 404", c.post(f"/api/client/orders/{o1}/checkout", headers=U2).status_code == 404)
check("unbekannte Bestellung -> 404", c.post("/api/client/orders/gibts-nicht/checkout", headers=U1).status_code == 404)
with mock.patch.object(stripe.checkout.Session, "create", side_effect=stripe.APIConnectionError("netz weg")):
    r = c.post(f"/api/client/orders/{o1}/checkout", headers=U1)
check("Stripe nicht erreichbar -> 502 ohne Interna, code=provider_unavailable",
      r.status_code == 502 and "netz weg" not in r.get_data(as_text=True) and r.json["code"] == "provider_unavailable")
with mock.patch.object(stripe.checkout.Session, "create", return_value=mock.Mock(url=None)):
    r = c.post(f"/api/client/orders/{o1}/checkout", headers=U1)
    check("Antwort ohne URL -> 502, code=provider_error", r.status_code == 502 and r.json["code"] == "provider_error")
for bad_url in ("http://checkout.stripe.test/x", "javascript:alert(1)", "//evil.example/x", ""):
    with mock.patch.object(stripe.checkout.Session, "create", return_value=mock.Mock(url=bad_url)):
        r = c.post(f"/api/client/orders/{o1}/checkout", headers=U1)
    check(f"nur https-URLs werden weitergereicht ({bad_url or 'leer'!r} -> 502)", r.status_code == 502 and "checkout_url" not in r.json)
o_cancel = new_order()
c.post(f"/api/client/orders/{o_cancel}/cancel", headers=U1)
r = c.post(f"/api/client/orders/{o_cancel}/checkout", headers=U1)
check("stornierte Bestellung -> 409 code=invalid_status", r.status_code == 409 and r.json["code"] == "invalid_status")
r = c.post("/api/admin/products", json={"name": "Yen", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50,
                                         "price_cents": 500, "currency": "JPY"}, headers=AH)
o_jpy = new_order(product=r.json["id"])
r = c.post(f"/api/client/orders/{o_jpy}/checkout", headers=U1)
check("Waehrung ohne Nachkommastellen -> 409 code=unsupported_currency", r.status_code == 409 and r.json["code"] == "unsupported_currency")
r = c.post("/api/admin/products", json={"name": "Gratis", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50,
                                         "price_cents": 0, "max_instances_per_user": 2}, headers=AH)
o_free = new_order(product=r.json["id"])
r = c.post(f"/api/client/orders/{o_free}/checkout", headers=U1)
check("Gratis-Bestellung -> 409 code=nothing_to_pay", r.status_code == 409 and r.json["code"] == "nothing_to_pay")

print("Stripe: Webhook-Signatur")
body = event_body(o1)
check("ohne Signatur -> 400", webhook(body, header=None).status_code == 400)
check("falsche Signatur -> 400", webhook(body, header="t=1,v1=abc").status_code == 400)
check("Signatur mit falschem Geheimnis -> 400", webhook(body, header=sign(body, secret="whsec_anderes")).status_code == 400)
check("veralteter Zeitstempel -> 400 (Replay-Schutz)", webhook(body, header=sign(body, ts=int(time.time()) - 3600)).status_code == 400)
check("manipulierter Inhalt -> 400", webhook(body.replace(b"499", b"1"), header=sign(body)).status_code == 400)
check("gueltige Signatur, aber kein JSON -> 400", webhook(b"das ist kein json").status_code == 400)
check("nichts verbucht nach abgelehnten Zustellungen", order(o1)["status"] == "pending_payment")
with app.app_context():
    check("keine payment_events fuer abgelehnte Zustellungen", PaymentEvent.query.count() == 0)

print("Stripe: Erstzahlung")
r = webhook(event_body(o1, "evt_a", pi="pi_a"))
check("gueltiger Webhook -> 200", r.status_code == 200 and r.json["results"][0]["status"] == "processed", r.get_data(as_text=True)[:200])
o = order(o1)
check("Bestellung active mit Instance, Referenz = payment_intent", o["status"] == "active" and o["instance_id"] and o["refs"] == ["pi_a"], str(o))
app.config["ADMIN_GUARD_ENABLED"] = True
r_guard = webhook(event_body(o1, "evt_a", pi="pi_a"))
app.config["ADMIN_GUARD_ENABLED"] = False
check("Webhook braucht keinen Login (auch mit aktivem Admin-Guard erreichbar)", r_guard.status_code == 200)
with app.app_context():
    n_inst = Instance.query.count()
    row = PaymentEvent.query.filter_by(event_id="evt_a").first()
    check("payment_events: processed mit Zeitstempel", row.status == "processed" and row.processed_at and row.order_uuid == o1 and row.provider == "stripe")
r = webhook(event_body(o1, "evt_a", pi="pi_a"))
check("gleiche Event-ID nochmal -> 200, duplicate", r.status_code == 200 and r.json["results"][0]["duplicate"] is True)
with app.app_context():
    check("keine zweite Instance, kein zweiter Eintrag", Instance.query.count() == n_inst and PaymentEvent.query.filter_by(event_id="evt_a").count() == 1)
end_first = order(o1)["end"]
r = webhook(event_body(o1, "evt_b", etype="checkout.session.async_payment_succeeded", pi="pi_a"))
check("anderes Event, gleiche Zahlung (pi_a) -> keine Doppel-Verlaengerung", r.status_code == 200 and order(o1)["end"] == end_first and order(o1)["refs"] == ["pi_a"])

print("Stripe: Verlaengerung")
r = webhook(event_body(o1, "evt_c", pi="pi_c"))
check("zweite Zahlung (pi_c) verlaengert um eine Laufzeit", r.status_code == 200 and order(o1)["end"] == end_first + timedelta(days=30), str(order(o1)["end"]))
check("beide Referenzen gespeichert", order(o1)["refs"] == ["pi_a", "pi_c"])
# ueberfaellig -> Zahlung hebt Sperre auf
from app.domain.billing.service import run_billing_tick
with app.app_context():
    report_install(c, Instance.query.get(order(o1)["instance_id"]).uuid, True)
    run_billing_tick(now=order(o1)["end"] + timedelta(hours=1))
check("Vorbedingung: past_due", order(o1)["status"] == "past_due")
r = webhook(event_body(o1, "evt_d", pi="pi_d"))
with app.app_context():
    inst = db.session.get(Instance, order(o1)["instance_id"])
    check("Zahlung bei past_due: active und entsperrt", order(o1)["status"] == "active" and inst.status is None)

print("Stripe: Sonderfaelle")
o2 = new_order()
r = webhook(event_body(o2, "evt_u", payment_status="unpaid"))
check("payment_status=unpaid wird ignoriert", r.status_code == 200 and r.json["results"][0]["status"] == "ignored" and order(o2)["status"] == "pending_payment")
r = webhook(event_body(o2, "evt_x", etype="payment_intent.created"))
check("anderer Ereignistyp -> 200, ignoriert und protokolliert", r.status_code == 200 and r.json["results"][0]["status"] == "ignored")
r = webhook(event_body("gibts-nicht", "evt_nf", pi="pi_nf"))
check("unbekannte Bestellung -> 200 ignoriert (kein Retry-Sturm)", r.status_code == 200 and r.json["results"][0]["status"] == "ignored")
r = webhook(event_body(o2, "evt_m1", pi="pi_m1", amount=1))
check("Betrag weicht ab -> mismatch, nichts freigeschaltet", r.json["results"][0]["status"] == "mismatch" and order(o2)["status"] == "pending_payment")
r = webhook(event_body(o2, "evt_m2", pi="pi_m2", currency="usd"))
check("Waehrung weicht ab -> mismatch", r.json["results"][0]["status"] == "mismatch" and order(o2)["status"] == "pending_payment")
check("Activity order:payment_unapplied fuer Abweichungen", events_named("order:payment_unapplied") == 2)
with app.app_context():
    check("Abweichungs-Detail gespeichert", "weichen ab" in PaymentEvent.query.filter_by(event_id="evt_m1").first().detail)
o3 = new_order()
c.post(f"/api/client/orders/{o3}/cancel", headers=U1)
r = webhook(event_body(o3, "evt_cn", pi="pi_cn"))
check("Zahlung fuer stornierte Bestellung -> unapplied", r.status_code == 200 and r.json["results"][0]["status"] == "unapplied" and order(o3)["status"] == "cancelled")
check("Event order:payment_unapplied (Erstattung pruefen)", events_named("order:payment_unapplied") == 3)
with app.app_context():
    ev = ActivityLog.query.filter_by(event="order:payment_unapplied").order_by(ActivityLog.id.desc()).first()
    check("Event nennt Zahlungsreferenz", "pi_cn" in str(ev.properties))

print("Stripe: keine Kapazitaet nach Zahlung")
r = c.post("/api/admin/products", json={"name": "Gross", "blueprint_id": ids["bp"], "memory": 4000, "disk": 1000, "cpu": 50,
                                         "price_cents": 999}, headers=AH)
o_big = new_order(product=r.json["id"])
r = webhook(event_body(o_big, "evt_big", pi="pi_big", amount=999))
check("kein Platz: 200 (kein Retry), processed mit Hinweis", r.status_code == 200 and r.json["results"][0]["status"] == "processed")
check("Bestellung bezahlt, aber awaiting_provisioning", order(o_big)["status"] == "awaiting_provisioning" and order(o_big)["refs"] == ["pi_big"])
with app.app_context():
    check("Hinweis im Ereignis", "Bereitstellung ausstehend" in PaymentEvent.query.filter_by(event_id="evt_big").first().detail)
    # Platz schaffen und erneut bereitstellen
    db.session.get(Agent, ids["agent"]).memory_total = 65536
    db.session.commit()
r = c.post(f"/api/admin/orders/{o_big}/mark-paid", headers=AH)
check("Admin stellt spaeter bereit (ohne Doppelverbuchung)", r.status_code == 200 and order(o_big)["status"] == "active" and order(o_big)["refs"] == ["pi_big"])

print("Stripe: Fehler waehrend der Verarbeitung")
o4 = new_order()
real = billing._apply_payment_event
calls = {"n": 0}


def flaky(ev):
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("DB kurz weg")
    return real(ev)


billing._apply_payment_event = flaky
payload = event_body(o4, "evt_flaky", pi="pi_flaky")
r = webhook(payload)
check("interner Fehler -> 500 (Stripe wiederholt)", r.status_code == 500 and "DB kurz weg" not in r.get_data(as_text=True))
with app.app_context():
    row = PaymentEvent.query.filter_by(event_id="evt_flaky").first()
    check("Ereignis bleibt 'received' (nicht final)", row.status == "received" and order(o4)["status"] == "pending_payment")
r = webhook(payload)
billing._apply_payment_event = real
check("Wiederholung verarbeitet es", r.status_code == 200 and r.json["results"][0]["status"] == "processed" and order(o4)["status"] == "active")

print("Konfiguration")


class StripeNoKeys(ProductionConfig):
    PAYMENT_PROVIDER = "stripe"
    STRIPE_SECRET_KEY = ""
    STRIPE_WEBHOOK_SECRET = ""


class UnknownProvider(ProductionConfig):
    PAYMENT_PROVIDER = "paypal"


class StripeOk(ProductionConfig):
    PAYMENT_PROVIDER = "stripe"
    STRIPE_SECRET_KEY = "sk_live_x"
    STRIPE_WEBHOOK_SECRET = "whsec_x"


check("Produktion: stripe ohne Schluessel -> KRITISCH", any("KRITISCH" in i and "STRIPE" in i for i in StripeNoKeys.validate_production()))
check("Produktion: unbekannter Anbieter -> KRITISCH", any("KRITISCH" in i and "paypal" in i for i in UnknownProvider.validate_production()))
check("Produktion: stripe mit Schluesseln -> kein Stripe-Problem", not any("STRIPE" in i or "PAYMENT_PROVIDER" in i for i in StripeOk.validate_production()))
app.config.update(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
r = webhook(event_body(o1, "evt_nokey"))
check("stripe ohne Schluessel: Webhook -> 500 mit klarer Meldung", r.status_code == 500 and "konfiguriert" in r.json["error"])
app.config.update(PAYMENT_PROVIDER="unbekannt")
check("unbekannter Anbieter: Webhook -> 500", webhook(event_body(o1, "evt_unk")).status_code == 500)
app.config.update(PAYMENT_PROVIDER="manual")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
