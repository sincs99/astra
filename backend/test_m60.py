"""M60 – MFA-Recovery-Codes: Hashes, Einmalnutzung, Neu-Erzeugen, Login, Migration."""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure import mail
from app.domain.users.models import User
from app.domain.activity.models import ActivityLog
import pyotp

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
    u = User(username="kunde", email="kunde@example.com")
    u.set_password("passwort-1234")
    db.session.add(u)
    db.session.commit()
    uid = u.id
c = app.test_client()
PW = "passwort-1234"
H = {"X-User-Id": str(uid)}


def codes_in_db():
    with app.app_context():
        return list(db.session.get(User, uid).mfa_recovery_codes or [])


def totp_now():
    with app.app_context():
        return pyotp.TOTP(db.session.get(User, uid).mfa_secret).now()


def login(code=None, field="mfa_code"):
    body = {"login": "kunde", "password": PW}
    if code is not None:
        body[field] = code
    return c.post("/api/auth/login", json=body)


def events(name):
    with app.app_context():
        return ActivityLog.query.filter_by(event=name).count()


print("Aktivieren")
check("ohne MFA: Rest 0", c.get("/api/auth/me", headers=H).json["mfa_recovery_codes_remaining"] == 0)
c.post("/api/auth/mfa/setup", headers=H)
r = c.post("/api/auth/mfa/verify", json={"code": totp_now()}, headers=H)
codes = r.json["recovery_codes"]
check("10 Codes im Format xxxxx-xxxxx, Rest 10", r.status_code == 200 and len(codes) == 10 and len(set(codes)) == 10
      and all(len(x) == 11 and x[5] == "-" for x in codes) and r.json["recovery_codes_remaining"] == 10, str(r.json))
stored = codes_in_db()
check("gespeichert werden nur Hashes (kein Klartext)", len(stored) == 10 and all(x.startswith(("scrypt:", "pbkdf2:")) for x in stored)
      and not any(code in str(stored) or code.replace("-", "") in str(stored) for code in codes))
check("Konto-Endpunkt: Rest 10, keine Codes/Hashes in der Antwort", c.get("/api/auth/me", headers=H).json["mfa_recovery_codes_remaining"] == 10
      and "recovery_codes" not in c.get("/api/auth/me", headers=H).json and "mfa_recovery_codes" not in c.get("/api/auth/me", headers=H).json)

print("Login mit TOTP und Recovery-Code")
r = login()
check("ohne Code: requires_mfa", r.json.get("requires_mfa") is True)
r = login(totp_now())
check("TOTP: Login ok, keine Recovery-Felder", r.status_code == 200 and "recovery_code_used" not in r.json and r.json["user"]["mfa_recovery_codes_remaining"] == 10)
mail.outbox.clear()
r = login(codes[0])
check("Recovery-Code: Login ok mit recovery_code_used und Rest 9", r.status_code == 200 and r.json["recovery_code_used"] is True
      and r.json["recovery_codes_remaining"] == 9 and r.json["user"]["mfa_recovery_codes_remaining"] == 9, str(r.json))
check("Event auth:mfa_recovery_used und Warnmail", events("auth:mfa_recovery_used") == 1
      and len([m for m in mail.outbox if m["to"] == "kunde@example.com" and "Recovery-Code verwendet" in m["subject"]]) == 1
      and "noch 9 Codes" in mail.outbox[-1]["body"])
check("derselbe Code ein zweites Mal: 401", login(codes[0]).status_code == 401)
check("anderer Code ueber Feld recovery_code, GROSS und ohne Strich: ok", login(codes[1].replace("-", "").upper(), field="recovery_code").status_code == 200)
check("falscher Code: 401", login("abcde-fghjk").status_code == 401)
check("6 Ziffern sind nie ein Recovery-Code (falscher TOTP): 401", login("000000").status_code == 401)
check("Rest 8", c.get("/api/auth/me", headers=H).json["mfa_recovery_codes_remaining"] == 8)
check("Fehlversuche zaehlen nicht", login("abcde-fghjk").status_code == 401 and codes_in_db().__len__() == 8)

print("Neu erzeugen")
r = c.post("/api/auth/mfa/recovery-codes", json={"password": PW})
check("ohne Anmeldung: 401", r.status_code == 401)
r = c.post("/api/auth/mfa/recovery-codes", json={"password": "falsch"}, headers=H)
check("falsches Passwort: 403 invalid_password, Codes unveraendert", r.status_code == 403 and r.json["code"] == "invalid_password" and len(codes_in_db()) == 8)
r = c.post("/api/auth/mfa/recovery-codes", json={}, headers=H)
check("ohne Passwort: 403", r.status_code == 403)
r = c.post("/api/auth/mfa/recovery-codes", json={"password": PW}, headers=H)
new = r.json["recovery_codes"]
check("richtiges Passwort: 10 neue Codes, Rest 10", r.status_code == 200 and len(new) == 10 and r.json["recovery_codes_remaining"] == 10
      and not set(new) & set(codes), str(r.json))
check("alte Codes ungueltig", login(codes[2]).status_code == 401)
check("neuer Code gilt", login(new[0]).status_code == 200)
check("Event auth:mfa_recovery_codes_regenerated", events("auth:mfa_recovery_codes_regenerated") == 1)

print("Altbestand (Klartext vor M60)")
with app.app_context():
    usr = db.session.get(User, uid)
    usr.mfa_recovery_codes = ["a1b2c3d4", "e5f6a7b8"]
    db.session.commit()
check("Klartext-Code wird akzeptiert und verbraucht", login("a1b2c3d4").status_code == 200 and codes_in_db() == ["e5f6a7b8"])
check("... nur einmal", login("a1b2c3d4").status_code == 401)

print("Datenmigration hasht Klartext-Codes")
spec = importlib.util.spec_from_file_location(
    "m60", os.path.join(os.path.dirname(__file__), "migrations", "versions", "t0o1p2q3r4s5_milestone60_recovery_code_hashes.py"))
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)
from alembic.migration import MigrationContext
from alembic.operations import Operations
with app.app_context():
    other = User(username="zwei", email="zwei@example.com", mfa_enabled=True, mfa_recovery_codes=["12345678", "abcdefgh"])
    nomfa = User(username="drei", email="drei@example.com")
    other.set_password("x-passwort-1"); nomfa.set_password("x-passwort-2")
    db.session.add_all([other, nomfa])
    db.session.commit()
    with db.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mig.upgrade()
    with db.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mig.upgrade()  # idempotent
    db.session.expire_all()
    stored = list(db.session.get(User, other.id).mfa_recovery_codes)
    mine = list(db.session.get(User, uid).mfa_recovery_codes)
    drei = db.session.get(User, nomfa.id).mfa_recovery_codes
check("alle Eintraege gehasht, Anzahl gleich", len(stored) == 2 and all(x.startswith(("scrypt:", "pbkdf2:")) for x in stored), str(stored))
check("bereits gehashte und Nutzer ohne Codes bleiben unveraendert", mine == codes_in_db() and drei is None)
from app.domain.auth.mfa_service import consume_recovery_code
with app.app_context():
    zwei = db.session.get(User, other.id)
    ok_first = consume_recovery_code(zwei, "1234-5678")  # Normalisierung: Striche egal
    ok_second = consume_recovery_code(zwei, "12345678")
check("migrierter Code gilt weiter (einmalig)", ok_first and not ok_second)

print("Deaktivieren")
r = c.post("/api/auth/mfa/disable", headers=H)
check("MFA aus: Codes weg, Rest 0", r.status_code == 200 and codes_in_db() == [] and c.get("/api/auth/me", headers=H).json["mfa_recovery_codes_remaining"] == 0)
r = c.post("/api/auth/mfa/recovery-codes", json={"password": PW}, headers=H)
check("Neu erzeugen ohne MFA: 409", r.status_code == 409)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
