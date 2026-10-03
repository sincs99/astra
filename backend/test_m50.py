"""M50 – Kundenmeldungen mit echten Umlauten (API-Antworten und Mails)."""

import email
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.users.models import User
from app.infrastructure import mail
from tools import umlauts
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


print("Werkzeug tools/umlauts.py")
check("Ersetzung ganzer Wörter", umlauts.fix("Ungueltige Daten fuer den Kunden, geloescht und zurueck") ==
      "Ungültige Daten für den Kunden, gelöscht und zurück")
keep = "neue zuerst aktuell Blueprint queue Request sequence true continue manuell Query values due enqueued"
check("Wörter ohne Umlaut-Bedeutung bleiben unverändert", umlauts.fix(keep) == keep)
check("nur ganze Wörter (kein Teilwort-Treffer)", umlauts.fix("fuerst Zurueckhaltung Ueberweisungen") == "fuerst Zurueckhaltung Ueberweisungen")
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "sample.py")
    open(p, "w", encoding="utf-8").write(
        '"""Docstring mit fuer und geloescht bleibt."""\n'
        "import logging\nlogger = logging.getLogger(__name__)\n"
        "def f(name):\n"
        '    """Noch ein Docstring: ungueltig."""\n'
        "    # Kommentar: fuer niemanden\n"
        '    logger.warning("Log fuer Entwickler: geloescht")\n'
        '    msg = {"error": "Ungueltige Eingabe fuer " + name, "code": "invalid_status"}\n'
        '    note = f"Instance \'{name}\' geloescht, neue Instance folgt"\n'
        "    return msg, note\n")
    n = umlauts.process(p, write=True)
    out = open(p, encoding="utf-8").read()
check("zwei Meldungstexte korrigiert", n == 2, str(n))
check("API-Meldung und f-String haben Umlaute", "Ungültige Eingabe für " in out and "gelöscht, neue Instance folgt" in out)
check("Docstrings, Kommentar und Log-Aufruf bleiben unberührt",
      "Docstring mit fuer und geloescht bleibt" in out and "Noch ein Docstring: ungueltig" in out
      and "# Kommentar: fuer niemanden" in out and "Log fuer Entwickler: geloescht" in out)
check("Code (Fehlercode, Namen) bleibt unverändert", '"code": "invalid_status"' in out and "def f(name)" in out)
check("Datei bleibt gültiges Python", compile(out, p, "exec") is not None)
files = umlauts.customer_files()
check(f"Kundendateien gefunden ({len(files)})", len(files) >= 25)
left = {os.path.relpath(f, umlauts.BACKEND): umlauts.process(f, write=False) for f in files}
left = {k: v for k, v in left.items() if v}
check("in keiner Kundendatei steckt noch eine ASCII-Schreibweise aus dem Wörterbuch", not left, str(left))

TRANSLIT = re.compile(r"\b(fuer|Fuer|ueber|Ueber|[Uu]ngueltig\w*|gueltig\w*|geloescht|[Ll]oesch\w*|zurueck\w*|[Bb]estaetig\w*|"
                      r"Ueberweisung\w*|Waehrung|[Vv]erlaeng\w*|moeglich|spaeter|laeuft|gehoert|[Kk]uendig\w*|[Uu]eberfaellig\w*|"
                      r"verfuegbar|Kapazitaet|hoechstens|unterstuetz\w*|[Pp]rueft|pruefen)\b")

app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    own = User(username="own", email="own@t.local")
    other = User(username="oth", email="oth@t.local")
    for u in (admin, own, other):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=2048, disk_total=100000, cpu_total=400)
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([admin, own, other, agent, bp])
    db.session.commit()
    for i in range(6):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, own=own.id, oth=other.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["own"])}
app.config["REGISTRATION_ENABLED"] = True
texts = []


def record(resp, label=None):
    j = resp.get_json(silent=True) or {}
    for key in ("error", "message"):
        if isinstance(j.get(key), str):
            texts.append((label or resp.request.path, j[key]))
    return resp


print("API-Antworten mit Umlauten")
r = record(c.post("/api/auth/login", json={"login": "own", "password": "falsch"}))
check("Login: Ungültige Anmeldedaten", r.status_code == 401 and r.json["error"] == "Ungültige Anmeldedaten")
r = record(c.post("/api/auth/verify-email", json={"token": "x"}))
check("E-Mail bestätigen: ungültiger Link", r.status_code == 400 and r.json["error"] == "Ungültiger Bestätigungs-Link")
r = record(c.post("/api/auth/password-reset/confirm", json={"token": "x", "password": "neues-passwort"}))
check("Passwort-Reset: ungültiger Link", r.json["error"] == "Ungültiger Reset-Link")
tok = c.post("/api/auth/login", json={"login": "own", "password": "test1234"}).json["access_token"]
r = record(c.post("/api/auth/change-password", json={"current_password": "x", "new_password": "ganz-neu-123"},
                  headers={"Authorization": f"Bearer {tok}"}))
check("Passwort ändern: falsches Passwort bleibt 401", r.status_code == 401)
r = record(c.post("/api/auth/change-password", json={"current_password": "test1234", "new_password": "ganz-neu-123"},
                  headers={"Authorization": f"Bearer {tok}"}))
check("Passwort ändern: Erfolgsmeldung", r.json["message"] == "Passwort wurde geändert")
r = record(c.post("/api/auth/register", json={"username": "x", "email": "kaputt", "password": "geheim123"}))
check("Registrierung: ungültige E-Mail", r.json["error"] == "Ungültige E-Mail-Adresse")

# Instance, Bestellung, Löschen
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 512, "disk": 1000, "cpu": 50,
                                         "price_cents": 100}, headers=AH)
pid = r.json["id"]
r = c.post("/api/client/orders", json={"product_id": pid, "name": "srv"}, headers=OH)
ou = r.json["uuid"]
r = record(c.post(f"/api/client/orders/{ou}/checkout", headers=OH))
check("Checkout mit manual: Überweisung, Code unverändert", r.status_code == 409 and "Überweisung" in r.json["error"] and r.json["code"] == "manual")
c.post(f"/api/client/orders/{ou}/cancel", headers=OH)
r = record(c.post(f"/api/client/orders/{ou}/checkout", headers=OH))
check("Checkout: Code invalid_status unverändert", r.json["code"] == "invalid_status")
r = record(c.delete(f"/api/admin/products/{pid}", headers=AH))
check("Produkt löschen: gelöscht/deaktivieren", r.status_code == 409 and "gelöscht" in r.json["error"] and "deaktivieren" in r.json["error"])

o2 = c.post("/api/client/orders", json={"product_id": pid, "name": "srv2"}, headers=OH).json["uuid"]
c.post(f"/api/admin/orders/{o2}/mark-paid", json={"payment_reference": "ref1"}, headers=AH)
r = record(c.post(f"/api/admin/orders/{o2}/mark-paid", headers=AH))
check("Verlängerung ohne Referenz: Für eine Verlängerung", r.status_code == 400 and r.json["error"].startswith("Für eine Verlängerung"))
iu = c.get(f"/api/client/orders/{o2}", headers=OH).json["instance_uuid"]
with app.app_context():
    report_install(c, iu, True)  # Wings meldet die abgeschlossene Installation
r = record(c.delete(f"/api/client/instances/{iu}", json={}, headers=OH))
check("Instance löschen ohne confirm: Bestätigung fehlt", r.status_code == 400 and r.json["error"].startswith("Bestätigung fehlt"))
r = record(c.delete(f"/api/client/instances/{iu}", json={"confirm": "srv2"}, headers=OH))
check("Instance gelöscht", r.status_code == 200 and r.json["message"] == "Instance gelöscht")
r = record(c.post("/api/admin/instances", json={"name": "zu-gross", "owner_id": ids["own"], "blueprint_id": ids["bp"],
                                                "memory": 99999}, headers=AH))
check("Kapazität: ausreichender Kapazität verfügbar", r.status_code == 409 and "Kapazität verfügbar" in r.json["error"])
r = record(c.post("/api/client/account/ssh-keys", json={"name": "k", "public_key": "ssh-ed25519"}, headers=OH))
check("SSH-Key: ungültiges Format", r.status_code == 400 and "Ungültiges Key-Format" in r.json["error"], r.get_data(as_text=True))

print("Mails mit Umlauten")
mail.outbox.clear()
c.post("/api/auth/password-reset/request", json={"email": "own@t.local"})
c.post("/api/auth/register", json={"username": "neu", "email": "neu@example.com", "password": "geheim123"})
app.config["EMAIL_VERIFICATION_REQUIRED"] = True
c.post("/api/auth/register", json={"username": "neu2", "email": "neu2@example.com", "password": "geheim123"})
app.config["EMAIL_VERIFICATION_REQUIRED"] = False
subjects = [m["subject"] for m in mail.outbox]
check("Reset-Mail: Passwort zurücksetzen", any(s == "Astra: Passwort zurücksetzen" for s in subjects), str(subjects))
check("Verifizierungs-Mail: bestätigen", any(s == "Astra: E-Mail-Adresse bestätigen" for s in subjects), str(subjects))
check("Mail-Text mit Umlauten", any("über diesen Link" in m["body"] and "gültig" in m["body"] for m in mail.outbox))
for m in mail.outbox:
    texts.append((f"Mail {m['subject']}", m["subject"] + "\n" + m["body"]))

# Billing-Tick-Mails
from app.domain.billing.service import run_billing_tick
from app.domain.billing.models import Order
o3 = c.post("/api/client/orders", json={"product_id": pid, "name": "srv3"}, headers=OH).json["uuid"]
c.post(f"/api/admin/orders/{o3}/mark-paid", json={"payment_reference": "ref3"}, headers=AH)
with app.app_context():
    report_install(c, c.get(f"/api/client/orders/{o3}", headers=OH).json["instance_uuid"], True)
    e3 = Order.query.filter_by(uuid=o3).first().current_period_end
    mail.outbox.clear()
    run_billing_tick(now=e3 - timedelta(days=2))            # Erinnerung
    run_billing_tick(now=e3 + timedelta(hours=1))           # überfällig
    run_billing_tick(now=e3 + timedelta(days=8))            # gelöscht
tick_subjects = [m["subject"] for m in mail.outbox]
check("Tick-Mails: Laufzeit endet bald / überfällig / beendet",
      "Astra: Die Laufzeit deines Servers endet bald" in tick_subjects
      and "Astra: Zahlung überfällig – dein Server wurde gesperrt" in tick_subjects
      and "Astra: Dein Server wurde beendet" in tick_subjects, str(tick_subjects))
check("Tick-Mail-Text: gelöscht, für", any("gelöscht" in m["body"] for m in mail.outbox) and any("für" in m["body"] for m in mail.outbox))
for m in mail.outbox:
    texts.append((f"Mail {m['subject']}", m["subject"] + "\n" + m["body"]))

print("Keine ASCII-Schreibweisen in Kundenmeldungen")
bad = [(src, t) for src, t in texts if TRANSLIT.search(t)]
check(f"{len(texts)} Meldungen und Mails geprüft, keine mit ASCII-Umlautersatz", not bad, str(bad[:3]))
check("genug Material geprüft", len(texts) >= 15, str(len(texts)))

print("Mailversand per SMTP mit Umlauten")
sent = {}


class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, user, pw):
        pass

    def send_message(self, msg):
        sent["msg"] = msg


app.config.update(TESTING=False, MAIL_SERVER="smtp.test", MAIL_PORT=25, MAIL_USE_TLS=False)
with mock.patch("app.infrastructure.mail.smtplib.SMTP", FakeSMTP):
    ok = mail.send_mail(app, "kunde@example.com", "Astra: Zahlung überfällig – gesperrt", "Hallo,\n\nüber Überweisung zahlen.\n")
app.config.update(TESTING=True, MAIL_SERVER="")
check("send_mail meldet Erfolg", ok is True)
raw = sent["msg"].as_bytes()
parsed = email.message_from_bytes(raw)
decoded_subject = str(email.header.make_header(email.header.decode_header(parsed["Subject"])))
check("Betreff überlebt die Kodierung", decoded_subject == "Astra: Zahlung überfällig – gesperrt", decoded_subject)
body = parsed.get_payload(decode=True).decode(parsed.get_content_charset() or "utf-8")
check("Text überlebt die Kodierung (UTF-8)", "Überweisung" in body and "über" in body and (parsed.get_content_charset() or "").lower() == "utf-8")

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
