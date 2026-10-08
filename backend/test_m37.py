"""M37 – Egg-Import (Pterodactyl PTDL_v2 / Pelican PLCN_v3 / natives Format)."""

import copy
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.blueprints.egg_import import EggImportError, convert, convert_egg, detect_format
from app.domain.blueprints.models import Blueprint
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


def raises(fn, *a):
    try:
        fn(*a)
    except EggImportError:
        return True
    return False


EGG_PATH = os.path.join(os.path.dirname(__file__), "..", "blueprints", "minecraft-paper.json")
egg = json.load(open(EGG_PATH, encoding="utf-8"))

print("convert_egg (PTDL_v2, Beispiel-Egg)")
bp = convert_egg(egg)
check("Name", bp["name"] == "Minecraft Paper")
check("erstes docker_image (M78: Java 25 fuer Paper 26.x)", bp["docker_image"] == "ghcr.io/pterodactyl/yolks:java_25")
check("startup_command", "{{SERVER_JARFILE}}" in bp["startup_command"] and bp["startup_command"].startswith("java -Xms128M"))
check("Install-Script/Container/Entrypoint", bp["install_script"].startswith("#!/bin/bash")
      and bp["install_container"].endswith("installers:debian") and bp["install_entrypoint"] == "bash")
check("config_startup (JSON-String -> dict)", bp["config_startup"] == {"done": ")! For help, type "})
check("config_stop", bp["config_stop"] == "stop")
check("config_files (JSON-String -> dict)", bp["config_files"]["server.properties"]["parser"] == "properties")
check("Platzhalter unveraendert", bp["config_files"]["server.properties"]["find"]["server-port"] == "{{server.build.default.port}}")
v = {x["env_var"]: x for x in bp["variables"]}
check("Variablen env_variable -> env_var", set(v) == {"MINECRAFT_VERSION", "SERVER_JARFILE", "DL_PATH", "BUILD_NUMBER"})
check("Variable default_value", v["SERVER_JARFILE"]["default_value"] == "server.jar")

print("Varianten / Randfaelle")
pel = copy.deepcopy(egg)
pel["meta"]["version"] = "PLCN_v3"
pel.pop("startup")
pel["startup_commands"] = {"Default": "java -jar {{SERVER_JARFILE}}"}
pel["config"] = {"files": {"a.yml": {"parser": "yaml", "find": {"x": "1"}}}, "startup": {"done": ["Done"]}, "stop": "^C"}
pel["docker_images"] = {"A": "img:a", "B": "img:b"}
pel["variables"][0]["default_value"] = True
p = convert_egg(pel)
check("Pelican: startup_commands", p["startup_command"] == "java -jar {{SERVER_JARFILE}}")
check("Pelican: Objekt-Config", p["config_files"] == {"a.yml": {"parser": "yaml", "find": {"x": "1"}}} and p["config_startup"] == {"done": ["Done"]})
check("^C -> ^SIGINT", p["config_stop"] == "^SIGINT")
check("erstes von mehreren Images", p["docker_image"] == "img:a")
check("bool default -> 'true'", p["variables"][0]["default_value"] == "true")
legacy = {"name": "Old", "image": "old:1", "startup": "run", "variables": [], "scripts": {"installation": {"script": "x", "container": "c", "entry": "ash"}}}
lp = convert_egg(legacy)
check("Legacy image + entry", lp["docker_image"] == "old:1" and lp["install_entrypoint"] == "ash")
check("kaputtes config.files -> Fehler", raises(convert_egg, {**egg, "config": {"files": "{kaputt"}}))
check("config.files kein Objekt -> Fehler", raises(convert_egg, {**egg, "config": {"files": "[1]"}}))
check("Name fehlt -> Fehler", raises(convert_egg, {"variables": []}))
check("Variable ohne env -> Fehler", raises(convert_egg, {"name": "x", "variables": [{"name": "a"}]}))
check("Format-Erkennung egg", detect_format(egg) == "egg")
check("Unbekanntes Format -> Fehler", raises(detect_format, {"foo": 1}))
check("Nicht-Objekt -> Fehler", raises(detect_format, [1, 2]))

app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="a@t.local", is_admin=True)
    admin.set_password("test1234")
    db.session.add(admin)
    db.session.commit()
    admin_id = admin.id

c = app.test_client()
h = {"X-User-Id": str(admin_id)}

print("POST /api/admin/blueprints/import")
r = c.post("/api/admin/blueprints/import", json=egg, headers=h)
check("Egg -> 201", r.status_code == 201, r.get_data(as_text=True)[:200])
check("Antwort enthaelt Blueprint", r.json.get("name") == "Minecraft Paper" and r.json["config_stop"] == "stop")
native = {**r.json, "format": "astra", "name": "Native Copy"}
r2 = c.post("/api/admin/blueprints/import", json=native, headers=h)
check("natives Format -> 201", r2.status_code == 201 and r2.json["name"] == "Native Copy")
check("natives Format: id nicht uebernommen", r2.json["id"] != r.json["id"])
r = c.post("/api/admin/blueprints/import", json={"foo": 1}, headers=h)
check("unbekanntes Format -> 400", r.status_code == 400)
r = c.post("/api/admin/blueprints/import", data="kein json", content_type="application/json", headers=h)
check("ungueltiges JSON -> 400", r.status_code == 400)
r = c.post("/api/admin/blueprints/import", json={**egg, "config": {"startup": "{kaputt"}}, headers=h)
check("kaputte Config -> 400", r.status_code == 400)
with app.app_context():
    check("nichts Halbes gespeichert", Blueprint.query.count() == 2, str(Blueprint.query.count()))

print("Admin-Guard greift auf Import")
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Login -> 401", c.post("/api/admin/blueprints/import", json=egg).status_code == 401)
app.config["ADMIN_GUARD_ENABLED"] = False

print("Config-Builder verarbeitet importiertes Egg")
from app.infrastructure.runner.config_builder import _build_config_files
files = _build_config_files(bp["config_files"], {"server": {"build": {"default": {"port": 25570}}}})
check("config_builder liefert server.properties", isinstance(files, list) and files and files[0].get("file") == "server.properties", str(files)[:200])

print("CLI import-blueprint")
cli = os.path.join(os.path.dirname(__file__), "cli.py")
env = {**os.environ, "APP_ENV": "testing", "DATABASE_URL": "sqlite:///:memory:"}
out = subprocess.run([sys.executable, cli, "import-blueprint", EGG_PATH], capture_output=True, text=True, env=env)
check("CLI Erfolg", out.returncode == 0 and "Minecraft Paper" in out.stdout, out.stdout + out.stderr[-300:])
out = subprocess.run([sys.executable, cli, "import-blueprint", "/nicht/da.json"], capture_output=True, text=True, env=env)
check("CLI fehlende Datei -> Exit 1", out.returncode == 1)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
