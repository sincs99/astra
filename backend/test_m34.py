"""M34 – Tests fuer Selbstregistrierung und Passwort-Reset."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
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
with app.app_context():
    db.create_all()
    c = app.test_client()
    reg = {"username": "neu", "email": "Neu@Example.com", "password": "geheim123"}

    print("Registrierung")
    r = c.post("/api/auth/register", json=reg)
    check("deaktiviert -> 403", r.status_code == 403, r.get_data(as_text=True))

    app.config["REGISTRATION_ENABLED"] = True
    r = c.post("/api/auth/register", json=reg)
    check("aktiv -> 201", r.status_code == 201, r.get_data(as_text=True))
    check("Token + kein Admin", bool(r.json.get("access_token")) and not r.json["user"]["is_admin"])
    check("E-Mail normalisiert", r.json["user"]["email"] == "neu@example.com")
    r = c.post("/api/auth/register", json={**reg, "username": "x", "email": "NEU@example.com"})
    check("doppelte E-Mail -> 409", r.status_code == 409)
    r = c.post("/api/auth/register", json={**reg, "email": "a@b.de"})
    check("doppelter Name -> 409", r.status_code == 409)
    r = c.post("/api/auth/register", json={**reg, "username": "y", "email": "y@b.de", "password": "kurz"})
    check("kurzes Passwort -> 400", r.status_code == 400)
    r = c.post("/api/auth/register", json={**reg, "username": "z", "email": "kaputt"})
    check("ungueltige E-Mail -> 400", r.status_code == 400)
    r = c.post("/api/auth/login", json={"login": "neu", "password": "geheim123"})
    check("Login mit neuem Account", r.status_code == 200)

    print("Passwort-Reset")
    mail.outbox.clear()
    r = c.post("/api/auth/password-reset/request", json={"email": "unbekannt@example.com"})
    check("unbekannte Adresse -> 200, keine Mail", r.status_code == 200 and not mail.outbox)
    r = c.post("/api/auth/password-reset/request", json={"email": "neu@example.com"})
    check("bekannte Adresse -> 200 + Mail", r.status_code == 200 and len(mail.outbox) == 1)
    token = mail.outbox[0]["body"].split("token=")[1].split()[0]

    r = c.post("/api/auth/password-reset/confirm", json={"token": "muell", "password": "neues-passwort"})
    check("ungueltiges Token -> 400", r.status_code == 400)
    r = c.post("/api/auth/password-reset/confirm", json={"token": token, "password": "kurz"})
    check("kurzes neues Passwort -> 400", r.status_code == 400)
    r = c.post("/api/auth/password-reset/confirm", json={"token": token, "password": "neues-passwort"})
    check("Reset erfolgreich", r.status_code == 200, r.get_data(as_text=True))
    r = c.post("/api/auth/login", json={"login": "neu", "password": "neues-passwort"})
    check("Login mit neuem Passwort", r.status_code == 200)
    r = c.post("/api/auth/login", json={"login": "neu", "password": "geheim123"})
    check("altes Passwort ungueltig", r.status_code == 401)
    r = c.post("/api/auth/password-reset/confirm", json={"token": token, "password": "nochmal-neu-1"})
    check("Token nur einmal nutzbar", r.status_code == 400)

    app.config["PASSWORD_RESET_TTL_MINUTES"] = 0
    mail.outbox.clear()
    c.post("/api/auth/password-reset/request", json={"email": "neu@example.com"})
    t2 = mail.outbox[0]["body"].split("token=")[1].split()[0]
    import time; time.sleep(1.1)
    r = c.post("/api/auth/password-reset/confirm", json={"token": t2, "password": "nochmal-neu-1"})
    check("abgelaufenes Token -> 400", r.status_code == 400)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
