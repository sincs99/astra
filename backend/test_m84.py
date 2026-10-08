"""M84 – Konfig-Export: allowed_origins, Warnungen (remote/localhost), WINGS_SYSTEM_USER."""

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

import yaml as _yaml

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


from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.users.models import User

ROOT = os.path.join(os.path.dirname(__file__), "..")
app = create_app("testing")
with app.app_context():
    db.create_all()
    adm = User(username="adm", email="adm@t.local", is_admin=True)
    adm.set_password("test1234")
    kd = User(username="kd", email="kd@t.local")
    kd.set_password("test1234")
    db.session.add_all([adm, kd])
    db.session.commit()
    AID, KID = adm.id, kd.id
c = app.test_client()
AH = {"X-User-Id": str(AID)}
KH = {"X-User-Id": str(KID)}
_n = [0]


def export(**fields):
    _n[0] += 1
    r = c.post("/api/admin/agents", json={"name": f"n{_n[0]}", "fqdn": f"n{_n[0]}.t.local", **fields}, headers=AH)
    assert r.status_code == 201, r.get_data(as_text=True)
    resp = c.get(f"/api/admin/agents/{r.json['id']}/configuration", headers=AH)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.json


def origins(**cfg):
    app.config.update(cfg)
    return export()["config"]["allowed_origins"]


print("allowed_origins (Punkt 1)")
DEV = dict(FRONTEND_URL="http://localhost:3000", BASE_URL="http://localhost:5000", CORS_ORIGINS="*")
check("Dev-Standard: Frontend und Backend, '*' ignoriert", origins(**DEV) == ["http://localhost:3000", "http://localhost:5000"])
check("Produktion: nur die Domain (Frontend = Backend = Panel)", origins(FRONTEND_URL="https://panel.astrahost.ch", BASE_URL="https://panel.astrahost.ch", CORS_ORIGINS="https://panel.astrahost.ch")
      == ["https://panel.astrahost.ch"])
check("Pilot-Fall: Browser-Origin http://192.168.1.7:3000 aus FRONTEND_URL", "http://192.168.1.7:3000" in origins(FRONTEND_URL="http://192.168.1.7:3000", BASE_URL="http://192.168.1.7:5000", CORS_ORIGINS="*"))
check("CORS mit mehreren Eintraegen: Reihenfolge stabil (Frontend, Backend, dann CORS), keine Duplikate",
      origins(FRONTEND_URL="https://a.example", BASE_URL="https://b.example", CORS_ORIGINS="https://c.example, https://a.example ,https://d.example")
      == ["https://a.example", "https://b.example", "https://c.example", "https://d.example"])
check("'*' mitten in der Liste wird ignoriert", origins(FRONTEND_URL="https://a.example", BASE_URL="https://a.example", CORS_ORIGINS="*,https://z.example") == ["https://a.example", "https://z.example"])
check("Pfade, Query und Schraegstrich fallen weg, Gross/Klein wird vereinheitlicht",
      origins(FRONTEND_URL="HTTPS://Panel.Example/app/?x=1", BASE_URL="https://panel.example/", CORS_ORIGINS="") == ["https://panel.example"])
check("Standardports fallen weg (https:443, http:80), andere bleiben", origins(FRONTEND_URL="https://p.example:443", BASE_URL="http://q.example:80", CORS_ORIGINS="https://r.example:8443")
      == ["https://p.example", "http://q.example", "https://r.example:8443"])
check("ungueltige Eintraege (ohne Schema, ftp, leer) werden uebergangen", origins(FRONTEND_URL="panel.example", BASE_URL="ftp://x.example", CORS_ORIGINS=", ,junk,https://ok.example") == ["https://ok.example"])
check("IPv6-Literal bleibt in Klammern", origins(FRONTEND_URL="http://[::1]:3000", BASE_URL="http://[::1]:5000", CORS_ORIGINS="") == ["http://[::1]:3000", "http://[::1]:5000"])
check("localhost-Eintraege bleiben in der Liste (Dev)", "http://localhost:3000" in origins(**DEV))
app.config.update(**DEV)
exp = export()
check("Export: config.allowed_origins und YAML stimmen ueberein", _yaml.safe_load(exp["yaml"]) == exp["config"] and _yaml.safe_load(exp["yaml"])["allowed_origins"] == ["http://localhost:3000", "http://localhost:5000"])
check("Alle Nodes (neu und Bestand) bekommen allowed_origins", export(daemon_base="/var/lib/pterodactyl/volumes")["config"]["allowed_origins"] == ["http://localhost:3000", "http://localhost:5000"])
check("allowed_origins stehen neben remote", _yaml.safe_load(exp["yaml"])["remote"] == "http://localhost:5000")

# ── Warnungen (Punkt 2) ─────────────────────────────────
print("warnings im Export (Punkt 2)")
WARN_REMOTE = "remote zeigt auf"
WARN_ORIGINS = "allowed_origins enthält nur localhost-Einträge"
app.config.update(DEV)
exp = export()
check("Dev-Standard (localhost): zwei Warnungen als Liste von Strings", isinstance(exp["warnings"], list) and len(exp["warnings"]) == 2 and all(isinstance(w, str) for w in exp["warnings"]), str(exp["warnings"]))
check("... remote zeigt auf localhost mit BASE_URL-Hinweis", exp["warnings"][0].startswith(WARN_REMOTE) and "http://localhost:5000" in exp["warnings"][0] and "BASE_URL" in exp["warnings"][0] and "anderen Host" in exp["warnings"][0], exp["warnings"][0])
check("... allowed_origins nur localhost mit Aufzaehlung", exp["warnings"][1].startswith(WARN_ORIGINS) and "http://localhost:3000" in exp["warnings"][1], exp["warnings"][1])
check("warnings stehen nur in der JSON-Antwort, nicht in config/yaml", "warnings" not in exp["config"] and "warnings" not in exp["yaml"])
app.config.update(FRONTEND_URL="https://panel.astrahost.ch", BASE_URL="https://panel.astrahost.ch", CORS_ORIGINS="https://panel.astrahost.ch")
check("Produktions-Adressen: keine Warnungen (leere Liste)", export()["warnings"] == [])
app.config.update(FRONTEND_URL="http://192.168.1.7:3000", BASE_URL="http://localhost:5000", CORS_ORIGINS="*")
w = export()["warnings"]
check("Pilot-Fall (Browser per LAN-IP, remote localhost): nur die remote-Warnung", len(w) == 1 and w[0].startswith(WARN_REMOTE), str(w))
app.config.update(FRONTEND_URL="http://localhost:3000", BASE_URL="https://panel.astrahost.ch", CORS_ORIGINS="*")
w = export()["warnings"]
check("remote ok, aber Frontend nur localhost: allowed_origins enthaelt BASE_URL -> keine Warnung", w == [], str(w))
for local in ("http://127.0.0.1:5000", "http://[::1]:5000", "http://0.0.0.0:5000", "http://panel.localhost:5000"):
    app.config.update(FRONTEND_URL="https://p.example", BASE_URL=local, CORS_ORIGINS="")
    w = export()["warnings"]
    check(f"{local}: remote-Warnung", len(w) == 1 and w[0].startswith(WARN_REMOTE), str(w))
app.config.update(FRONTEND_URL="https://p.example", BASE_URL="https://localhost.example.com", CORS_ORIGINS="")
check("Domain, die nur mit 'localhost' beginnt, ist nicht lokal", export()["warnings"] == [])
app.config.update(DEV)
app.config.update(ADMIN_GUARD_ENABLED=True)
check("Export fuer Nicht-Admin: weiterhin 403 (keine Warnungen/Konfiguration)", c.get("/api/admin/agents/1/configuration", headers=KH).status_code == 403)
app.config.update(ADMIN_GUARD_ENABLED=False)

from app.config import ProductionConfig
mk = lambda **kw: type("C", (ProductionConfig,), kw)
iss = lambda name, **kw: [i for i in mk(**kw).validate_production() if i.startswith("WARNUNG") and name in i and "localhost" in i]
check("Produktions-Check: BASE_URL localhost -> WARNUNG", len(iss("BASE_URL", BASE_URL="http://localhost:5000", FRONTEND_URL="https://p.example")) == 1)
check("Produktions-Check: FRONTEND_URL localhost -> WARNUNG", len(iss("FRONTEND_URL", BASE_URL="https://p.example", FRONTEND_URL="http://localhost:3000")) == 1)
check("Produktions-Check: oeffentliche Adressen -> keine Warnung", not iss("BASE_URL", BASE_URL="https://p.example", FRONTEND_URL="https://p.example") and not iss("FRONTEND_URL", BASE_URL="https://p.example", FRONTEND_URL="https://p.example"))
check("Produktions-Check: 127.0.0.1 gilt auch", len(iss("BASE_URL", BASE_URL="http://127.0.0.1:5000", FRONTEND_URL="https://p.example")) == 1)

print("install-wings.sh gibt die Warnungen aus")
WINGS_SH = open(os.path.join(ROOT, "scripts", "install-wings.sh"), encoding="utf-8").read()
check("Syntax", subprocess.run(["bash", "-n", os.path.join(ROOT, "scripts", "install-wings.sh")], capture_output=True).returncode == 0)
m = re.search(r"WARNINGS=\$\(printf '%s' \"\$RESP\" \| python3 -c '([^']+)' \"\$CONF_DIR/config.yml\"\)", WINGS_SH)
check("Abruf liest yaml und warnings in einem Aufruf", m is not None)
wfun = re.search(r"^warn\(\) \{.*\}$", WINGS_SH, re.M)
check("warn()-Funktion vorhanden (gelb auf dem Terminal)", wfun is not None and "033[33m" in wfun.group(0))
if m and wfun:
    import json
    with tempfile.TemporaryDirectory() as td:
        resp = json.dumps({"yaml": "remote: http://localhost:5000\n", "warnings": ["Erste Warnung", "Zweite mit Umlaut ä"]})
        script = f"""set -euo pipefail
{wfun.group(0)}
CONF_DIR={td}
RESP='{resp}'
WARNINGS=$(printf '%s' "$RESP" | python3 -c '{m.group(1)}' "$CONF_DIR/config.yml")
printf '%s\\n' "$WARNINGS" | while IFS= read -r w; do
    if [ -n "$w" ]; then warn "$w"; fi
done
echo done
"""
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        check("zwei Warnungen -> zwei Zeilen '[wings] WARNUNG: ...', kein Abbruch, YAML geschrieben",
              r.returncode == 0 and "[wings] WARNUNG: Erste Warnung" in r.stdout and "[wings] WARNUNG: Zweite mit Umlaut ä" in r.stdout and r.stdout.strip().endswith("done")
              and open(os.path.join(td, "config.yml"), encoding="utf-8").read().startswith("remote:"), r.stdout + r.stderr)
        resp0 = json.dumps({"yaml": "remote: https://p\n", "warnings": []})
        r = subprocess.run(["bash", "-c", script.replace(resp, resp0)], capture_output=True, text=True)
        check("keine Warnungen: keine WARNUNG-Zeile und kein Abbruch unter set -e", r.returncode == 0 and "WARNUNG" not in r.stdout and r.stdout.strip().endswith("done"), r.stdout + r.stderr)
        resp1 = json.dumps({"yaml": "remote: https://p\n"})
        r = subprocess.run(["bash", "-c", script.replace(resp, resp1)], capture_output=True, text=True)
        check("aelteres Panel ohne Feld warnings: kein Fehler", r.returncode == 0 and "WARNUNG" not in r.stdout, r.stdout + r.stderr)
loc = re.search(r"# NOTE_LOCAL_BEGIN\n(.*?)# NOTE_LOCAL_END", WINGS_SH, re.S)
check("--config-Pfad: Pruefung auf remote=localhost vorhanden", loc is not None)
if loc and wfun:
    def local(remote):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "config.yml"), "w").write(f"debug: false\nremote: {remote}\n")
            r = subprocess.run(["bash", "-c", f"set -euo pipefail\n{wfun.group(0)}\nCONF_DIR={td}\n{loc.group(1)}\necho done"], capture_output=True, text=True)
            return r.returncode, r.stdout
    for url in ("http://localhost:5000", "http://127.0.0.1:5000", "http://0.0.0.0:5000", "http://[::1]:5000"):
        rc, out = local(url)
        check(f"--config mit remote {url}: Warnung, kein Abbruch", rc == 0 and "WARNUNG: remote in der config.yml zeigt auf" in out and out.strip().endswith("done"), out)
    rc, out = local("https://panel.astrahost.ch")
    check("--config mit oeffentlichem remote: keine Warnung", rc == 0 and "WARNUNG" not in out)

# ── Systembenutzer (Punkt 3) ────────────────────────────
print("WINGS_SYSTEM_USER (Punkt 3)")
app.config.update(DEV, WINGS_SYSTEM_USER="astra")
check("Standard: system.username = astra", export()["config"]["system"]["username"] == "astra")
app.config.update(WINGS_SYSTEM_USER="wingsd")
cfg = export()["config"]
check("WINGS_SYSTEM_USER=wingsd wirkt im Export (YAML identisch)", cfg["system"]["username"] == "wingsd" and cfg["system"]["root_directory"] == "/var/lib/astra")
check("Bestandsnode (/var/lib/pterodactyl) bleibt pterodactyl", export(daemon_base="/var/lib/pterodactyl/volumes")["config"]["system"]["username"] == "pterodactyl")
check("Bestandsnode (/var/lib/pelican) bleibt pelican", export(daemon_base="/var/lib/pelican/volumes")["config"]["system"]["username"] == "pelican")
for bad in ("", "Root", "root", "nobody", "daemon", "9abc", "a b", "x" * 33, "ad;min", "/etc"):
    app.config.update(WINGS_SYSTEM_USER=bad)
    check(f"ungueltiger Wert {bad!r} im laufenden Betrieb: Rueckfall auf astra", export()["config"]["system"]["username"] == "astra")
app.config.update(WINGS_SYSTEM_USER="node_1-svc")
check("Unterstrich, Bindestrich und Ziffern erlaubt", export()["config"]["system"]["username"] == "node_1-svc")
app.config.update(WINGS_SYSTEM_USER="astra")
bad_user = lambda v: [i for i in mk(WINGS_SYSTEM_USER=v).validate_production() if "WINGS_SYSTEM_USER" in i]
check("Produktions-Check: Standard ok", ProductionConfig.WINGS_SYSTEM_USER == "astra" and not bad_user("astra") and not bad_user("wingsd"))
check("Produktions-Check: ungueltig ist KRITISCH", all(len(bad_user(v)) == 1 and bad_user(v)[0].startswith("KRITISCH") for v in ("root", "Admin", "1abc", "a b", "x" * 40, "nobody", "daemon")))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
