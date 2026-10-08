"""M78 – Pilot-Fehler: Paper-Blueprint (Fill v3), Wings-Installer, Netz, White-Label, Agent-Kapazitaet, Endpoint."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

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
EGG_PATH = os.path.join(ROOT, "blueprints", "minecraft-paper.json")
egg = json.load(open(EGG_PATH, encoding="utf-8"))
SCRIPT = egg["scripts"]["installation"]["script"]

print("Paper-Blueprint: statische Eigenschaften")
check("keine Referenz mehr auf api.papermc.io (stillgelegt)", "api.papermc.io" not in SCRIPT)
check("nutzt Fill v3", "https://fill.papermc.io/v3/projects/" in SCRIPT and 'downloads["server:default"]' in SCRIPT)
check("set -euo pipefail", re.search(r"^set -euo pipefail$", SCRIPT, re.M) is not None)
check("curl bricht bei HTTP-Fehlern ab (-f) und es gibt kein curl ohne -f", all("-fsSL" in ln for ln in SCRIPT.splitlines() if "curl " in ln and not ln.lstrip().startswith(("#", "apt-get"))))
check("Download wird als ZIP geprueft (PK + unzip -t)", '"PK"' in SCRIPT and "unzip -tq" in SCRIPT)
check("schreibt kein eula.txt", "eula=true" not in SCRIPT.replace("setting eula=true in eula.txt", "") and "> eula.txt" not in SCRIPT and "echo eula" not in SCRIPT)
check("kein eval (DL_PATH wird nicht ausgefuehrt)", "eval " not in SCRIPT)
check("Java 25 und Java 21 als Images, Java 25 zuerst (Standard)", list(egg["docker_images"].values())[:2] == ["ghcr.io/pterodactyl/yolks:java_25", "ghcr.io/pterodactyl/yolks:java_21"], str(egg["docker_images"]))
check("Syntax (bash -n)", subprocess.run(["bash", "-n"], input=SCRIPT, text=True, capture_output=True).returncode == 0)

# ── Script gegen eine simulierte Fill-API ausfuehren ─────
FAKE_CURL = r'''#!/bin/bash
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    --retry|--retry-delay|--connect-timeout|--max-time) shift 2 ;;
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


def key(url):
    return re.sub(r"[^A-Za-z0-9]", "_", url)


def make_jar(path, extra="a"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n" + extra)
    return open(path, "rb").read()


def run_install(routes, env=None, preexisting=None):
    """routes: URL -> bytes/str (nicht vorhanden = HTTP 404). Rueckgabe (returncode, output, serverdir, requests)."""
    with tempfile.TemporaryDirectory() as tmp:
        fake = os.path.join(tmp, "fake")
        bindir = os.path.join(tmp, "bin")
        server = os.path.join(tmp, "server")
        for d in (fake, bindir, server):
            os.makedirs(d)
        for url, body in routes.items():
            open(os.path.join(fake, key(url)), "wb").write(body if isinstance(body, bytes) else body.encode())
        open(os.path.join(bindir, "curl"), "w").write(FAKE_CURL)
        open(os.path.join(bindir, "apt-get"), "w").write("#!/bin/bash\nexit 0\n")
        for n in ("curl", "apt-get"):
            os.chmod(os.path.join(bindir, n), 0o755)
        for name, content in (preexisting or {}).items():
            open(os.path.join(server, name), "wb").write(content)
        script = SCRIPT.replace("/mnt/server", server)
        e = {**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"], "FAKE_DIR": fake}
        for k in ("MINECRAFT_VERSION", "BUILD_NUMBER", "DL_PATH", "SERVER_JARFILE"):
            e.pop(k, None)
        e.update(env or {})
        r = subprocess.run(["bash", "-c", script], env=e, capture_output=True, text=True, timeout=60, cwd=tmp)
        reqs = open(os.path.join(fake, "_requests")).read().split() if os.path.exists(os.path.join(fake, "_requests")) else []
        files = {n: open(os.path.join(server, n), "rb").read() for n in os.listdir(server) if os.path.isfile(os.path.join(server, n))}
        return r.returncode, r.stdout + r.stderr, files, reqs, tmp


with tempfile.TemporaryDirectory() as t0:
    JAR = make_jar(os.path.join(t0, "p.jar"))
SHA = hashlib.sha256(JAR).hexdigest()
DL = "https://fill-data.papermc.io/v1/objects/abc/paper-26.1.1-7.jar"
PROPS = "https://raw.githubusercontent.com/parkervcp/eggs/master/minecraft/java/server.properties"
PROJECT = json.dumps({"project": {"id": "paper"}, "versions": {
    "1.20": ["1.20.6"], "1.21": ["1.21.8", "1.21.7"], "26.1": ["26.1.1", "26.1", "26.1-pre1", "26.1-rc1"]}})


def build(vid="26.1.1", bid=7, sha=SHA, url=DL, channel="STABLE"):
    return json.dumps({"id": bid, "channel": channel, "downloads": {"server:default": {"name": f"paper-{vid}-{bid}.jar", "url": url, "checksums": {"sha256": sha}}}})


def routes(**over):
    r = {API: PROJECT, f"{API}/versions/26.1.1/builds/latest": build(), DL: JAR, PROPS: "server-port=25565\n"}
    r.update(over)
    return r


print("Paper-Install: Erfolg")
rc, out, files, reqs, _ = run_install(routes())
check("latest: Exit 0, server.jar ist das Jar", rc == 0 and files.get("server.jar") == JAR, out[-400:])
check("latest loest 26.1.1 auf (nicht 1.21.8, Vorabversionen ignoriert)", f"{API}/versions/26.1.1/builds/latest" in reqs and "Using the latest paper version 26.1.1" in out, out[-400:])
check("Checksumme geprueft", "Checksum OK" in out)
check("kein eula.txt, keine Fehlerseite, server.properties geladen", "eula.txt" not in files and files.get("server.properties") == b"server-port=25565\n", str(list(files)))
check("keine temporaere Datei bleibt liegen", not [n for n in files if n.startswith(".download")], str(list(files)))
check("Hinweis zur EULA in der Ausgabe", "Accept the Minecraft EULA" in out)
check("nur Fill-Hosts angefragt (kein api.papermc.io)", all("api.papermc.io" not in u for u in reqs), str(reqs))

print("Paper-Install: Version und Build")
r2 = routes(**{f"{API}/versions/1.21.8/builds/100": build("1.21.8", 100, url=DL), f"{API}/versions/1.21.8/builds/latest": build("1.21.8", 99)})
rc, out, files, reqs, _ = run_install(r2, {"MINECRAFT_VERSION": "1.21.8", "BUILD_NUMBER": "100"})
check("feste Version + Build 100 wird angefragt", rc == 0 and f"{API}/versions/1.21.8/builds/100" in reqs and "Version is valid" in out, out[-300:])
rc, out, files, reqs, _ = run_install(r2, {"MINECRAFT_VERSION": "1.21.8", "BUILD_NUMBER": "latest"})
check("Build latest bei fester Version", rc == 0 and f"{API}/versions/1.21.8/builds/latest" in reqs, str(reqs))
rc, out, files, reqs, _ = run_install(routes(), {"MINECRAFT_VERSION": "9.9.9"})
check("unbekannte Version: Hinweis und Rueckfall auf die neueste", rc == 0 and "not found. Defaulting to the latest" in out and files.get("server.jar") == JAR, out[-300:])
rc, out, files, reqs, _ = run_install(routes(), {"BUILD_NUMBER": "424242"})
check("unbekannter Build: Rueckfall auf die neueste", rc == 0 and "Using the latest build" in out and files.get("server.jar") == JAR, out[-300:])
rc, out, files, reqs, _ = run_install(routes(), {"BUILD_NUMBER": "abc; rm -rf /"})
check("Build-Nummer mit Muell: kein Angriff, neueste Build", rc == 0 and "is not a number" in out, out[-300:])
rc, out, files, reqs, _ = run_install(routes(), {"MINECRAFT_VERSION": "", "BUILD_NUMBER": ""})
check("leere Variablen gelten als latest", rc == 0 and files.get("server.jar") == JAR, out[-300:])
flat = routes()
flat[API] = json.dumps({"versions": ["1.21.7", "1.21.8", "1.9"]})
flat[f"{API}/versions/1.21.8/builds/latest"] = build("1.21.8", 5)
rc, out, files, reqs, _ = run_install(flat)
check("flache Versionsliste: 1.21.8 > 1.9 (Versionssortierung)", rc == 0 and f"{API}/versions/1.21.8/builds/latest" in reqs, str(reqs))

print("Paper-Install: Fehler duerfen nie still 'ready' melden")
old = {"server.jar": b"ALTES-JAR"}
rc, out, files, _, _ = run_install(routes(**{API: '{"ok":false,"error":"sunset"}'}), preexisting=old)
check("API ohne Versionsliste (Sunset-Antwort): Exit != 0, bestehendes server.jar bleibt", rc != 0 and files.get("server.jar") == b"ALTES-JAR" and "no versions" in out, f"{rc} {out[-300:]}")
rc, out, files, _, _ = run_install({PROPS: "x"})
check("API nicht erreichbar (404): Exit != 0, kein server.jar", rc != 0 and "server.jar" not in files, f"{rc} {out[-200:]}")
rc, out, files, _, _ = run_install(routes(**{DL: '{"ok":false,"error":"sunset"}'}), preexisting=old)
check("Download liefert Fehlerseite (143-Byte-Fall): Exit != 0, kein ZIP, altes Jar bleibt", rc != 0 and files.get("server.jar") == b"ALTES-JAR" and "not a jar" in out, f"{rc} {out[-300:]}")
rc, out, files, _, _ = run_install(routes(**{DL: b"PK\x03\x04kaputt"}), preexisting=old)
check("Jar mit PK-Kopf aber beschaedigt: Exit != 0", rc != 0 and files.get("server.jar") == b"ALTES-JAR", f"{rc} {out[-300:]}")
rc, out, files, _, _ = run_install(routes(**{f"{API}/versions/26.1.1/builds/latest": build(sha="0" * 64)}), preexisting=old)
check("falsche Pruefsumme: Exit != 0", rc != 0 and "Checksum mismatch" in out and files.get("server.jar") == b"ALTES-JAR", f"{rc} {out[-300:]}")
rc, out, files, _, _ = run_install(routes(**{f"{API}/versions/26.1.1/builds/latest": json.dumps({"id": 7, "downloads": {}})}))
check("Build ohne server-Download: Exit != 0", rc != 0 and "No server download" in out, f"{rc} {out[-200:]}")
rc, out, files, _, _ = run_install(routes(**{DL: b""}))
check("leerer Download: Exit != 0", rc != 0 and "server.jar" not in files, f"{rc} {out[-200:]}")
rc, out, files, _, _ = run_install({k: v for k, v in routes().items() if k != PROPS})
check("server.properties nicht ladbar: nur Warnung, Install gelingt", rc == 0 and "WARNING" in out and "server.properties" not in files and files.get("server.jar") == JAR, out[-300:])

print("Paper-Install: Ersetzen und eigener Link")
rc, out, files, _, _ = run_install(routes(), preexisting=old)
check("altes server.jar wird nach erfolgreichem Download zu server.jar.old", rc == 0 and files.get("server.jar.old") == b"ALTES-JAR" and files.get("server.jar") == JAR)
rc, out, files, _, _ = run_install(routes(), {"SERVER_JARFILE": "paper.jar"})
check("SERVER_JARFILE wird respektiert", rc == 0 and files.get("paper.jar") == JAR and "server.jar" not in files)
CUSTOM = "https://example.test/mein-paper-26.1.1.jar"
rc, out, files, reqs, _ = run_install({CUSTOM: JAR, PROPS: "x"}, {"DL_PATH": "https://example.test/mein-paper-{{MINECRAFT_VERSION}}.jar", "MINECRAFT_VERSION": "26.1.1"})
check("DL_PATH: Platzhalter ersetzt, keine Fill-Abfrage", rc == 0 and files.get("server.jar") == JAR and CUSTOM in reqs and not any("fill.papermc.io" in u for u in reqs), f"{rc} {out[-300:]} {reqs}")
with tempfile.TemporaryDirectory() as td:
    marker = os.path.join(td, "pwned")
    rc, out, files, reqs, _ = run_install({}, {"DL_PATH": f"https://example.test/$(touch {marker}).jar"})
    check("DL_PATH wird nie ausgefuehrt (Command-Substitution bleibt Text)", not os.path.exists(marker))
rc, out, files, reqs, _ = run_install({}, {"DL_PATH": "file:///etc/passwd"})
check("DL_PATH nur http(s)", rc != 0 and "http(s)" in out and not reqs)

# ── install-wings.sh ─────────────────────────────────────
print("install-wings.sh")
WINGS_SH = open(os.path.join(ROOT, "scripts", "install-wings.sh"), encoding="utf-8").read()
check("Syntax (bash -n)", subprocess.run(["bash", "-n", os.path.join(ROOT, "scripts", "install-wings.sh")], capture_output=True).returncode == 0)
check("kein Heredoc zusammen mit Here-String mehr", "<<<" not in WINGS_SH)
m = re.search(r"printf '%s' \"\$RESP\" \| python3 -c '([^']+)' \"\$CONF_DIR/config.yml\"", WINGS_SH)
check("config.yml-Abruf per printf | python3 -c", m is not None)
if m:
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "config.yml")
        payload = json.dumps({"yaml": "debug: false\nremote: https://p.example\nname: Gr\u00fcn\n", "ok": True, "x": None, "y": False})
        r = subprocess.run(["bash", "-c", f"printf '%s' \"$RESP\" | python3 -c '{m.group(1)}' \"$T\""], env={**os.environ, "RESP": payload, "T": target}, capture_output=True, text=True)
        check("JSON mit true/false/null wird gelesen (kein NameError), YAML geschrieben",
              r.returncode == 0 and open(target, encoding="utf-8").read().startswith("debug: false\nremote: https://p.example\nname: Gr\u00fcn"), r.stderr)
        r = subprocess.run(["bash", "-c", f"printf '%s' \"$RESP\" | python3 -c '{m.group(1)}' \"$T\""], env={**os.environ, "RESP": "kein json", "T": target}, capture_output=True, text=True)
        check("kaputte Antwort: Fehler (Exit != 0)", r.returncode != 0)
usage = subprocess.run(["bash", os.path.join(ROOT, "scripts", "install-wings.sh"), "--help"], capture_output=True, text=True)
check("--help nennt --install-docker und --grub-swapaccount", usage.returncode == 0 and "--install-docker" in usage.stdout and "--grub-swapaccount" in usage.stdout, usage.stdout[-300:])
a = WINGS_SH.index("get.docker.com")
lines = WINGS_SH.splitlines()
idx = next(i for i, ln in enumerate(lines) if "get.docker.com" in ln and not ln.lstrip().startswith("#"))
check("Docker-Installation nur hinter --install-docker", "if $INSTALL_DOCKER" in " ".join(lines[max(0, idx - 3):idx]), lines[idx - 3:idx])
g = WINGS_SH.index('sed -i \'s/^GRUB_CMDLINE_LINUX_DEFAULT')
check("GRUB-Aenderung nur hinter --grub-swapaccount", "if $GRUB_SWAP" in WINGS_SH[WINGS_SH.rfind("if $GRUB_SWAP", 0, g):g])
if os.geteuid() == 0:
    with tempfile.TemporaryDirectory() as td:
        bindir = os.path.join(td, "bin")
        os.makedirs(bindir)
        for tool in ("bash", "id", "uname", "grep", "sed", "awk", "cat", "date", "stat", "curl", "mkdir", "head", "tr", "cp", "chmod"):
            src = subprocess.run(["bash", "-c", f"command -v {tool}"], capture_output=True, text=True).stdout.strip()
            if src:
                os.symlink(src, os.path.join(bindir, tool))
        cfg = os.path.join(td, "c.yml")
        open(cfg, "w").write("remote: https://p\n")
        r = subprocess.run([os.path.join(bindir, "bash"), os.path.join(ROOT, "scripts", "install-wings.sh"), "--config", cfg],
                           env={"PATH": bindir}, capture_output=True, text=True)
        check("ohne Docker und ohne Flag: Abbruch mit Hinweis, nichts installiert", r.returncode != 0 and "Docker fehlt" in r.stderr and "--install-docker" in r.stderr and "get.docker.com" not in r.stdout, r.stdout + r.stderr)

# ── Docker-Netz (M78): Konfig-Export und Ueberlappungs-Warnung ──
print("Docker-Netz")
import ipaddress
import yaml as _yaml
from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.users.models import User

app = create_app("testing")
with app.app_context():
    db.create_all()
    adm = User(username="adm", email="adm@t.local", is_admin=True)
    adm.set_password("test1234")
    db.session.add(adm)
    db.session.commit()
    ADMIN = {"X-User-Id": str(adm.id)}
c = app.test_client()


_agent_n = [0]


def agent_config(**fields):
    _agent_n[0] += 1
    n = _agent_n[0]
    r = c.post("/api/admin/agents", json={"name": f"n{n}", "fqdn": f"n{n}.t.local", **fields}, headers=ADMIN)
    assert r.status_code == 201, r.get_data(as_text=True)
    cfg = c.get(f"/api/admin/agents/{r.json['id']}/configuration", headers=ADMIN).json
    return cfg["config"], cfg["yaml"]


cfg, yml = agent_config()
v4 = cfg["docker"]["network"]["interfaces"]["v4"]
check("Export: Subnetz 172.30.0.0/16, Gateway 172.30.0.1", v4 == {"subnet": "172.30.0.0/16", "gateway": "172.30.0.1"}, str(cfg["docker"]))
check("Export: docker.network.interface = Gateway-Adresse (Wings erwartet hier eine IP)", cfg["docker"]["network"]["interface"] == "172.30.0.1")
check("Export: YAML identisch zur Config und ohne 172.18", _yaml.safe_load(yml) == cfg and "172.18" not in yml)
app.config["WINGS_DOCKER_SUBNET"] = "10.77.0.0/20"
cfg, _ = agent_config(daemon_listen=8081)
check("WINGS_DOCKER_SUBNET aenderbar, Gateway = erste Hostadresse", cfg["docker"]["network"]["interfaces"]["v4"] == {"subnet": "10.77.0.0/20", "gateway": "10.77.0.1"})
app.config["WINGS_DOCKER_SUBNET"] = "kaputt"
cfg, _ = agent_config(daemon_listen=8082)
check("ungueltiger Wert im laufenden Betrieb: Rueckfall auf 172.30.0.0/16", cfg["docker"]["network"]["interfaces"]["v4"]["subnet"] == "172.30.0.0/16")
app.config["WINGS_DOCKER_SUBNET"] = "172.30.0.0/16"

from app.config import ProductionConfig
mk = lambda **kw: type("C", (ProductionConfig,), kw)
iss = lambda **kw: [i for i in mk(**kw).validate_production() if "WINGS_DOCKER_SUBNET" in i]
check("Produktions-Check: Standard ok", ProductionConfig.WINGS_DOCKER_SUBNET == "172.30.0.0/16" and not iss())
check("Produktions-Check: ungueltig (kein Netz, Host-Bits, IPv6, /32, /4) ist KRITISCH",
      all(len(iss(WINGS_DOCKER_SUBNET=v)) == 1 and iss(WINGS_DOCKER_SUBNET=v)[0].startswith("KRITISCH") for v in ("abc", "172.30.0.5/16", "fd00::/64", "172.30.0.1/32", "10.0.0.0/4")))
check("Produktions-Check: 172.18.0.0/16 und 172.17.0.0/16 sind eine WARNUNG", all(iss(WINGS_DOCKER_SUBNET=v)[0].startswith("WARNUNG") for v in ("172.18.0.0/16", "172.17.0.0/20")))

# Ueberlappungs-Pruefung des Installers mit einem Fake-docker
nc = re.search(r"# NETCHECK_BEGIN\nread -r -d '' NETCHECK <<'PY' \|\| true\n(.*?)\nPY\n# NETCHECK_END", WINGS_SH, re.S)
check("Ueberlappungs-Pruefung im Installer vorhanden", nc is not None)
if nc:
    def netcheck(config_yml, networks):
        with tempfile.TemporaryDirectory() as td:
            bindir = os.path.join(td, "bin")
            os.makedirs(bindir)
            nets = [{"Name": n, "Id": f"id{i}", "IPAM": {"Config": [{"Subnet": sn} for sn in subs]}} for i, (n, subs) in enumerate(networks)]
            open(os.path.join(td, "nets.json"), "w").write(json.dumps(nets))
            open(os.path.join(bindir, "docker"), "w").write("#!/bin/bash\nif [ \"$2\" = ls ]; then for i in $(seq 0 %d); do echo id$i; done; else cat %s/nets.json; fi\n" % (max(len(nets) - 1, 0), td))
            os.chmod(os.path.join(bindir, "docker"), 0o755)
            cfgf = os.path.join(td, "config.yml")
            open(cfgf, "w").write(config_yml)
            r = subprocess.run([sys.executable, "-c", nc.group(1), cfgf], env={**os.environ, "PATH": bindir + os.pathsep + os.environ["PATH"]}, capture_output=True, text=True)
            return r.returncode, [ln.split("|") for ln in r.stdout.splitlines()]
    base = "docker:\n  network:\n    name: %s\n    interfaces:\n      v4:\n        subnet: %s\n        gateway: %s\n"
    compose = [("astra_default", ["172.18.0.0/16"]), ("bridge", ["172.17.0.0/16"]), ("host", [])]
    rc, hits = netcheck(base % ("pterodactyl_nw", "172.18.0.0/16", "172.18.0.1"), compose)
    check("Pilot-Fall: 172.18.0.0/16 ueberlappt astra_default -> Warnung", rc == 0 and hits == [["172.18.0.0/16", "astra_default", "172.18.0.0/16"]], str(hits))
    rc, hits = netcheck(base % ("pterodactyl_nw", "172.30.0.0/16", "172.30.0.1"), compose)
    check("172.30.0.0/16 ist frei -> keine Warnung", rc == 0 and hits == [], str(hits))
    rc, hits = netcheck(base % ("pterodactyl_nw", "172.18.0.0/16", "172.18.0.1"), [("pterodactyl_nw", ["172.18.0.0/16"])])
    check("das eigene Wings-Netz zaehlt nicht als Konflikt", rc == 0 and hits == [], str(hits))
    rc, hits = netcheck(base % ("astra_nw", "172.30.5.0/24", "172.30.5.1"), [("andere", ["172.30.0.0/16"])])
    check("kleineres Subnetz innerhalb eines groesseren Netzes -> Warnung", rc == 0 and len(hits) == 1 and hits[0][1] == "andere", str(hits))
    rc, hits = netcheck("debug: false\n", compose)
    check("config.yml ohne Subnetz: keine Ausgabe, kein Fehler", rc == 0 and hits == [])
    rc, hits = netcheck(base % ("x", "172.18.0.0/16", "172.18.0.1"), [("v6", ["fd00::/64"]), ("kaputt", ["nicht-ip"])])
    check("IPv6- und kaputte Eintraege stoeren nicht", rc == 0 and hits == [], str(hits))

# ── White-Label der Wings-Konfiguration (M78) ───────────
print("White-Label")
cfg, yml = agent_config()
sysd = cfg["system"]
check("neuer Agent: Standard-Datenverzeichnis /var/lib/astra/volumes", sysd["data"] == "/var/lib/astra/volumes", sysd["data"])
check("system.*: astra-Pfade und -Benutzer", (sysd["root_directory"], sysd["log_directory"], sysd["archive_directory"], sysd["backup_directory"], sysd["tmp_directory"], sysd["username"])
      == ("/var/lib/astra", "/var/log/astra", "/var/lib/astra/archives", "/var/lib/astra/backups", "/tmp/astra", "astra"), str(sysd))
net = cfg["docker"]["network"]
check("docker.network: Name und network_mode astra_nw, interface bleibt eine IP", net["name"] == "astra_nw" and net["network_mode"] == "astra_nw" and net["interface"] == "172.30.0.1", str(net))
check("kein 'pterodactyl' im Export eines neuen Agents (auch nicht im YAML)", "pterodactyl" not in yml.lower() and "pelican" not in yml.lower(), yml)
check("SFTP/API-Felder unveraendert", sysd["sftp"]["bind_port"] == 2022 and cfg["api"]["port"] == 8080)
cfg, yml = agent_config(daemon_base="/var/lib/pterodactyl/volumes", daemon_listen=8090)
check("Bestandsnode /var/lib/pterodactyl/volumes: alte Namen bleiben (root, Logs, Benutzer, Netz)",
      (cfg["system"]["root_directory"], cfg["system"]["log_directory"], cfg["system"]["backup_directory"], cfg["system"]["username"], cfg["docker"]["network"]["name"])
      == ("/var/lib/pterodactyl", "/var/log/pterodactyl", "/var/lib/pterodactyl/backups", "pterodactyl", "pterodactyl_nw"), str(cfg["system"]))
check("... aber das Docker-Subnetz ist trotzdem der freie Bereich", cfg["docker"]["network"]["interfaces"]["v4"]["subnet"] == "172.30.0.0/16")
cfg, yml = agent_config(daemon_base="/var/lib/pelican/volumes", daemon_listen=8091)
check("Bestandsnode Pelican: pelican-Namen", cfg["system"]["root_directory"] == "/var/lib/pelican" and cfg["system"]["username"] == "pelican" and cfg["docker"]["network"]["name"] == "pelican_nw", str(cfg["system"]))
cfg, yml = agent_config(daemon_base="/srv/wings", daemon_listen=8092)
check("eigenes Datenverzeichnis (/srv/wings): data bleibt, sonst astra-Namen", cfg["system"]["data"] == "/srv/wings" and cfg["system"]["root_directory"] == "/var/lib/astra" and cfg["system"]["username"] == "astra")
cfg, yml = agent_config(daemon_base="/var/lib/pterodactyl2/volumes", daemon_listen=8093)
check("aehnlicher Praefix (/var/lib/pterodactyl2) gilt nicht als Bestandsnode", cfg["system"]["username"] == "astra")
check("Export-YAML ist mit PyYAML lesbar und identisch", _yaml.safe_load(yml) == cfg)

check("Installer: Konfigurationsordner /etc/astra", re.search(r"^CONF_DIR=/etc/astra$", WINGS_SH, re.M) is not None)
check("Installer: systemd-Unit startet wings --config $CONF_DIR/config.yml", "ExecStart=/usr/local/bin/wings --config $CONF_DIR/config.yml" in WINGS_SH)
check("Installer: Fallback-Datenordner /var/lib/astra/volumes", '"${DATA_DIR:-/var/lib/astra/volumes}"' in WINGS_SH)
check("Installer: kein /etc/pterodactyl als Ziel mehr (nur als Hinweis auf Altbestand)", "CONF_DIR=/etc/pterodactyl" not in WINGS_SH and "for old in /etc/pterodactyl /etc/pelican" in WINGS_SH)
check("Installer: Hinweis auf Altbestand", "aeltere Konfiguration" in WINGS_SH)

# ── Agent-Kapazitaet und Endpoint-Zuweisung (Pruefung, M78) ──
print("Agent-Kapazitaet")
from app.domain.blueprints.models import Blueprint
with app.app_context():
    kd = User(username="kd", email="kd@t.local")
    kd.set_password("test1234")
    bp = Blueprint(name="mc", docker_image="img", startup_command="run")
    db.session.add_all([kd, bp])
    db.session.commit()
    KD_ID, BP_ID = kd.id, bp.id
    KD = {"X-User-Id": str(kd.id)}
r = c.post("/api/admin/agents", json={"name": "cap1", "fqdn": "cap1.t.local", "memory_total": 8192, "disk_total": 100000, "cpu_total": 400, "memory_overalloc": 10}, headers=ADMIN)
check("POST /api/admin/agents nimmt memory_total/disk_total/cpu_total (+ *_overalloc) an und gibt sie unter denselben Namen zurueck",
      r.status_code == 201 and (r.json["memory_total"], r.json["disk_total"], r.json["cpu_total"], r.json["memory_overalloc"]) == (8192, 100000, 400, 10), str(r.json))
CAP = r.json["id"]
r = c.patch(f"/api/admin/agents/{CAP}", json={"memory_total": 16384, "disk_total": 200000}, headers=ADMIN)
check("PATCH /api/admin/agents/<id> aendert die Kapazitaet", r.status_code == 200 and r.json["memory_total"] == 16384 and r.json["disk_total"] == 200000 and r.json["cpu_total"] == 400, str(r.json))
lst = c.get("/api/admin/agents", headers=ADMIN).json
check("GET /api/admin/agents (Liste) enthaelt die Felder", any(a["id"] == CAP and a["memory_total"] == 16384 for a in lst))
check("negative Kapazitaet -> 400", c.patch(f"/api/admin/agents/{CAP}", json={"memory_total": -1}, headers=ADMIN).status_code == 400)
check("Text statt Zahl -> 400", c.patch(f"/api/admin/agents/{CAP}", json={"disk_total": "viel"}, headers=ADMIN).status_code == 400)
with app.app_context():
    capsum = db.session.get(Agent, CAP).get_capacity_summary()
check("Kapazitaets-Zusammenfassung (Fleet/Monitoring) nutzt memory_total_mb/disk_total_mb/cpu_total_percent", (capsum["memory_total_mb"], capsum["disk_total_mb"], capsum["cpu_total_percent"]) == (16384, 200000, 400), str(capsum))

print("Endpoint-Zuweisung")
r = c.post(f"/api/admin/agents/{CAP}/endpoints/bulk", json={"ip": "0.0.0.0", "port_start": 25565, "port_end": 25567}, headers=ADMIN)
check("Endpoints anlegen (Bereich)", r.status_code == 201 and r.json["created"] == 3)
r = c.post("/api/admin/instances", json={"name": "s1", "owner_id": KD_ID, "blueprint_id": BP_ID, "agent_id": CAP, "memory": 512, "disk": 1000, "cpu": 50}, headers=ADMIN)
check("Instance ohne endpoint_id: primary_endpoint_id gesetzt (niedrigster freier Port)", r.status_code == 201 and r.json["primary_endpoint_id"] is not None, str(r.json))
conn = r.json["connection"]
check("connection = {host, ip, port, sftp_port, address} im POST-Ergebnis", conn == {"host": "cap1.t.local", "ip": "0.0.0.0", "port": 25565, "sftp_port": 2022, "address": "cap1.t.local:25565"}, str(conn))
UUID = r.json["uuid"]
one = c.get(f"/api/client/instances/{UUID}", headers=KD)
check("GET /api/client/instances/<uuid>: primary_endpoint_id und connection", one.status_code == 200 and one.json["primary_endpoint_id"] == r.json["primary_endpoint_id"] and one.json["connection"] == conn, str(one.json.get("connection")))
lst = c.get("/api/client/instances", headers=KD).json
check("GET /api/client/instances (Liste): connection je Instance", lst and lst[0]["connection"] == conn)
adm_list = c.get("/api/admin/instances", headers=ADMIN).json
check("GET /api/admin/instances (Liste): connection und primary_endpoint_id", any(i["uuid"] == UUID and i["connection"] == conn and i["primary_endpoint_id"] for i in adm_list))
r2 = c.post("/api/admin/instances", json={"name": "s2", "owner_id": KD_ID, "blueprint_id": BP_ID, "agent_id": CAP, "memory": 512, "disk": 1000, "cpu": 50}, headers=ADMIN)
check("zweite Instance bekommt den naechsten freien Endpoint (25566)", r2.status_code == 201 and r2.json["connection"]["port"] == 25566, str(r2.json.get("connection")))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
