"""M57 – JWT wird nach Passwortwechsel/-reset ungueltig; change-password liefert ein frisches Token."""

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

with app.app_context():
    db.create_all()
    u = User(username="kunde", email="kunde@example.com")
    u.set_password("altes-passwort1")
    db.session.add(u)
    db.session.commit()
    uid = u.id

c = app.test_client()


def bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


def me(tok):
    return c.get("/api/auth/me", headers=bearer(tok)).status_code


def login(pw):
    r = c.post("/api/auth/login", json={"login": "kunde", "password": pw})
    return r.json.get("access_token") or r.json.get("token")


print("Token bleibt gueltig, solange das Passwort gleich bleibt")
t1 = login("altes-passwort1")
t2 = login("altes-passwort1")
check("zwei Logins, beide gueltig", t1 and t2 and me(t1) == 200 and me(t2) == 200)

print("Passwort aendern")
r = c.post("/api/auth/change-password", json={"current_password": "altes-passwort1", "new_password": "neues-passwort1"}, headers=bearer(t1))
check("200 mit frischem Token", r.status_code == 200 and r.json.get("access_token"), str(r.json))
fresh = r.json["access_token"]
check("altes Token (dieses Geraet) ungueltig", me(t1) == 401)
check("Token eines anderen Geraets ungueltig", me(t2) == 401)
check("frisches Token gueltig", me(fresh) == 200)
check("neuer Login funktioniert und ist gueltig", me(login("neues-passwort1")) == 200)
r = c.post("/api/auth/change-password", json={"current_password": "falsch", "new_password": "nochmal-neu1"}, headers=bearer(fresh))
check("falsches aktuelles Passwort: 401, Token bleibt gueltig", r.status_code == 401 and me(fresh) == 200)

print("Passwort zuruecksetzen")
mail.outbox.clear()
c.post("/api/auth/password-reset/request", json={"email": "kunde@example.com"})
r = c.post("/api/auth/password-reset/confirm", json={"token": token_from_mail(), "password": "reset-passwort1"})
check("Reset ok", r.status_code == 200, str(r.json))
check("Token vor dem Reset ungueltig", me(fresh) == 401)
check("Login mit neuem Passwort gueltig", me(login("reset-passwort1")) == 200)

print("Alte Tokens ohne Claim")
with app.app_context():
    from flask_jwt_extended import create_access_token
    legacy = create_access_token(identity=str(uid), additional_claims={"username": "kunde"})
check("Token ohne pwf bleibt bis zum Ablauf gueltig (Abwaertskompatibel)", me(legacy) == 200)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
