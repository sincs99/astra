"""M67 – Sprache des Kunden fuer Servertexte: users.locale, Mails und Belege in DE/EN."""

import os
import re
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure import mail
from app.domain.users.models import User
from datetime import datetime, timedelta
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order
from app.domain.billing.payments import PaymentEvent
from app.domain.billing.service import run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.i18n import format_datetime, format_money, tr
from app.i18n.messages import MESSAGES
from app.infrastructure import mail

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
app.config["REGISTRATION_ENABLED"] = True
with app.app_context():
    db.create_all()
    u = User(username="kunde", email="kunde@example.com")
    u.set_password("passwort-1234")
    db.session.add(u)
    db.session.commit()
    uid = u.id
c = app.test_client()
H = {"X-User-Id": str(uid)}


def me():
    return c.get("/api/auth/me", headers=H).json


print("Teil 1: users.locale")
check("Standard: Deutsch", me()["locale"] == "de")
with app.app_context():
    check("in der Datenbank NULL", db.session.get(User, uid).locale is None)
r = c.patch("/api/client/account", json={"locale": "en"}, headers=H)
check("PATCH locale=en: 200 mit Nutzerobjekt", r.status_code == 200 and r.json["locale"] == "en" and r.json["username"] == "kunde", str(r.json))
check("/api/auth/me liefert en", me()["locale"] == "en")
for bad in ("fr", "EN", "en-US", "", None, 5, ["en"]):
    r = c.patch("/api/client/account", json={"locale": bad}, headers=H)
    check(f"ungueltig {bad!r}: 400 invalid_locale", r.status_code == 400 and r.json.get("code") == "invalid_locale", str(r.json))
check("nach Fehlversuchen weiter en", me()["locale"] == "en")
check("leerer Body: 400", c.patch("/api/client/account", json={}, headers=H).status_code == 400)
check("ohne Anmeldung: 401", c.patch("/api/client/account", json={"locale": "de"}).status_code == 401)
r = c.patch("/api/client/account", json={"locale": "de"}, headers=H)
check("zurueck auf de", r.json["locale"] == "de")

print("Registrierung")
r = c.post("/api/auth/register", json={"username": "neu1", "email": "neu1@example.com", "password": "geheim1234", "locale": "en"})
check("Registrierung mit locale=en", r.status_code == 201 and r.json["user"]["locale"] == "en", str(r.json))
r = c.post("/api/auth/register", json={"username": "neu2", "email": "neu2@example.com", "password": "geheim1234"})
check("ohne locale: de", r.status_code == 201 and r.json["user"]["locale"] == "de")
r = c.post("/api/auth/register", json={"username": "neu3", "email": "neu3@example.com", "password": "geheim1234", "locale": "xx"})
check("ungueltige locale: 400, kein Konto", r.status_code == 400 and "Sprache" in r.json["error"])
with app.app_context():
    check("Konto neu3 wurde nicht angelegt", User.query.filter_by(username="neu3").first() is None)

print("Migration")
from app.i18n import normalize_locale
check("normalize_locale: en-US, EN, de_DE, unbekannt, None", [normalize_locale(x) for x in ("en-US", "EN", "de_DE", "fr", None)] == ["en", "en", "de", "de", "de"])
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    dbp = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{dbp}", "RUNNER_ADAPTER": "stub", "FLASK_APP": "app:create_app"}
    subprocess.run([sys.executable, "-c", "from app import create_app;from app.extensions import db;a=create_app()\nwith a.app_context(): db.create_all()"],
                   env=env, check=True, capture_output=True, cwd=cwd)
    con = sqlite3.connect(dbp)
    con.execute("alter table users drop column locale")
    con.execute("insert into users (username,email,password_hash,is_admin) values ('alt','alt@x','h',0)")
    con.commit()
    run = lambda *a: subprocess.run([sys.executable, "-m", "flask", "db", *a], env=env, capture_output=True, text=True, cwd=cwd)
    stamp = run("stamp", "v2q3r4s5t6u7")
    up = run("upgrade")
    cols = {r[1] for r in sqlite3.connect(dbp).execute("pragma table_info(users)")}
    keep = sqlite3.connect(dbp).execute("select username, locale from users").fetchall()
    up2 = run("upgrade")
    down = run("downgrade", "v2q3r4s5t6u7")
    cols_down = {r[1] for r in sqlite3.connect(dbp).execute("pragma table_info(users)")}
    heads = run("heads")
check("stamp + upgrade ok, Spalte vorhanden, Bestandsnutzer behalten (locale NULL)", stamp.returncode == 0 and up.returncode == 0 and "locale" in cols and keep == [("alt", None)], up.stderr[-300:])
check("zweites upgrade (Inspector-Guard) ok", up2.returncode == 0)
check("downgrade entfernt die Spalte", down.returncode == 0 and "locale" not in cols_down, down.stderr[-300:])
check("genau ein Migrations-Head", heads.stdout.count("(head)") == 1, heads.stdout[-100:])

print("Teil 2: Uebersetzungen")
fmt = lambda t: set(re.findall(r"\{(\w+)\}", t))
check("DE und EN haben dieselben Schluessel", set(MESSAGES["de"]) == set(MESSAGES["en"]), str(set(MESSAGES["de"]) ^ set(MESSAGES["en"])))
check("dieselben Platzhalter je Schluessel", all(fmt(MESSAGES["de"][k]) == fmt(MESSAGES["en"][k]) for k in MESSAGES["de"]),
      str([k for k in MESSAGES["de"] if fmt(MESSAGES["de"][k]) != fmt(MESSAGES["en"][k])]))
check("EN-Texte sind wirklich uebersetzt (keine Kopie des Deutschen)", all(MESSAGES["de"][k] != MESSAGES["en"][k]
      for k in MESSAGES["de"] if len(MESSAGES["de"][k]) > 12), str([k for k in MESSAGES["de"] if len(MESSAGES["de"][k]) > 12 and MESSAGES["de"][k] == MESSAGES["en"][k]]))
check("tr: Fallback Deutsch bei unbekannter Sprache und None", tr("fr", "receipt.number") == "Belegnummer" and tr(None, "receipt.number") == "Belegnummer")
check("tr: EN", tr("en", "receipt.number") == "Receipt number")
check("tr: unbekannter Schluessel liefert den Schluessel", tr("en", "gibt.es.nicht") == "gibt.es.nicht")
check("tr: fehlender Platzhalter wirft nicht", "{uuid}" in tr("en", "mail.renewed.body", instance_name="x", end="y"))
d = datetime(2026, 10, 4, 14, 5)
check("Datum DE/EN", format_datetime("de", d) == "04.10.2026 14:05 UTC" and format_datetime("en", d) == "4 Oct 2026, 14:05 UTC")
check("Betrag DE/EN", format_money("de", 123456, "EUR") == "1.234,56 EUR" and format_money("en", 123456, "EUR") == "\u20ac1,234.56"
      and format_money("en", 250, "USD") == "$2.50" and format_money("en", 250, "CHF") == "CHF 2.50")

print("Mails und Belege je Sprache")
with app.app_context():
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    admin.set_password("x-passwort-1")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=100000, disk_total=1000000, cpu_total=800)
    bp = Blueprint(name="Minecraft Paper", docker_image="img", startup_command="run")
    db.session.add_all([admin, agent, bp])
    db.session.commit()
    for i in range(10):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    adm_id, bp_id, agent_id = admin.id, bp.id, agent.id
AH = {"X-User-Id": str(adm_id)}
r = c.post("/api/admin/products", json={"name": "Klein", "blueprint_id": bp_id, "memory": 600, "disk": 500, "cpu": 50,
                                         "price_cents": 123456, "billing_period_days": 30}, headers=AH)
PID = r.json["id"]
n = [0]


def new_order():
    n[0] += 1
    return c.post("/api/client/orders", json={"product_id": PID, "name": f"srv{n[0]}"}, headers=H).json["uuid"]


def pay(ou, ref):
    return c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)


def mails_for(ou, to="kunde@example.com"):
    return [m for m in mail.outbox if m["to"] == to and ou in m["body"]]


def set_locale(loc):
    with app.app_context():
        db.session.get(User, uid).locale = loc
        db.session.commit()


def order_state(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"end": o.current_period_end, "purpose": o.payment_purpose, "id": o.id}


# -- Deutsch (Standard) bleibt unveraendert --
set_locale(None)
o_de = new_order()
mail.outbox.clear()
pay(o_de, "pi_de")
ms = mails_for(o_de)
check("DE: Server bereit wie bisher", len(ms) == 1 and ms[0]["subject"] == "Astra: Dein Server ist bereit" and "deine Zahlung ist eingegangen und dein Server" in ms[0]["body"], str(ms))
mail.outbox.clear()
pay(o_de, "pi_de2")
ms = mails_for(o_de)
st = order_state(o_de)
check("DE: Verlaengerung mit deutschem Datum", len(ms) == 1 and ms[0]["subject"] == "Astra: Zahlung eingegangen, Server verlängert"
      and f"{st['end']:%d.%m.%Y %H:%M} UTC" in ms[0]["body"], str(ms))

# -- Englisch --
set_locale("en")
o_en = new_order()
st = order_state(o_en)
mail.outbox.clear()
pay(o_en, "pi_en")
ms = mails_for(o_en)
check("EN: 'Your server is ready' mit Anrede und Adresse", len(ms) == 1 and ms[0]["subject"] == "Astra: Your server is ready"
      and ms[0]["body"].startswith("Hello,") and "we received your payment and your server" in ms[0]["body"]
      and "Connection address:" in ms[0]["body"] and f"Order: {o_en}" in ms[0]["body"], str(ms))
check("EN: kein deutscher Text in der Mail", not re.search(r"Hallo|Bestellung|Verbindungsadresse|Zahlung", ms[0]["subject"] + ms[0]["body"]))
mail.outbox.clear()
pay(o_en, "pi_en2")
ms = mails_for(o_en)
end = order_state(o_en)["end"]
check("EN: Verlaengerung mit englischem Datum", len(ms) == 1 and ms[0]["subject"] == "Astra: Payment received, server renewed"
      and format_datetime("en", end) in ms[0]["body"], str(ms))

o_wait = new_order()
with app.app_context():
    db.session.get(Agent, agent_id).memory_total = 100  # kein Platz fuer 600 MB
    db.session.commit()
mail.outbox.clear()
r = pay(o_wait, "pi_wait")
ms = mails_for(o_wait)
check("EN: 'Payment received' bei fehlendem Platz", r.status_code == 409 and len(ms) == 1 and ms[0]["subject"] == "Astra: Payment received"
      and "no free capacity" in ms[0]["body"], str(ms))
with app.app_context():
    db.session.get(Agent, agent_id).memory_total = 100000
    db.session.commit()
mail.outbox.clear()
with app.app_context():
    run_billing_tick(datetime.utcnow() + timedelta(minutes=1))
ms = mails_for(o_wait)
check("EN: spaetere Bereitstellung durch den Tick", len(ms) == 1 and ms[0]["subject"] == "Astra: Your server is ready" and "your server '" in ms[0]["body"], str(ms))

# Erinnerung, Sperre, Loeschhinweis, Beendet (Tick)
o_t = new_order()
pay(o_t, "pi_t")
end_t = order_state(o_t)["end"]
purpose = order_state(o_t)["purpose"]
REM = app.config["BILLING_REMINDER_DAYS"]
mail.outbox.clear()
with app.app_context():
    run_billing_tick(end_t - timedelta(days=REM) + timedelta(minutes=1))
ms = mails_for(o_t)
check("EN: Erinnerung mit Betrag in Euro, Datum und Verwendungszweck", len(ms) == 1 and ms[0]["subject"] == "Astra: The term of your server ends soon"
      and "\u20ac1,234.56 for 30 days" in ms[0]["body"] and format_datetime("en", end_t) in ms[0]["body"]
      and f"Payment reference: {purpose}" in ms[0]["body"], str(ms))
mail.outbox.clear()
with app.app_context():
    run_billing_tick(end_t + timedelta(hours=1))
ms = mails_for(o_t)
check("EN: Sperre mit Frist und Verwendungszweck", len(ms) == 1 and ms[0]["subject"] == "Astra: Payment overdue \u2013 your server has been suspended"
      and "within 7 days" in ms[0]["body"] and f"Payment reference: {purpose}" in ms[0]["body"], str(ms))
mail.outbox.clear()
with app.app_context():
    run_billing_tick(end_t + timedelta(days=8))
ms = mails_for(o_t)
check("EN: Beendet mit uebersetztem Grund", len(ms) == 1 and ms[0]["subject"] == "Astra: Your server has been terminated"
      and "(payment not received)" in ms[0]["body"], str(ms))

o_c = new_order()
pay(o_c, "pi_c")
c.post(f"/api/client/orders/{o_c}/cancel", headers=H)
end_c = order_state(o_c)["end"]
mail.outbox.clear()
with app.app_context():
    run_billing_tick(end_c - timedelta(days=1))
ms = mails_for(o_c)
check("EN: Loeschhinweis nach Kuendigung", len(ms) == 1 and ms[0]["subject"] == "Astra: Your server will be deleted soon"
      and format_datetime("en", end_c) in ms[0]["body"], str(ms))
mail.outbox.clear()
with app.app_context():
    run_billing_tick(end_c + timedelta(hours=1))
ms = mails_for(o_c)
check("EN: Beendet wegen Kuendigung", len(ms) == 1 and "(cancellation at the end of the term)" in ms[0]["body"], str(ms))

# Erstattung
o_r = new_order()
pay(o_r, "pi_r")
mail.outbox.clear()
with app.app_context():
    ev = PaymentEvent("evt_r", "charge.refunded", "refunded", payment_reference="pi_r", amount_cents=123456, currency="EUR",
                      full_refund=True, refunded_cents=123456)
    billing.process_payment_events("stripe", [ev])
ms = mails_for(o_r)
check("EN: Erstattung", len(ms) == 1 and ms[0]["subject"] == "Astra: Payment refunded \u2013 your server has been suspended" and "after 7 days" in ms[0]["body"], str(ms))

# Konto-Mails
app.config["EMAIL_VERIFICATION_REQUIRED"] = True
mail.outbox.clear()
c.post("/api/auth/register", json={"username": "engl", "email": "engl@example.com", "password": "geheim1234", "locale": "en"})
ms = [m for m in mail.outbox if m["to"] == "engl@example.com"]
check("EN: Bestaetigungs-Mail bei Registrierung", len(ms) == 1 and ms[0]["subject"] == "Astra: Confirm your email address" and ms[0]["body"].startswith("Hello engl,")
      and "/verify-email?token=" in ms[0]["body"], str(ms))
mail.outbox.clear()
c.post("/api/auth/register", json={"username": "deut", "email": "deut@example.com", "password": "geheim1234"})
ms = [m for m in mail.outbox if m["to"] == "deut@example.com"]
check("DE: Bestaetigungs-Mail unveraendert", len(ms) == 1 and ms[0]["subject"] == "Astra: E-Mail-Adresse bestätigen" and ms[0]["body"].startswith("Hallo deut,"))
app.config["EMAIL_VERIFICATION_REQUIRED"] = False
mail.outbox.clear()
c.post("/api/auth/password-reset/request", json={"email": "kunde@example.com"})
ms = [m for m in mail.outbox if m["to"] == "kunde@example.com"]
check("EN: Passwort-Reset-Mail", len(ms) == 1 and ms[0]["subject"] == "Astra: Reset your password" and "valid for 60 minutes" in ms[0]["body"] and "/password-reset/confirm?token=" in ms[0]["body"], str(ms))
mail.outbox.clear()
c.post("/api/auth/password-reset/request", json={"email": "deut@example.com"})
ms = [m for m in mail.outbox if m["to"] == "deut@example.com"]
check("DE: Passwort-Reset-Mail unveraendert", len(ms) == 1 and ms[0]["subject"] == "Astra: Passwort zurücksetzen")
from app.api.auth.routes import _notify_recovery_used
mail.outbox.clear()
with app.test_request_context():
    with app.app_context():
        _notify_recovery_used(db.session.get(User, uid), 1)
ms = [m for m in mail.outbox if m["to"] == "kunde@example.com"]
check("EN: Recovery-Code-Mail mit Hinweis auf neue Codes", len(ms) == 1 and ms[0]["subject"] == "Astra: Recovery code used"
      and "1 codes are left" in ms[0]["body"] and "generate new codes" in ms[0]["body"], str(ms))

# Belege
rc = c.get(f"/api/client/orders/{o_en}/receipt?format=text", headers=H).get_data(as_text=True)
check("EN-Beleg (Text): Titel, Zeilenbezeichnungen, Betrag, Datum, Verwendungszweck", all(x in rc for x in [
    "PAYMENT RECEIPT", "Receipt number: ", "Customer: kunde", "Service: Game server plan Klein (Minecraft Paper), server 'srv", "Term: 30 days",
    "Amount: \u20ac1,234.56", "Payment reference: ASTRA-", "Transaction reference: pi_en2", "not an invoice for VAT purposes"]), rc)
check("EN-Beleg: kein deutscher Text", not re.search(r"Belegnummer|Betrag|Laufzeit|Zahlungsbeleg|Verwendungszweck|Leistung", rc))
check("EN-Beleg: englisches Datum", re.search(r"Date: \d{1,2} [A-Z][a-z]{2} \d{4} \(UTC\)", rc) is not None, rc)
rh = c.get(f"/api/client/orders/{o_en}/receipt", headers=H).get_data(as_text=True)
check("EN-Beleg (HTML): lang=en, Titel", '<html lang="en">' in rh and "<h1>Payment receipt</h1>" in rh)
set_locale("de")
rc_de = c.get(f"/api/client/orders/{o_en}/receipt?format=text", headers=H).get_data(as_text=True)
check("nach Wechsel auf de wird derselbe Beleg deutsch gerendert", "ZAHLUNGSBELEG" in rc_de and "Betrag: 1.234,56 EUR" in rc_de and "Verwendungszweck: ASTRA-" in rc_de, rc_de)
check("Beleg-JSON unabhaengig von der Sprache", c.get(f"/api/client/orders/{o_en}/receipt?format=json", headers=H).json["amount_cents"] == 123456)
set_locale("fr")  # direkt in der Datenbank: unbekannte Sprache faellt auf Deutsch zurueck
mail.outbox.clear()
pay(new_order(), "pi_fr")
check("unbekannte gespeicherte Sprache: Mail auf Deutsch", any(m["subject"] == "Astra: Dein Server ist bereit" for m in mail.outbox))
check("to_dict liefert fuer eine unbekannte gespeicherte Sprache 'de'", c.get("/api/auth/me", headers=H).json["locale"] == "de")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
