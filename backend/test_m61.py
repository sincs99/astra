"""M61 – Logout-Blocklist: Token wird beim Logout bis zum Ablauf gesperrt."""

import json
import os
import subprocess
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.infrastructure import mail
from app.domain.users.models import User
from app.domain.auth.models import RevokedToken
from app.domain.auth.blocklist import cleanup_revoked_tokens, is_revoked, revoke_token
from app.domain.activity.models import ActivityLog
import jwt as pyjwt

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


def login():
    return c.post("/api/auth/login", json={"login": "kunde", "password": "passwort-1234"}).json["access_token"]


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


def me(t):
    return c.get("/api/auth/me", headers=bearer(t)).status_code


def revoked_count():
    with app.app_context():
        return RevokedToken.query.count()


print("Logout sperrt das verwendete Token")
t1, t2 = login(), login()
claims = pyjwt.decode(t1, options={"verify_signature": False})
check("Token hat jti und exp", bool(claims.get("jti")) and claims.get("exp"))
check("beide Tokens gueltig", me(t1) == 200 and me(t2) == 200)
r = c.post("/api/auth/logout", headers=bearer(t1))
check("Logout: 200 token_revoked", r.status_code == 200 and r.json["token_revoked"] is True, str(r.json))
check("gesperrtes Token: 401 auf /me", me(t1) == 401)
check("gesperrtes Token: 401 auch auf Kundenroute", c.get("/api/client/instances", headers=bearer(t1)).status_code == 401)
check("anderes Token (anderes Geraet) bleibt gueltig", me(t2) == 200)
check("Eintrag in der Blocklist", revoked_count() == 1)
with app.app_context():
    check("Activity-Event auth:logout", ActivityLog.query.filter_by(event="auth:logout").count() == 1)
    row = RevokedToken.query.first()
    check("expires_at = exp des Tokens (naive UTC), user_id gesetzt", row.jti == claims["jti"] and row.user_id == uid
          and abs((row.expires_at - datetime.utcfromtimestamp(claims["exp"])).total_seconds()) < 2)
r = c.post("/api/auth/logout", headers=bearer(t1))
check("zweiter Logout mit gesperrtem Token: 401, kein zweiter Eintrag", r.status_code == 401 and revoked_count() == 1)
check("neuer Login nach Logout funktioniert", me(login()) == 200)

print("Idempotenz und Nebenwirkungen")
with app.app_context():
    again = revoke_token(claims["jti"], datetime.utcnow() + timedelta(hours=1), uid)
check("revoke_token zweimal: kein Fehler, False", again is False and revoked_count() == 1)
with app.app_context():
    check("is_revoked: unbekannte jti, None und leer sind nie gesperrt", not is_revoked("unbekannt") and not is_revoked(None) and not is_revoked(""))
    check("is_revoked: gesperrte jti", is_revoked(claims["jti"]))

print("API-Key und Dev-Header haben nichts zu sperren")
with app.app_context():
    from app.domain.auth.apikey_service import create_api_key
    _, raw = create_api_key(uid, "account", "test")
r = c.post("/api/auth/logout", headers=bearer(raw))
check("Logout mit API-Key: 200, token_revoked=false, Key bleibt gueltig", r.status_code == 200 and r.json["token_revoked"] is False and me(raw) == 200, str(r.json))
r = c.post("/api/auth/logout", headers={"X-User-Id": str(uid)})
check("Logout mit Dev-Header: 200, token_revoked=false", r.status_code == 200 and r.json["token_revoked"] is False)
check("kein zusaetzlicher Blocklist-Eintrag", revoked_count() == 1)

print("Tokens ohne jti (aelter) bleiben bis zum Ablauf gueltig")
legacy = pyjwt.encode({"sub": str(uid), "exp": int(time.time()) + 600, "type": "access", "fresh": False, "iat": int(time.time()), "nbf": int(time.time())},
                      app.config["JWT_SECRET_KEY"], algorithm="HS256")
check("Token ohne jti wird akzeptiert", me(legacy) == 200)
r = c.post("/api/auth/logout", headers=bearer(legacy))
check("Logout damit: 200, token_revoked=false, Token weiter gueltig", r.status_code == 200 and r.json["token_revoked"] is False and me(legacy) == 200)

print("Aufraeumen abgelaufener Eintraege")
with app.app_context():
    db.session.add(RevokedToken(jti="alt-1", user_id=uid, expires_at=datetime.utcnow() - timedelta(hours=1)))
    db.session.add(RevokedToken(jti="alt-2", user_id=uid, expires_at=datetime.utcnow() - timedelta(minutes=1)))
    db.session.commit()
    dry = cleanup_revoked_tokens(dry_run=True)
check("Trockenlauf zaehlt zwei, loescht nichts", dry == {"matched": 2, "deleted": 0} and revoked_count() == 3, str(dry))
t3 = login()
c.post("/api/auth/logout", headers=bearer(t3))
check("beilaeufiges Aufraeumen beim naechsten Logout: abgelaufene weg, aktive bleiben", revoked_count() == 2)
with app.app_context():
    db.session.add(RevokedToken(jti="alt-3", user_id=uid, expires_at=datetime.utcnow() - timedelta(days=2)))
    db.session.commit()
    res = cleanup_revoked_tokens()
check("cleanup_revoked_tokens loescht nur Abgelaufene", res == {"matched": 1, "deleted": 1} and revoked_count() == 2)
with app.app_context():
    check("gesperrte, noch gueltige jti bleibt gesperrt", is_revoked(claims["jti"]))

print("CLI cleanup-jobs raeumt mit auf")
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    dbp = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{dbp}", "RUNNER_ADAPTER": "stub"}
    subprocess.run([sys.executable, "-c", "from datetime import datetime, timedelta\n"
                    "from app import create_app;from app.extensions import db\n"
                    "from app.domain.auth.models import RevokedToken\n"
                    "a=create_app()\n"
                    "with a.app_context():\n"
                    "    db.create_all()\n"
                    "    db.session.add(RevokedToken(jti='x',expires_at=datetime.utcnow()-timedelta(hours=1)))\n"
                    "    db.session.add(RevokedToken(jti='y',expires_at=datetime.utcnow()+timedelta(hours=1)))\n"
                    "    db.session.commit()"], env=env, capture_output=True, check=True, cwd=cwd)
    dry = subprocess.run([sys.executable, "cli.py", "cleanup-jobs", "--dry-run"], env=env, capture_output=True, text=True, cwd=cwd)
    left_dry = sqlite3.connect(dbp).execute("select count(*) from revoked_tokens").fetchone()[0]
    out = subprocess.run([sys.executable, "cli.py", "cleanup-jobs"], env=env, capture_output=True, text=True, cwd=cwd)
    left = sqlite3.connect(dbp).execute("select jti from revoked_tokens").fetchall()
summary = json.loads(out.stdout.splitlines()[-1]) if out.returncode == 0 else {}
check("--dry-run zaehlt, loescht nicht", dry.returncode == 0 and left_dry == 2 and json.loads(dry.stdout.splitlines()[-1])["revoked_tokens"] == {"matched": 1, "deleted": 0})
check("Lauf loescht den abgelaufenen Eintrag, der aktive bleibt", out.returncode == 0 and summary["revoked_tokens"] == {"matched": 1, "deleted": 1} and left == [("y",)], out.stdout + out.stderr[-200:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
