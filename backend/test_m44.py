"""M44 – Produkte und Bestellungen (manuelle Zahlung)."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.billing.models import Order, Product
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
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
    u1 = User(username="kunde1", email="k1@t.local")
    u2 = User(username="kunde2", email="k2@t.local")
    for u in (admin, u1, u2):
        u.set_password("test1234")
    bp = Blueprint(name="mc", docker_image="img", startup_command="run")
    agent = Agent(name="n1", fqdn="n1.test", memory_total=4096, disk_total=100000, cpu_total=400)
    db.session.add_all([admin, u1, u2, bp, agent])
    db.session.commit()
    for i in range(4):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, bp=bp.id, agent=agent.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
U2 = {"X-User-Id": str(ids["u2"])}

PROD = {"name": "Starter", "description": "1 GB", "blueprint_id": ids["bp"], "memory": 1024, "disk": 5000,
        "cpu": 100, "price_cents": 499, "currency": "eur", "billing_period_days": 30}

print("Admin: Produkte")
r = c.post("/api/admin/products", json=PROD, headers=AH)
check("Produkt anlegen -> 201", r.status_code == 201, r.get_data(as_text=True)[:200])
pid = r.json["id"]
check("Waehrung normalisiert, Standardwerte", r.json["currency"] == "EUR"
      and r.json["resources"]["io"] == 500 and r.json["resources"]["swap"] == 0 and r.json["is_active"] is True)
bad = [
    ({**PROD, "name": ""}, "leerer Name"),
    ({**PROD, "memory": 0}, "memory 0"),
    ({**PROD, "memory": "1024"}, "memory als String"),
    ({**PROD, "memory": True}, "memory als bool"),
    ({**PROD, "price_cents": -1}, "negativer Preis"),
    ({**PROD, "currency": "EURO"}, "ungueltige Waehrung"),
    ({**PROD, "billing_period_days": 0}, "Laufzeit 0"),
    ({**PROD, "io": 5}, "io 5"),
    ({**PROD, "is_active": "ja"}, "is_active kein bool"),
    ({k: v for k, v in PROD.items() if k != "cpu"}, "cpu fehlt"),
]
for body, label in bad:
    check(f"{label} -> 400", c.post("/api/admin/products", json=body, headers=AH).status_code == 400)
check("unbekannter Blueprint -> 404", c.post("/api/admin/products", json={**PROD, "blueprint_id": 9999}, headers=AH).status_code == 404)
r = c.post("/api/admin/products", json={**PROD, "name": "Gratis", "price_cents": 0}, headers=AH)
check("kostenlos ohne max_instances_per_user -> 400", r.status_code == 400 and "max_instances_per_user" in r.json["error"])
r = c.post("/api/admin/products", json={**PROD, "name": "Gratis", "price_cents": 0, "max_instances_per_user": 1,
                                         "memory": 256, "disk": 1000, "cpu": 50}, headers=AH)
check("kostenlos mit Limit -> 201", r.status_code == 201)
free_id = r.json["id"]
r = c.patch(f"/api/admin/products/{free_id}", json={"max_instances_per_user": None}, headers=AH)
check("Limit bei Gratis-Produkt entfernen -> 400", r.status_code == 400)
r = c.patch(f"/api/admin/products/{pid}", json={"description": "neu", "price_cents": 599}, headers=AH)
check("PATCH teilweise -> 200", r.status_code == 200 and r.json["description"] == "neu" and r.json["price_cents"] == 599)
r = c.patch(f"/api/admin/products/{pid}", json={"price_cents": 499}, headers=AH)
check("GET /products/{id}", c.get(f"/api/admin/products/{pid}", headers=AH).json["name"] == "Starter")
check("unbekanntes Produkt -> 404", c.get("/api/admin/products/9999", headers=AH).status_code == 404)
r = c.post("/api/admin/products", json={**PROD, "name": "Inaktiv", "is_active": False}, headers=AH)
inactive_id = r.json["id"]

print("Oeffentliche Produktliste")
r = c.get("/api/client/products")
names = [p["name"] for p in r.json]
check("ohne Login erreichbar", r.status_code == 200)
check("nur aktive Produkte", "Starter" in names and "Gratis" in names and "Inaktiv" not in names, str(names))
check("keine internen Felder", all(not ({"blueprint_id", "is_active", "max_instances_per_user"} & set(p)) for p in r.json))
check("Preis und Ressourcen sichtbar", r.json[-1]["price_cents"] == 499 and r.json[-1]["resources"]["memory"] == 1024)

print("Bestellung anlegen")
check("ohne Login -> 401", c.post("/api/client/orders", json={"product_id": pid}).status_code == 401)
r = c.post("/api/client/orders", json={"product_id": pid, "name": "Mein Server"}, headers=U1)
check("Bestellung -> 201 pending_payment", r.status_code == 201 and r.json["status"] == "pending_payment", r.get_data(as_text=True)[:200])
oid = r.json["uuid"]
check("Name und Schnappschuss", r.json["instance_name"] == "Mein Server" and r.json["price_cents"] == 499
      and r.json["resources"]["memory"] == 1024 and r.json["instance_uuid"] is None)
with app.app_context():
    check("noch keine Instance angelegt", Instance.query.count() == 0)
r = c.post("/api/client/orders", json={"product_id": pid}, headers=U1)
check("ohne Namen: generierter Name", r.status_code == 201 and r.json["instance_name"].startswith("Starter "))
c.post(f"/api/client/orders/{r.json['uuid']}/cancel", headers=U1)
check("unbekanntes Produkt -> 404", c.post("/api/client/orders", json={"product_id": 9999}, headers=U1).status_code == 404)
check("inaktives Produkt -> 404", c.post("/api/client/orders", json={"product_id": inactive_id}, headers=U1).status_code == 404)
check("product_id fehlt -> 400", c.post("/api/client/orders", json={}, headers=U1).status_code == 400)
check("product_id als String -> 400", c.post("/api/client/orders", json={"product_id": "1"}, headers=U1).status_code == 400)
check("Name zu lang -> 400", c.post("/api/client/orders", json={"product_id": pid, "name": "x" * 121}, headers=U1).status_code == 400)
# Preis aendern: Bestellung behaelt den Schnappschuss
c.patch(f"/api/admin/products/{pid}", json={"price_cents": 999, "memory": 2048}, headers=AH)
r = c.get(f"/api/client/orders/{oid}", headers=U1)
check("Preisaenderung beruehrt bestehende Bestellung nicht", r.json["price_cents"] == 499 and r.json["resources"]["memory"] == 1024)
c.patch(f"/api/admin/products/{pid}", json={"price_cents": 499, "memory": 1024}, headers=AH)

print("Isolation und Rechte")
check("fremder Kunde sieht Bestellung nicht -> 404", c.get(f"/api/client/orders/{oid}", headers=U2).status_code == 404)
check("fremder Kunde kann nicht stornieren -> 404", c.post(f"/api/client/orders/{oid}/cancel", headers=U2).status_code == 404)
check("Liste nur eigene", [o["uuid"] for o in c.get("/api/client/orders", headers=U2).json] == [])
check("Kunde 1 sieht seine Bestellung", oid in [o["uuid"] for o in c.get("/api/client/orders", headers=U1).json])
app.config["ADMIN_GUARD_ENABLED"] = True
check("Admin-Produkte ohne Login -> 401", c.get("/api/admin/products").status_code == 401)
check("Admin-Produkte als Kunde -> 403", c.post("/api/admin/products", json=PROD, headers=U1).status_code == 403)
check("mark-paid als Kunde -> 403", c.post(f"/api/admin/orders/{oid}/mark-paid", headers=U1).status_code == 403)
check("Admin-Bestellungen als Kunde -> 403", c.get("/api/admin/orders", headers=U1).status_code == 403)
app.config["ADMIN_GUARD_ENABLED"] = False

print("Limits")
for i in range(3):
    c.post("/api/client/orders", json={"product_id": pid}, headers=U2)
# U2 hat 3 offene, U1 hat 1 offene (oid)
for i in range(2):
    r = c.post("/api/client/orders", json={"product_id": pid}, headers=U2)
r = c.post("/api/client/orders", json={"product_id": pid}, headers=U2)
check("mehr als 5 offene Bestellungen -> 409", r.status_code == 409 and "offene" in r.json["error"], r.get_data(as_text=True))
for o in c.get("/api/client/orders", headers=U2).json:
    c.post(f"/api/client/orders/{o['uuid']}/cancel", headers=U2)
check("nach Storno wieder bestellbar", c.post("/api/client/orders", json={"product_id": pid}, headers=U2).status_code == 201)

print("Zahlung und Bereitstellung")
r = c.post(f"/api/admin/orders/{oid}/mark-paid", json={"payment_reference": "Ueberweisung 1"}, headers=AH)
check("mark-paid -> 200 active", r.status_code == 200 and r.json["status"] == "active", r.get_data(as_text=True)[:250])
check("Instance angelegt und zugeordnet", r.json["instance_uuid"] is not None and r.json["instance_name"] == "Mein Server")
check("Verbindungsadresse in der Bestellung", r.json["connection"] and r.json["connection"]["host"] == "n1.test")
check("Zahlungsreferenz und Zeitstempel", r.json["payment_reference"] == "Ueberweisung 1" and r.json["paid_at"] and r.json["current_period_end"])
with app.app_context():
    o = Order.query.filter_by(uuid=oid).first()
    inst = db.session.get(Instance, o.instance_id)
    check("Instance gehoert dem Kunden", inst.owner_id == ids["u1"])
    check("Ressourcen aus Schnappschuss", (inst.memory, inst.disk, inst.cpu) == (1024, 5000, 100))
    check("Agent automatisch gewaehlt, Endpoint belegt", inst.agent_id == ids["agent"] and inst.primary_endpoint_id is not None)
    check("Laufzeit = paid_at + 30 Tage", (o.current_period_end - o.paid_at).days == 30)
    n_instances = Instance.query.count()
r = c.post(f"/api/admin/orders/{oid}/mark-paid", headers=AH)
check("zweites mark-paid ist idempotent (200, aktiv)", r.status_code == 200 and r.json["status"] == "active")
with app.app_context():
    check("keine zweite Instance", Instance.query.count() == n_instances)
    check("Activity order:paid genau einmal", ActivityLog.query.filter_by(event="order:paid", subject_id=Order.query.filter_by(uuid=oid).first().id).count() == 1)
check("Kunde sieht aktive Bestellung mit Instance", c.get(f"/api/client/orders/{oid}", headers=U1).json["instance_uuid"] is not None)
check("mark-paid unbekannt -> 404", c.post("/api/admin/orders/gibts-nicht/mark-paid", headers=AH).status_code == 404)
check("payment_reference kein String -> 400", c.post(f"/api/admin/orders/{oid}/mark-paid", json={"payment_reference": 5}, headers=AH).status_code == 400)

print("Keine Kapazitaet nach Zahlung")
r = c.post("/api/admin/products", json={**PROD, "name": "Gross", "memory": 3500, "price_cents": 1000}, headers=AH)
big_id = r.json["id"]
o_big = c.post("/api/client/orders", json={"product_id": big_id, "name": "Big"}, headers=U1).json["uuid"]
r = c.post(f"/api/admin/orders/{o_big}/mark-paid", json={"payment_reference": "Ueberweisung 2"}, headers=AH)
check("kein Platz -> 409 mit Hinweis 'bezahlt'", r.status_code == 409 and "bezahlt" in r.json["error"], r.get_data(as_text=True))
r = c.get(f"/api/admin/orders/{o_big}", headers=AH)
check("Status awaiting_provisioning, Zahlung gespeichert", r.json["status"] == "awaiting_provisioning" and r.json["payment_reference"] == "Ueberweisung 2" and r.json["paid_at"])
with app.app_context():
    check("keine halbe Instance", Instance.query.filter_by(name="Big").count() == 0)
    check("Activity order:provision_failed", ActivityLog.query.filter_by(event="order:provision_failed").count() == 1)
    a = db.session.get(Agent, ids["agent"])
    a.memory_total = 16384
    db.session.commit()
r = c.post(f"/api/admin/orders/{o_big}/mark-paid", headers=AH)
check("erneutes mark-paid stellt bereit -> active", r.status_code == 200 and r.json["status"] == "active" and r.json["instance_uuid"])
check("Zahlungsreferenz bleibt die erste", r.json["payment_reference"] == "Ueberweisung 2")
with app.app_context():
    check("Zahlung nicht doppelt verbucht", ActivityLog.query.filter_by(event="order:paid").count() == 2)

print("Stornieren")
o_c = c.post("/api/client/orders", json={"product_id": pid}, headers=U1).json["uuid"]
r = c.post(f"/api/client/orders/{o_c}/cancel", headers=U1)
check("offene Bestellung -> cancelled", r.status_code == 200 and r.json["status"] == "cancelled")
check("storniert kann nicht bezahlt werden -> 409", c.post(f"/api/admin/orders/{o_c}/mark-paid", headers=AH).status_code == 409)
check("erneut stornieren -> 409", c.post(f"/api/client/orders/{o_c}/cancel", headers=U1).status_code == 409)
r = c.post(f"/api/client/orders/{oid}/cancel", headers=U1)
check("aktive Bestellung -> cancel_at_period_end, Status bleibt active",
      r.status_code == 200 and r.json["status"] == "active" and r.json["cancel_at_period_end"] is True and r.json["cancelled_at"])
check("aktive Bestellung weiter ohne Instanzverlust", r.json["instance_uuid"] is not None)
check("doppelte Kuendigung ist idempotent", c.post(f"/api/client/orders/{oid}/cancel", headers=U1).status_code == 200)

print("Gratis-Produkt")
r = c.post("/api/client/orders", json={"product_id": free_id, "name": "Free1"}, headers=U2)
check("Gratis -> sofort aktiv mit Instance", r.status_code == 201 and r.json["status"] == "active" and r.json["instance_uuid"], r.get_data(as_text=True)[:200])
check("Zahlungsreferenz 'free'", r.json["payment_reference"] == "free")
r = c.post("/api/client/orders", json={"product_id": free_id}, headers=U2)
check("Limit 1 pro Kunde -> 409", r.status_code == 409 and "Limit" in r.json["error"])
check("anderer Kunde darf eigenes Gratis-Paket", c.post("/api/client/orders", json={"product_id": free_id}, headers=U1).status_code == 201)

print("Admin: Bestellungen und Produkt loeschen")
r = c.get("/api/admin/orders", headers=AH)
check("Admin-Liste mit Kundennamen", r.status_code == 200 and all("username" in o for o in r.json))
check("Filter status=cancelled", all(o["status"] == "cancelled" for o in c.get("/api/admin/orders?status=cancelled", headers=AH).json))
check("Filter user_id", all(o["user_id"] == ids["u2"] for o in c.get(f"/api/admin/orders?user_id={ids['u2']}", headers=AH).json))
check("ungueltiger Status -> 400", c.get("/api/admin/orders?status=quatsch", headers=AH).status_code == 400)
check("Produkt mit Bestellungen nicht loeschbar -> 409", c.delete(f"/api/admin/products/{pid}", headers=AH).status_code == 409)
check("Blueprint mit Produkten nicht loeschbar -> 409", c.delete(f"/api/admin/blueprints/{ids['bp']}", headers=AH).status_code == 409)
check("unbenutztes Produkt loeschbar", c.delete(f"/api/admin/products/{inactive_id}", headers=AH).status_code == 200)

print("E-Mail-Verifizierung")
app.config["EMAIL_VERIFICATION_REQUIRED"] = True
r = c.post("/api/client/orders", json={"product_id": pid}, headers=U1)
check("unbestaetigt -> 403 email_not_verified", r.status_code == 403 and r.json.get("code") == "email_not_verified")
with app.app_context():
    db.session.get(User, ids["u1"]).email_verified_at = __import__("datetime").datetime.now()
    db.session.commit()
check("bestaetigt -> bestellbar", c.post("/api/client/orders", json={"product_id": pid}, headers=U1).status_code == 201)
app.config["EMAIL_VERIFICATION_REQUIRED"] = False

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
