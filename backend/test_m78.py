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

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
