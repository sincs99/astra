"""M64 – Spielname (blueprint_name) an Instance und Bestellung, Verwendungszweck (payment_purpose)."""

import os
import re
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.billing.models import Order
from app.domain.billing.service import run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.users.models import User
from app.infrastructure import mail
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
    u1 = User(username="k1", email="k1@t.local")
    for u in (admin, u1):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=4096, disk_total=100000, cpu_total=400)
    bp = Blueprint(name="Minecraft Paper 1.21", docker_image="img", startup_command="run")
    db.session.add_all([admin, u1, agent, bp])
    db.session.commit()
    for i in range(5):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, agent=agent.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
PURPOSE = re.compile(r"^ASTRA-\d{4}-[0-9A-F]{2}$")

r = c.post("/api/admin/products", json={"name": "Crew", "blueprint_id": ids["bp"], "memory": 512, "disk": 500,
                                         "cpu": 50, "price_cents": 990, "billing_period_days": 30}, headers=AH)
assert r.status_code == 201, r.get_data(as_text=True)
pid = r.json["id"]

print("Bestellung: Verwendungszweck und Spielname")
r = c.post("/api/client/orders", json={"product_id": pid, "name": "Freitagsrunde"}, headers=U1)
assert r.status_code == 201, r.get_data(as_text=True)
o1 = r.json
check("payment_purpose hat die Form ASTRA-NNNN-XX", bool(PURPOSE.match(o1.get("payment_purpose") or "")), str(o1.get("payment_purpose")))
check("laufende Nummer entspricht der Bestell-ID", o1["payment_purpose"].split("-")[1] == f"{o1['id']:04d}")
check("blueprint_name kommt vom Produkt", o1.get("blueprint_name") == "Minecraft Paper 1.21", str(o1.get("blueprint_name")))
r = c.post("/api/client/orders", json={"product_id": pid, "name": "Zweiter"}, headers=U1)
o2 = r.json
check("zwei Bestellungen, zwei Verwendungszwecke", o2["payment_purpose"] != o1["payment_purpose"])
check("GET liefert denselben Verwendungszweck (stabil)", c.get(f"/api/client/orders/{o1['uuid']}", headers=U1).json["payment_purpose"] == o1["payment_purpose"])
check("Admin-Liste enthaelt den Verwendungszweck",
      any(o["payment_purpose"] == o1["payment_purpose"] for o in c.get("/api/admin/orders", headers=AH).json))
with app.app_context():
    o = Order.query.filter_by(uuid=o1["uuid"]).first()
    check("Pruefzeichen stammen aus der UUID", o.payment_purpose.endswith(o.uuid.replace("-", "")[:2].upper()))
    check("ungespeicherte Bestellung: kein Verwendungszweck", Order(uuid="x").payment_purpose is None)
    check("blueprint_name faellt auf den Schnappschuss zurueck, wenn das Produkt fehlt",
          Order(snapshot={"blueprint_id": ids["bp"]}).blueprint_name == "Minecraft Paper 1.21")
    check("blueprint_name None ohne Blueprint", Order(snapshot={}).blueprint_name is None)

print("Instance: Spielname")
r = c.post(f"/api/admin/orders/{o1['uuid']}/mark-paid", json={"payment_reference": "ueberweisung-1"}, headers=AH)
assert r.status_code == 200 and r.json["status"] == "active", r.get_data(as_text=True)
iu = r.json["instance_uuid"]
with app.app_context():
    assert report_install(c, iu, True).status_code == 204
r = c.get(f"/api/client/instances/{iu}", headers=U1)
check("Kunden-Instance traegt blueprint_name", r.status_code == 200 and r.json.get("blueprint_name") == "Minecraft Paper 1.21", r.get_data(as_text=True)[:200])
check("Kunden-Instance-Liste traegt blueprint_name",
      any(i.get("blueprint_name") == "Minecraft Paper 1.21" for i in c.get("/api/client/instances", headers=U1).json))
r = c.get("/api/admin/instances", headers=AH)
check("Admin-Instance-Liste traegt blueprint_name", any(i.get("blueprint_name") == "Minecraft Paper 1.21" for i in r.json))

print("Beleg und Mails nennen Spiel und Verwendungszweck")
r = c.get(f"/api/client/orders/{o1['uuid']}/receipt?format=json", headers=U1)
check("Beleg-JSON enthaelt blueprint_name und payment_purpose",
      r.status_code == 200 and r.json.get("blueprint_name") == "Minecraft Paper 1.21" and r.json.get("payment_purpose") == o1["payment_purpose"], r.get_data(as_text=True)[:300])
txt = c.get(f"/api/client/orders/{o1['uuid']}/receipt?format=text", headers=U1).get_data(as_text=True)
check("Beleg-Text: Leistung nennt das Spiel", "Gameserver-Paket Crew (Minecraft Paper 1.21), Server 'Freitagsrunde'" in txt, txt)
check("Beleg-Text: Zeile Verwendungszweck", f"Verwendungszweck" in txt and o1["payment_purpose"] in txt, txt)
html = c.get(f"/api/client/orders/{o1['uuid']}/receipt", headers=U1).get_data(as_text=True)
check("Beleg-HTML enthaelt den Verwendungszweck", o1["payment_purpose"] in html)

with app.app_context():
    o = Order.query.filter_by(uuid=o1["uuid"]).first()
    end = o.current_period_end
mail.outbox.clear()
with app.app_context():
    res = run_billing_tick(now=end - timedelta(days=app.config["BILLING_REMINDER_DAYS"]) + timedelta(minutes=1))
rem = [m for m in mail.outbox if "endet bald" in m["subject"]]
check("Erinnerungsmail verschickt", res["reminded"] >= 1 and len(rem) == 1, str(res))
check("Erinnerungsmail nennt den Verwendungszweck", rem and f"Verwendungszweck: {o1['payment_purpose']}" in rem[0]["body"], rem[0]["body"] if rem else "")
mail.outbox.clear()
with app.app_context():
    run_billing_tick(now=end + timedelta(minutes=1))
sus = [m for m in mail.outbox if "überfällig" in m["subject"]]
check("Sperr-Mail nennt den Verwendungszweck", sus and f"Verwendungszweck: {o1['payment_purpose']}" in sus[0]["body"], sus[0]["body"] if sus else str([m["subject"] for m in mail.outbox]))

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
