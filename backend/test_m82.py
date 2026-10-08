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

# ── Endpoint-Auto-Vergabe (Punkt 3) ─────────────────────
print("Endpoint auto_assign (Punkt 3)")
import sqlite3
from app.domain.agents.models import Agent
from app.domain.agents import placement
from app.domain.agents.monitoring_service import _get_endpoint_summary
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance

with app.app_context():
    own = User(username="own", email="own@t.local")
    own.set_password("test1234")
    bp = Blueprint(name="vrising", docker_image="img", startup_command="run")
    ag1 = Agent(name="n1", fqdn="n1.t.local", memory_total=8192, disk_total=100000, cpu_total=800)
    ag2 = Agent(name="n2", fqdn="n2.t.local", memory_total=8192, disk_total=100000, cpu_total=800)
    db.session.add_all([own, bp, ag1, ag2])
    db.session.commit()
    OWN, BP, N1, N2 = own.id, bp.id, ag1.id, ag2.id
OH = {"X-User-Id": str(OWN)}


def mk(agent, port, **extra):
    r = c.post(f"/api/admin/agents/{agent}/endpoints", json={"ip": "0.0.0.0", "port": port, **extra}, headers=AH)
    return r


r = mk(N1, 9876)
check("neuer Endpoint: auto_assign standardmaessig true", r.status_code == 201 and r.json["auto_assign"] is True, str(r.json))
E_GAME = r.json["id"]
r = mk(N1, 9877, auto_assign=False)
check("POST /agents/<id>/endpoints mit auto_assign=false", r.status_code == 201 and r.json["auto_assign"] is False, str(r.json))
E_QUERY = r.json["id"]
E_THIRD = mk(N1, 9878).json["id"]
check("auto_assign kein Boolean -> 400", mk(N1, 9879, auto_assign="nein").status_code == 400 and mk(N1, 9879, auto_assign=0).status_code == 400)
r = c.post(f"/api/admin/agents/{N1}/endpoints/bulk", json={"ip": "0.0.0.0", "port_start": 9890, "port_end": 9892}, headers=AH)
check("bulk: Standard auto_assign true", r.status_code == 201 and all(e["auto_assign"] is True for e in r.json["endpoints"]))
r = c.post(f"/api/admin/agents/{N1}/endpoints/bulk", json={"ip": "0.0.0.0", "port_start": 9900, "port_end": 9901, "auto_assign": False}, headers=AH)
check("bulk mit auto_assign=false", r.status_code == 201 and r.json["created"] == 2 and all(e["auto_assign"] is False for e in r.json["endpoints"]), str(r.json))
check("bulk: auto_assign kein Boolean -> 400", c.post(f"/api/admin/agents/{N1}/endpoints/bulk", json={"port_start": 9910, "port_end": 9911, "auto_assign": "x"}, headers=AH).status_code == 400)
lst = c.get("/api/admin/endpoints", headers=AH).json
check("GET /api/admin/endpoints liefert auto_assign", all(isinstance(e["auto_assign"], bool) for e in lst) and any(e["id"] == E_QUERY and e["auto_assign"] is False for e in lst))

print("PATCH /api/admin/endpoints/<id>")
R = c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": False}, headers=AH)
check("auto_assign=false -> 200 mit Endpoint-Dict", R.status_code == 200 and R.json["id"] == E_THIRD and R.json["auto_assign"] is False and R.json["is_locked"] is False, str(R.json))
R = c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": True, "is_locked": True}, headers=AH)
check("beide Flags zusammen", R.status_code == 200 and R.json["auto_assign"] is True and R.json["is_locked"] is True)
R = c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"is_locked": False}, headers=AH)
check("nur is_locked: auto_assign bleibt", R.status_code == 200 and R.json["is_locked"] is False and R.json["auto_assign"] is True)
check("unbekannter Endpoint -> 404", c.patch("/api/admin/endpoints/99999", json={"auto_assign": False}, headers=AH).status_code == 404)
check("leerer Body / ohne Felder -> 400", c.patch(f"/api/admin/endpoints/{E_THIRD}", json={}, headers=AH).status_code == 400 and c.patch(f"/api/admin/endpoints/{E_THIRD}", headers=AH).status_code == 400
      and c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"port": 1}, headers=AH).status_code == 400)
check("kein Boolean -> 400 (nichts geaendert)", c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": "false"}, headers=AH).status_code == 400
      and c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": False, "is_locked": 1}, headers=AH).status_code == 400
      and c.get("/api/admin/endpoints", headers=AH).json[[e["id"] for e in c.get("/api/admin/endpoints", headers=AH).json].index(E_THIRD)]["auto_assign"] is True)

print("automatische Vergabe uebergeht auto_assign=false")
for e in [E_THIRD]:
    pass
# Agent 1: 9876 (auto), 9877 (nur manuell), 9878 (auto), 9890-9892 (auto), 9900-9901 (nur manuell). Erst die 9890er sperren, damit der Fall klar bleibt.
for ep in c.get("/api/admin/endpoints", headers=AH).json:
    if 9890 <= ep["port"] <= 9892:
        c.patch(f"/api/admin/endpoints/{ep['id']}", json={"is_locked": True}, headers=AH)


def create(name, **extra):
    return c.post("/api/admin/instances", json={"name": name, "owner_id": OWN, "blueprint_id": BP, "memory": 512, "disk": 1000, "cpu": 50, **extra}, headers=AH)


a = create("a", agent_id=N1)
b = create("b", agent_id=N1)
check("erste Instanz bekommt 9876", a.status_code == 201 and a.json["connection"]["port"] == 9876, str(a.json.get("connection")))
check("zweite Instanz bekommt 9878 (9877 ist nur manuell)", b.status_code == 201 and b.json["connection"]["port"] == 9878, str(b.json.get("connection")))
cc = create("c", agent_id=N1)
check("dritte Instanz: nur noch manuelle/gesperrte Endpoints -> 409", cc.status_code == 409, cc.get_data(as_text=True))
with app.app_context():
    check("placement.has_free_endpoint: false, wenn nur manuelle uebrig sind", placement.has_free_endpoint(N1) is False)
    summ = _get_endpoint_summary(db.session.get(Agent, N1))
check("Endpoint-Zusammenfassung des Monitorings: manual gezaehlt, free ohne manuelle", summ["manual"] == 3 and summ["free"] == 0, str(summ))

print("explizite Zuweisung bleibt moeglich")
d = create("d", agent_id=N1, endpoint_id=E_QUERY)
check("endpoint_id bei der Anlage: auch mit auto_assign=false", d.status_code == 201 and d.json["primary_endpoint_id"] == E_QUERY and d.json["connection"]["port"] == 9877, d.get_data(as_text=True)[:200])
manual2 = next(e["id"] for e in c.get("/api/admin/endpoints", headers=AH).json if e["port"] == 9900)
r = c.post(f"/api/admin/instances/{a.json['uuid']}/endpoints", json={"endpoint_id": manual2}, headers=AH)
check("POST .../endpoints (M80) weist einen auto_assign=false-Endpoint zu", r.status_code == 201 and any(e["port"] == 9900 for e in r.json["endpoints"]), r.get_data(as_text=True)[:200])
locked_manual = next(e["id"] for e in c.get("/api/admin/endpoints", headers=AH).json if e["port"] == 9901)
c.patch(f"/api/admin/endpoints/{locked_manual}", json={"is_locked": True}, headers=AH)
r = c.post(f"/api/admin/instances/{a.json['uuid']}/endpoints", json={"endpoint_id": locked_manual}, headers=AH)
check("gesperrt bleibt gesperrt (409), auch bei explizitem Zuweisen", r.status_code == 409)
check("gesperrter Endpoint bei der Anlage -> 400", create("e", agent_id=N1, endpoint_id=locked_manual).status_code == 400)

print("Platzierung und Transfer beachten auto_assign")
mk(N2, 9876, auto_assign=False)
r = create("auto-placement")
check("Anlage ohne agent_id: Agent 2 hat nur einen manuellen Endpoint -> keine Platzierung (409/400)", r.status_code in (400, 409), f"{r.status_code} {r.get_data(as_text=True)[:200]}")
mk(N2, 9877)
r = create("auto-placement-2")
check("... sobald Agent 2 einen automatisch vergebbaren Endpoint hat, wird platziert", r.status_code == 201 and r.json["agent_id"] == N2 and r.json["connection"]["port"] == 9877, f"{r.status_code} {r.get_data(as_text=True)[:200]}")
tr = c.post(f"/api/admin/instances/{b.json['uuid']}/transfer", json={"target_agent_id": N2}, headers=AH)
check("Transfer zu Agent 2: ohne freien automatischen Endpoint abgelehnt", tr.status_code in (400, 409), f"{tr.status_code} {tr.get_data(as_text=True)[:200]}")

print("Rechte")
app.config["ADMIN_GUARD_ENABLED"] = True
check("PATCH ohne Anmeldung -> 401", c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": False}).status_code == 401)
check("PATCH als Kunde -> 403", c.patch(f"/api/admin/endpoints/{E_THIRD}", json={"auto_assign": False}, headers=OH).status_code == 403)
app.config["ADMIN_GUARD_ENABLED"] = False

print("Migration auto_assign")
cwd = os.path.dirname(__file__)
with tempfile.TemporaryDirectory() as tmp:
    dbp = f"{tmp}/t.db"
    menv = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{dbp}", "RUNNER_ADAPTER": "stub", "FLASK_APP": "app:create_app"}
    mrun = lambda *a_: subprocess.run([sys.executable, "-m", "flask", "db", *a_], env=menv, capture_output=True, text=True, cwd=cwd)
    # Zustand vor M82: bis M70 migrieren, einen Endpoint anlegen, dann hochziehen
    up0 = mrun("upgrade", "y5t6u7v8w9x0")
    con = sqlite3.connect(dbp)
    con.execute("insert into agents (id, uuid, name, fqdn) values (1, 'u-1', 'n1', 'n1.t.local')")
    con.execute("insert into endpoints (agent_id, ip, port) values (1, '0.0.0.0', 25565)")
    con.commit()
    con.close()
    up = mrun("upgrade")
    cols = lambda: {r_[1]: r_ for r_ in sqlite3.connect(dbp).execute("pragma table_info(endpoints)")}
    col = cols().get("auto_assign")
    old_row = sqlite3.connect(dbp).execute("select auto_assign from endpoints where port = 25565").fetchone()
    down = mrun("downgrade", "y5t6u7v8w9x0")
    gone = "auto_assign" not in cols()
    up2 = mrun("upgrade")
    heads = mrun("heads")
check("Upgrade: Spalte NOT NULL mit Standard true, bestehende Endpoints bekommen true", up0.returncode == 0 and up.returncode == 0 and col is not None and col[3] == 1 and old_row == (1,), f"{up0.stderr[-200:]} {up.stderr[-200:]} {col} {old_row}")
check("Downgrade entfernt die Spalte, erneutes Upgrade und genau ein Head", down.returncode == 0 and gone and up2.returncode == 0 and heads.stdout.count("(head)") == 1, down.stderr[-300:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
