"""M82 – Zweite Pilot-Liste: Install-Image Debian 12, Paper-Kanal (BUILD_CHANNEL), Endpoint-Auto-Vergabe."""

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

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


ROOT = os.path.join(os.path.dirname(__file__), "..")
EGG = json.load(open(os.path.join(ROOT, "blueprints", "minecraft-paper.json"), encoding="utf-8"))
NEW_IMG = "ghcr.io/parkervcp/installers:debian"
OLD_IMG = "ghcr.io/pterodactyl/installers:debian"

from app import create_app
from app.extensions import db
from app.domain.blueprints.models import DEFAULT_INSTALL_CONTAINER, Blueprint
from app.domain.users.models import User
from app.infrastructure.runner import config_builder

app = create_app("testing")
with app.app_context():
    db.create_all()
    adm = User(username="adm", email="adm@t.local", is_admin=True)
    adm.set_password("test1234")
    db.session.add(adm)
    db.session.commit()
    AID = adm.id
c = app.test_client()
AH = {"X-User-Id": str(AID)}

print("Install-Image (Punkt 1)")
check("Paper-Blueprint nutzt parkervcp/installers:debian (Debian 12)", EGG["scripts"]["installation"]["container"] == NEW_IMG)
check("Standard-Install-Container im Modell", DEFAULT_INSTALL_CONTAINER == NEW_IMG)
src = open(os.path.join(os.path.dirname(config_builder.__file__), "config_builder.py"), encoding="utf-8").read()
check("Fallback im Config-Builder", NEW_IMG in src and OLD_IMG not in src)
for rel in ("docs/deploy-runbook.md", "docs/wings-remote-api.md"):
    txt = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    check(f"{rel}: neues Install-Image; das alte nur als Hinweis (Debian 11)", NEW_IMG in txt and all("Debian 11" in ln for ln in txt.splitlines() if OLD_IMG in ln))
with app.app_context():
    old_bp = Blueprint(name="alt", docker_image="img", startup_command="run", install_container=OLD_IMG)
    keep_bp = Blueprint(name="eigenes", docker_image="img", startup_command="run", install_container="ghcr.io/pterodactyl/installers:alpine")
    none_bp = Blueprint(name="leer", docker_image="img", startup_command="run")
    db.session.add_all([old_bp, keep_bp, none_bp])
    db.session.commit()
    OLD_ID, KEEP_ID, NONE_ID = old_bp.id, keep_bp.id, none_bp.id
    check("Blueprint ohne gespeichertes Image bekommt den neuen Standard", db.session.get(Blueprint, NONE_ID).get_install_container() == NEW_IMG)
    check("gespeicherter alter Wert bleibt (kein stilles Umschreiben)", db.session.get(Blueprint, OLD_ID).get_install_container() == OLD_IMG)
r = c.patch(f"/api/admin/blueprints/{OLD_ID}", json={"install_container": NEW_IMG}, headers=AH)
check("PATCH /api/admin/blueprints/<id> kann install_container umstellen", r.status_code == 200 and r.json["install_container"] == NEW_IMG, str(r.get_data(as_text=True))[:200])
r = c.patch(f"/api/admin/blueprints/{OLD_ID}", json={"install_container": OLD_IMG}, headers=AH)
check("... und zurueckstellen (fuer den CLI-Test)", r.status_code == 200 and r.json["install_container"] == OLD_IMG)

# CLI gegen eine Datei-Datenbank
with tempfile.TemporaryDirectory() as td:
    dburl = f"sqlite:///{td}/m82.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": dburl, "SECRET_KEY": "x" * 40, "AUTO_MIGRATE": "false"}
    setup = ("from app import create_app\nfrom app.extensions import db\nfrom app.domain.blueprints.models import Blueprint\n"
             "app = create_app()\nwith app.app_context():\n    db.create_all()\n"
             f"    db.session.add_all([Blueprint(name='a1', docker_image='i', startup_command='r', install_container='{OLD_IMG}'),"
             f" Blueprint(name='a2', docker_image='i', startup_command='r', install_container='{OLD_IMG}'),"
             " Blueprint(name='b', docker_image='i', startup_command='r', install_container='ghcr.io/pterodactyl/installers:alpine'),"
             " Blueprint(name='c', docker_image='i', startup_command='r')])\n    db.session.commit()\n")
    subprocess.run([sys.executable, "-c", setup], env=env, cwd=os.path.dirname(__file__), check=True, capture_output=True)

    def cli(*args):
        r = subprocess.run([sys.executable, "cli.py", "update-install-container", *args], env=env, cwd=os.path.dirname(__file__), capture_output=True, text=True)
        return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", r.stderr

    def stored():
        chk = ("import json\nfrom app import create_app\nfrom app.domain.blueprints.models import Blueprint\napp = create_app()\n"
               "with app.app_context():\n    print(json.dumps({b.name: b.install_container for b in Blueprint.query.all()}))\n")
        out = subprocess.run([sys.executable, "-c", chk], env=env, cwd=os.path.dirname(__file__), capture_output=True, text=True).stdout.strip().splitlines()[-1]
        return json.loads(out)

    rc, out, err = cli("--dry-run")
    res = json.loads(out)
    check("--dry-run: zeigt die betroffenen Blueprints, aendert nichts", rc == 0 and sorted(res["blueprints"]) == ["a1", "a2"] and res["updated"] == 0 and res["dry_run"] is True
          and stored()["a1"] == OLD_IMG, f"{rc} {out} {err[-200:]}")
    rc, out, err = cli()
    res = json.loads(out)
    st = stored()
    check("stellt genau die Blueprints mit dem alten Standard um", rc == 0 and res["updated"] == 2 and st["a1"] == NEW_IMG and st["a2"] == NEW_IMG, f"{rc} {out} {err[-200:]}")
    check("eigene Images (alpine) und leere Werte bleiben unveraendert", st["b"] == "ghcr.io/pterodactyl/installers:alpine" and st["c"] is None, str(st))
    rc, out, err = cli()
    check("zweiter Lauf: idempotent, nichts mehr zu tun", rc == 0 and json.loads(out)["updated"] == 0)
    rc, out, err = cli("--from", "ghcr.io/pterodactyl/installers:alpine", "--to", "ghcr.io/parkervcp/installers:alpine")
    check("--from/--to fuer andere Images", rc == 0 and json.loads(out)["blueprints"] == ["b"] and stored()["b"] == "ghcr.io/parkervcp/installers:alpine")
    rc, out, err = cli("--from", NEW_IMG, "--to", NEW_IMG)
    check("gleiche Werte -> Fehler (Exit 2)", rc == 2)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
