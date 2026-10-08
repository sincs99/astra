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

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
