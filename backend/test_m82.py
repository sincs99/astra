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

# ── Paper: BUILD_CHANNEL (Punkt 2) ──────────────────────
print("Paper-Kanal BUILD_CHANNEL (Punkt 2)")
import hashlib
import zipfile

SCRIPT = EGG["scripts"]["installation"]["script"]
FAKE_CURL = r'''#!/bin/bash
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -A|--retry|--retry-delay|--connect-timeout|--max-time) shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
echo "$url" >> "$FAKE_DIR/_requests"
f="$FAKE_DIR/$(printf '%s' "$url" | tr -c 'A-Za-z0-9' '_')"
if [ ! -f "$f" ]; then echo "curl: (22) The requested URL returned error: 404" >&2; exit 22; fi
if [ -n "$out" ]; then cat "$f" > "$out"; else cat "$f"; fi
'''
API = "https://fill.papermc.io/v3/projects/paper"
PROPS = "https://raw.githubusercontent.com/parkervcp/eggs/master/minecraft/java/server.properties"


def key(url):
    return re.sub(r"[^A-Za-z0-9]", "_", url)


def jar_bytes(tag):
    with tempfile.TemporaryDirectory() as t:
        pth = os.path.join(t, "x.jar")
        with zipfile.ZipFile(pth, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", f"Manifest-Version: 1.0\nTag: {tag}\n")
        return open(pth, "rb").read()


class Fill:
    """Simulierte Fill-API: Versionen mit Builds (id, channel); Downloads sind je Build ein eigenes Jar."""

    def __init__(self, versions: dict, groups=None, wrap=False):
        self.routes = {}
        self.jars = {}
        self.wrap = wrap
        grouped = groups or {"26": [v for v in versions if v.startswith("26")], "1.21": [v for v in versions if v.startswith("1.")]}
        self.routes[API] = json.dumps({"project": {"id": "paper"}, "versions": grouped})
        for ver, builds in versions.items():
            items = []
            for bid, channel in builds:
                jar = jar_bytes(f"{ver}-{bid}")
                url = f"https://fill-data.papermc.io/v1/objects/{ver}-{bid}.jar"
                self.jars[(ver, bid)] = jar
                self.routes[url] = jar
                item = {"id": bid, "channel": channel, "downloads": {"server:default": {"name": f"paper-{ver}-{bid}.jar", "url": url, "checksums": {"sha256": hashlib.sha256(jar).hexdigest()}}}}
                items.append(item)
                self.routes[f"{API}/versions/{ver}/builds/{bid}"] = json.dumps(item)
            self.routes[f"{API}/versions/{ver}/builds"] = json.dumps({"builds": items} if wrap else items)
        self.routes[PROPS] = "server-port=25565\n"


def run(fill, env=None):
    with tempfile.TemporaryDirectory() as tmp:
        fake, bindir, server = (os.path.join(tmp, n) for n in ("fake", "bin", "server"))
        for d in (fake, bindir, server):
            os.makedirs(d)
        for url, body in fill.routes.items():
            open(os.path.join(fake, key(url)), "wb").write(body if isinstance(body, bytes) else body.encode())
        open(os.path.join(bindir, "curl"), "w").write(FAKE_CURL)
        open(os.path.join(bindir, "apt-get"), "w").write("#!/bin/bash\nexit 0\n")
        for n in ("curl", "apt-get"):
            os.chmod(os.path.join(bindir, n), 0o755)
        e = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"], "FAKE_DIR": fake}
        for k in ("MINECRAFT_VERSION", "BUILD_NUMBER", "BUILD_CHANNEL", "DL_PATH", "SERVER_JARFILE"):
            e.pop(k, None)
        e.update(env or {})
        r = subprocess.run(["bash", "-c", SCRIPT.replace("/mnt/server", server)], env=e, capture_output=True, text=True, timeout=60, cwd=tmp)
        jar = open(os.path.join(server, "server.jar"), "rb").read() if os.path.exists(os.path.join(server, "server.jar")) else None
        reqs = open(os.path.join(fake, "_requests")).read().split() if os.path.exists(os.path.join(fake, "_requests")) else []
        return r.returncode, r.stdout + r.stderr, jar, reqs


PILOT = {"26.3": [(159, "BETA")], "26.2": [(118, "BETA"), (120, "STABLE")], "26.1.1": [(7, "STABLE")], "1.21.8": [(100, "STABLE")]}
f = Fill(PILOT)
rc, out, jar, reqs = run(f)
check("Pilot-Fall: 26.3 nur BETA -> Standard STABLE faellt auf 26.2 Build 120 zurueck", rc == 0 and jar == f.jars[("26.2", 120)], out[-500:])
check("Log: Version, Build und Kanal; Hinweis auf die uebersprungene Version", "MC Version: 26.2" in out and "Build: 120 (channel STABLE)" in out and "Version 26.3 has no STABLE build yet" in out, out[-500:])
rc, out, jar, reqs = run(f, {"BUILD_CHANNEL": "BETA"})
check("BUILD_CHANNEL=BETA nimmt 26.3 Build 159", rc == 0 and jar == f.jars[("26.3", 159)] and "Build: 159 (channel BETA)" in out, out[-500:])
rc, out, jar, reqs = run(f, {"BUILD_CHANNEL": "beta"})
check("Kleinschreibung und Leerzeichen werden toleriert", rc == 0 and jar == f.jars[("26.3", 159)])
f2 = Fill({"26.3": [(159, "BETA"), (160, "ALPHA")], "26.2": [(120, "STABLE")]})
rc, out, jar, reqs = run(f2, {"BUILD_CHANNEL": "ALPHA"})
check("BUILD_CHANNEL=ALPHA nimmt den neuesten Build (160) der neuesten Version", rc == 0 and jar == f2.jars[("26.3", 160)], out[-300:])
rc, out, jar, reqs = run(f2, {"BUILD_CHANNEL": "BETA"})
check("BUILD_CHANNEL=BETA ignoriert ALPHA-Builds (159)", rc == 0 and jar == f2.jars[("26.3", 159)], out[-300:])
rc, out, jar, reqs = run(f2)
check("Standard ohne Variable (bestehende Instanzen) = STABLE", rc == 0 and jar == f2.jars[("26.2", 120)], out[-300:])
f3 = Fill({"26.2": [(120, "STABLE"), (125, "BETA")]})
rc, out, jar, reqs = run(f3)
check("STABLE: neuester STABLE-Build (120), nicht der neuere BETA (125)", rc == 0 and jar == f3.jars[("26.2", 120)])
rc, out, jar, reqs = run(f3, {"BUILD_CHANNEL": "BETA"})
check("BETA: der neueste Build gewinnt (125)", rc == 0 and jar == f3.jars[("26.2", 125)])
f4 = Fill({"26.2": [(120, "RECOMMENDED"), (121, "BETA")]})
rc, out, jar, reqs = run(f4)
check("RECOMMENDED zaehlt als stabil", rc == 0 and jar == f4.jars[("26.2", 120)])
f5 = Fill({"26.2": [(1, "ALPHA")], "26.1": [(2, "ALPHA")]})
rc, out, jar, reqs = run(f5)
check("kein STABLE-Build in keiner Version: Exit != 0, kein server.jar", rc != 0 and jar is None and "No paper version with a STABLE" in out, out[-300:])
rc, out, jar, reqs = run(f, {"BUILD_CHANNEL": "NIGHTLY"})
check("ungueltiger Kanal: Exit != 0 vor jedem Download", rc != 0 and "BUILD_CHANNEL must be" in out and jar is None and not any("fill-data" in u for u in reqs), out[-300:])
rc, out, jar, reqs = run(Fill(PILOT, wrap=True))
check("Build-Liste auch als {builds: [...]} lesbar", rc == 0 and jar is not None)

print("feste Build-Nummer und feste Version")
rc, out, jar, reqs = run(f, {"BUILD_NUMBER": "159"})
check("feste Nummer mit latest-Version: gilt unabhaengig vom Kanal (BETA-Build trotz STABLE)", rc == 0 and jar == f.jars[("26.3", 159)] and "Build: 159 (channel BETA)" in out and f"{API}/versions/26.3/builds/159" in reqs, out[-300:])
rc, out, jar, reqs = run(f, {"MINECRAFT_VERSION": "26.2", "BUILD_NUMBER": "118"})
check("feste Version + feste Nummer (BETA): wird genommen", rc == 0 and jar == f.jars[("26.2", 118)])
rc, out, jar, reqs = run(f, {"MINECRAFT_VERSION": "26.2"})
check("feste Version, Build latest: neuester STABLE (120)", rc == 0 and jar == f.jars[("26.2", 120)])
rc, out, jar, reqs = run(f, {"MINECRAFT_VERSION": "26.3"})
check("feste Version ohne STABLE-Build: Warnung, neuester Build irgendeines Kanals", rc == 0 and jar == f.jars[("26.3", 159)] and "WARNING" in out, out[-300:])
rc, out, jar, reqs = run(f, {"MINECRAFT_VERSION": "26.2", "BUILD_NUMBER": "999"})
check("unbekannte Nummer: Rueckfall auf den neuesten Build im Kanal", rc == 0 and jar == f.jars[("26.2", 120)] and "not found" in out)
rc, out, jar, reqs = run(f, {"BUILD_NUMBER": "abc; rm -rf /"})
check("Build-Nummer mit Muell: Hinweis, Kanal-Auswahl", rc == 0 and "is not a number" in out and jar == f.jars[("26.2", 120)], out[-300:])

print("Blueprint-Variable BUILD_CHANNEL")
var = next((v for v in EGG["variables"] if v["env_variable"] == "BUILD_CHANNEL"), None)
check("Variable vorhanden: Standard STABLE, sichtbar und editierbar", var is not None and var["default_value"] == "STABLE" and var["user_viewable"] is True and var["user_editable"] is True, str(var))
check("Regel erlaubt STABLE|BETA|ALPHA", var is not None and "in:STABLE,BETA,ALPHA" in var["rules"] and var["rules"].startswith("required|string"), str(var and var["rules"]))
r = c.post("/api/admin/blueprints/import", json=EGG, headers=AH)
check("Egg-Import uebernimmt die Variable", r.status_code == 201 and "BUILD_CHANNEL" in {v["env_var"] for v in r.json["variables"]}, r.get_data(as_text=True)[:200])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
