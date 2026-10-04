"""M67 – Sprache des Kunden fuer Servertexte: users.locale, Mails und Belege in DE/EN."""

import os
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
check("einziger Head w3r4s5t6u7v8", heads.stdout.strip().endswith("w3r4s5t6u7v8 (head)") and heads.stdout.count("(head)") == 1, heads.stdout[-100:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
