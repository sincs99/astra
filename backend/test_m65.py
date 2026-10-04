"""M65 – Suche in der Admin-Bestellliste: GET /api/admin/orders?q=..."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
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


app = create_app("testing")
with app.app_context():
    db.create_all()
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    u1 = User(username="pascal", email="p@t.local")
    u2 = User(username="Marie", email="m@t.local")
    for u in (admin, u1, u2):
        u.set_password("test1234")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=4096, disk_total=100000, cpu_total=400)
    bp = Blueprint(name="Minecraft", docker_image="img", startup_command="run")
    db.session.add_all([admin, u1, u2, agent, bp])
    db.session.commit()
    for i in range(5):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
U2 = {"X-User-Id": str(ids["u2"])}

pid = c.post("/api/admin/products", json={"name": "Crew", "blueprint_id": ids["bp"], "memory": 512, "disk": 500,
                                           "cpu": 50, "price_cents": 990, "billing_period_days": 30}, headers=AH).json["id"]
o1 = c.post("/api/client/orders", json={"product_id": pid, "name": "Freitagsrunde"}, headers=U1).json
o2 = c.post("/api/client/orders", json={"product_id": pid, "name": "Valheim Clan"}, headers=U1).json
o3 = c.post("/api/client/orders", json={"product_id": pid, "name": "Bauprojekt"}, headers=U2).json


def search(q, extra=""):
    r = c.get(f"/api/admin/orders?q={q}{extra}", headers=AH)
    return r.status_code, [o["uuid"] for o in r.json] if r.status_code == 200 else r.json


print("Suche")
check("ohne q: alle drei", len(c.get("/api/admin/orders", headers=AH).json) == 3)
check("Verwendungszweck exakt", search(o2["payment_purpose"]) == (200, [o2["uuid"]]), str(search(o2["payment_purpose"])))
check("Verwendungszweck klein geschrieben", search(o2["payment_purpose"].lower()) == (200, [o2["uuid"]]))
check("Verwendungszweck als Praefix ohne Pruefzeichen", search(o2["payment_purpose"].rsplit("-", 1)[0]) == (200, [o2["uuid"]]))
check("Praefix 'ASTRA' trifft alle", search("ASTRA")[1] and len(search("ASTRA")[1]) == 3)
check("Servername Teiltext, Gross-/Kleinschreibung egal", search("valheim") == (200, [o2["uuid"]]))
check("Nutzername Teiltext", search("marie") == (200, [o3["uuid"]]))
check("Nutzername trifft beide Bestellungen des Kunden", sorted(search("pascal")[1]) == sorted([o1["uuid"], o2["uuid"]]))
check("UUID-Praefix", search(o1["uuid"][:8]) == (200, [o1["uuid"]]))
check("UUID-Teilstueck in der Mitte trifft nicht", search(o1["uuid"][4:12]) == (200, []))
check("kein Treffer: leere Liste", search("gibtsnicht") == (200, []))
check("Leerzeichen werden ignoriert", search("%20valheim%20") == (200, [o2["uuid"]]))
check("q kombiniert mit status", search("pascal", "&status=pending_payment")[1] and len(search("pascal", "&status=pending_payment")[1]) == 2)
check("q kombiniert mit fremdem status: leer", search("pascal", "&status=active") == (200, []))

print("Eingabe und Rechte")
check("100 Zeichen: ok", search("a" * 100)[0] == 200)
check("101 Zeichen: 400", search("a" * 101)[0] == 400)
app.config["ADMIN_GUARD_ENABLED"] = True
check("Kunde: 403", c.get("/api/admin/orders?q=x", headers=U1).status_code == 403)
check("ohne Anmeldung: 401", c.get("/api/admin/orders?q=x").status_code == 401)

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
