"""M38 – E-Mail-Verifizierung bei Registrierung."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure import mail
from app.domain.users.models import User

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


def token_from_mail(i=-1):
    return mail.outbox[i]["body"].split("token=")[1].split()[0]


app = create_app("testing")
app.config["REGISTRATION_ENABLED"] = True

with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    admin.set_password("test1234")
    db.session.add(admin)
    db.session.commit()
    admin_id = admin.id

c = app.test_client()
reg = {"username": "neu", "email": "neu@example.com", "password": "geheim123"}

print("Flag aus (Standard)")
check("Standard ist aus", app.config["EMAIL_VERIFICATION_REQUIRED"] is False)
mail.outbox.clear()
r = c.post("/api/auth/register", json=reg)
check("Registrierung liefert Token, keine Mail", r.status_code == 201 and "access_token" in r.json and not mail.outbox)
check("Nutzer unbestaetigt", r.json["user"]["email_verified"] is False)
check("Login funktioniert trotzdem",
      c.post("/api/auth/login", json={"login": "neu", "password": "geheim123"}).status_code == 200)

print("Flag an")
app.config["EMAIL_VERIFICATION_REQUIRED"] = True
mail.outbox.clear()
r = c.post("/api/auth/register", json={"username": "v", "email": "v@example.com", "password": "geheim123"})
check("Registrierung -> 201 ohne Token", r.status_code == 201 and "access_token" not in r.json
      and r.json["verification_required"] is True, r.get_data(as_text=True))
check("Verifizierungs-Mail gesendet", len(mail.outbox) == 1 and mail.outbox[0]["to"] == "v@example.com")
check("Verify-Link zeigt auf Frontend-Route /verify-email", "/verify-email?token=" in mail.outbox[0]["body"])
tok = token_from_mail()
r = c.post("/api/auth/login", json={"login": "v", "password": "geheim123"})
check("Login vor Bestaetigung -> 403 email_not_verified", r.status_code == 403 and r.json.get("code") == "email_not_verified")
r = c.post("/api/auth/login", json={"login": "v", "password": "falsch"})
check("falsches Passwort -> weiter 401 (kein Status-Leak)", r.status_code == 401)
r = c.post("/api/auth/login", json={"login": "neu", "password": "geheim123"})
check("Altnutzer ohne Bestaetigung -> 403", r.status_code == 403)

r = c.post("/api/auth/verify-email", json={"token": "muell"})
check("ungueltiges Token -> 400", r.status_code == 400)
r = c.post("/api/auth/verify-email", json={"token": tok})
check("Token gueltig -> 200", r.status_code == 200, r.get_data(as_text=True))
r = c.post("/api/auth/login", json={"login": "v", "password": "geheim123"})
check("Login nach Bestaetigung -> 200", r.status_code == 200 and r.json["user"]["email_verified"] is True)
check("Token erneut nutzbar (idempotent)", c.post("/api/auth/verify-email", json={"token": tok}).status_code == 200)

print("Erneut senden")
mail.outbox.clear()
c.post("/api/auth/resend-verification", json={"email": "unbekannt@example.com"})
check("unbekannte Adresse -> keine Mail", not mail.outbox)
c.post("/api/auth/resend-verification", json={"email": "v@example.com"})
check("bereits bestaetigt -> keine Mail", not mail.outbox)
r = c.post("/api/auth/resend-verification", json={"login": "neu"})
check("Benutzername statt Adresse -> Mail", r.status_code == 200 and len(mail.outbox) == 1)
mail.outbox.clear()
r = c.post("/api/auth/resend-verification", json={"email": "neu@example.com"})
check("unbestaetigt -> Mail, Antwort 200", r.status_code == 200 and len(mail.outbox) == 1)
c.post("/api/auth/verify-email", json={"token": token_from_mail()})
check("Login nach Resend-Bestaetigung",
      c.post("/api/auth/login", json={"login": "neu", "password": "geheim123"}).status_code == 200)

print("Token an Adresse gebunden")
mail.outbox.clear()
c.post("/api/auth/register", json={"username": "w", "email": "w@example.com", "password": "geheim123"})
tw = token_from_mail()
with app.app_context():
    u = User.query.filter_by(username="w").first()
    u.email = "geaendert@example.com"
    db.session.commit()
check("Token nach Adressaenderung ungueltig", c.post("/api/auth/verify-email", json={"token": tw}).status_code == 400)

print("Passwort-Reset bestaetigt Adresse")
mail.outbox.clear()
c.post("/api/auth/register", json={"username": "x", "email": "x@example.com", "password": "geheim123"})
mail.outbox.clear()
c.post("/api/auth/password-reset/request", json={"email": "x@example.com"})
r = c.post("/api/auth/password-reset/confirm", json={"token": token_from_mail(), "password": "neues-passwort"})
check("Reset -> 200", r.status_code == 200)
check("danach Login moeglich",
      c.post("/api/auth/login", json={"login": "x", "password": "neues-passwort"}).status_code == 200)

print("Admin-angelegte Nutzer sind bestaetigt")
app.config["ADMIN_GUARD_ENABLED"] = True
r = c.post("/api/admin/users", json={"username": "byadmin", "email": "ba@t.local", "password": "secret123"},
           headers={"X-User-Id": str(admin_id)})
check("Admin legt Nutzer an", r.status_code == 201 and r.json["email_verified"] is True, r.get_data(as_text=True))
check("Login ohne Verifizierung moeglich",
      c.post("/api/auth/login", json={"login": "byadmin", "password": "secret123"}).status_code == 200)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
