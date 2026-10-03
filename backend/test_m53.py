"""M53 – Ueberwachung des Billing-Ticks (letzter Lauf, Status-Endpunkt, Preflight-Warnung)."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order
from app.domain.billing.service import get_tick_status, run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.system.models import SystemState
from app.domain.system.upgrade_service import run_preflight_check
from app.domain.users.models import User
from test_helpers import report_install

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
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    own = User(username="own", email="own@t.local")
    for u in (admin, own):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=1024, disk_total=100000, cpu_total=400)
    bp = Blueprint(name="b", docker_image="img", startup_command="run")
    db.session.add_all([admin, own, agent, bp])
    db.session.commit()
    for i in range(8):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, own=own.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
OH = {"X-User-Id": str(ids["own"])}


def status():
    return c.get("/api/admin/billing/status", headers=AH).json


def preflight():
    with app.app_context():
        return run_preflight_check()


def tick(now=None):
    with app.app_context():
        return run_billing_tick(now=now)


print("Ohne Bestellungen ist ein fehlender Tick unkritisch")
s = status()
check("healthy, nie gelaufen, nichts zu tun", s["healthy"] is True and s["last_run_at"] is None and s["age_seconds"] is None and s["orders_needing_tick"] == 0, str(s))
check("Konfiguration: 15 Minuten", s["max_age_minutes"] == 15)
check("Preflight: billing_tick not_needed", preflight()["checks"]["billing_tick"] == "not_needed")

print("Bestellungen warten, Tick lief nie")
r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 200, "disk": 500, "cpu": 50, "price_cents": 100}, headers=AH)
pid = r.json["id"]
def paid(ref):
    ou = c.post("/api/client/orders", json={"product_id": pid}, headers=OH).json["uuid"]
    c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref}, headers=AH)
    return ou
o1 = paid("r1")
s = status()
check("1 Bestellung braucht den Tick", s["orders_needing_tick"] == 1 and s["orders_by_status"].get("active") == 1)
check("nie gelaufen -> unhealthy", s["healthy"] is False and s["last_run_at"] is None)
pf = preflight()
check("Preflight: billing_tick = warning", pf["checks"]["billing_tick"] == "warning", str(pf["checks"]))
msg = [i for i in pf["issues"] if "Billing-Tick" in i]
check("Meldung nennt 'noch nie' und die Zahl der wartenden Bestellungen", msg and "noch nie" in msg[0] and "1 Bestellung" in msg[0], str(msg))
check("Preflight blockiert nicht: nur Warnung", "billing_tick" not in [k for k, v in pf["checks"].items() if isinstance(v, str) and v.startswith("error")])

print("Nach einem Lauf")
res = tick()
s = status()
check("healthy, Zeitpunkt mit UTC-Suffix", s["healthy"] is True and s["last_run_at"].endswith("+00:00"), str(s["last_run_at"]))
check("Alter klein", s["age_seconds"] is not None and 0 <= s["age_seconds"] < 60)
check("Ergebnis des Laufs gespeichert", s["last_summary"] == res and s["last_summary"]["checked"] >= 1, str(s["last_summary"]))
check("Preflight: billing_tick = ok", preflight()["checks"]["billing_tick"] == "ok")
with app.app_context():
    check("genau eine Zeile im Zustandsspeicher", SystemState.query.count() == 1)
    first_updated = db.session.get(SystemState, "billing_tick").updated_at
tick()
with app.app_context():
    check("weiterer Lauf ueberschreibt dieselbe Zeile", SystemState.query.count() == 1)

print("Zu lange her")
tick(now=datetime.utcnow() - timedelta(minutes=20))
s = status()
check("20 Minuten alt -> unhealthy", s["healthy"] is False and 19 * 60 <= s["age_seconds"] <= 21 * 60, str(s["age_seconds"]))
pf = preflight()
msg = [i for i in pf["issues"] if "Billing-Tick" in i]
check("Preflight warnt mit Alter in Minuten", pf["checks"]["billing_tick"] == "warning" and msg and "vor 20 Minuten" in msg[0], str(msg))
app.config["BILLING_TICK_MAX_AGE_MINUTES"] = 30
check("Schwelle per Konfiguration (30 Minuten) -> wieder healthy", status()["healthy"] is True and status()["max_age_minutes"] == 30)
app.config["BILLING_TICK_MAX_AGE_MINUTES"] = 15
tick(now=datetime.utcnow() - timedelta(minutes=14))
check("14 Minuten alt -> noch healthy (Grenze)", status()["healthy"] is True)
tick()

print("Welche Bestellungen den Tick brauchen")
with app.app_context():
    for o in Order.query.all():
        o.status = "cancelled"
    db.session.commit()
tick(now=datetime.utcnow() - timedelta(hours=2))
check("nur stornierte Bestellungen -> kein Tick noetig, trotz altem Lauf healthy", status()["healthy"] is True and status()["orders_needing_tick"] == 0)
for st, expected in (("pending_payment", False), ("expired", False), ("active", True), ("past_due", True), ("awaiting_provisioning", True)):
    with app.app_context():
        o = Order.query.first()
        o.status = st
        db.session.commit()
    s = status()
    check(f"Status {st}: braucht Tick = {expected}", (s["orders_needing_tick"] == 1) is expected, str(s["orders_needing_tick"]))

print("Fehler im Lauf werden vermerkt, Vermerken stoert den Tick nicht")
with app.app_context():
    Order.query.first().status = "active"
    db.session.commit()
with mock.patch.object(billing, "_process_order", side_effect=RuntimeError("kaputt")):
    res = tick()
s = status()
check("Lauf mit Fehler ist trotzdem vermerkt (mit Fehlerliste)", len(s["last_summary"]["errors"]) == 1 and "kaputt" in s["last_summary"]["errors"][0]["error"], str(s["last_summary"]))
with mock.patch("app.domain.system.models.SystemState", side_effect=RuntimeError("DB weg")):
    with app.app_context():
        SystemState.query.delete()
        db.session.commit()
    res = tick()
check("Vermerken schlaegt fehl: Tick liefert trotzdem sein Ergebnis", isinstance(res, dict) and "provisioned" in res, str(res))

print("Zugriff")
app.config["ADMIN_GUARD_ENABLED"] = True
check("ohne Login -> 401", c.get("/api/admin/billing/status").status_code == 401)
check("als Kunde -> 403", c.get("/api/admin/billing/status", headers=OH).status_code == 403)
check("als Admin -> 200", c.get("/api/admin/billing/status", headers=AH).status_code == 200)
app.config["ADMIN_GUARD_ENABLED"] = False

print("CLI vermerkt den Lauf")
with tempfile.TemporaryDirectory() as tmp:
    db_path = f"{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db_path}", "RUNNER_ADAPTER": "stub"}
    subprocess.run([sys.executable, "-c",
                    "from app import create_app;from app.extensions import db;a=create_app()\n"
                    "with a.app_context(): db.create_all()"], env=env, capture_output=True, check=True, cwd=os.path.dirname(__file__))
    out = subprocess.run([sys.executable, "cli.py", "billing-tick"], env=env, capture_output=True, text=True, cwd=os.path.dirname(__file__))
    row = sqlite3.connect(db_path).execute("select value from system_state where key='billing_tick'").fetchone()
value = json.loads(row[0]) if row else {}
check("CLI: Exit 0 und Lauf in system_state vermerkt", out.returncode == 0 and value.get("last_run_at", "").endswith("+00:00")
      and value.get("summary", {}).get("errors") == [], out.stderr[-200:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
