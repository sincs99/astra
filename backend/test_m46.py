"""M46 – Billing-Tick: Ablauf, Karenzzeit, Loeschung, Verlaengerung (Zeit per now= eingefroren)."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.domain.activity.models import ActivityLog
from app.domain.agents.models import Agent
from app.domain.billing import service as billing
from app.domain.billing.models import Order
from app.domain.billing.service import PAYMENT_SUSPEND_REASON, run_billing_tick
from app.domain.blueprints.models import Blueprint
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance
from app.domain.instances.service import get_runner, set_runner
from app.domain.users.models import User
from app.infrastructure import mail
from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
from app.utils.timeutil import iso_utc
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


class RecordingRunner(StubRunnerAdapter):
    def __init__(self):
        super().__init__()
        self.calls = []

    def delete_instance(self, agent, instance):
        self.calls.append(("delete_instance", instance.uuid))
        return super().delete_instance(agent, instance)

    def send_power_action(self, agent, instance, action):
        self.calls.append(("power", instance.uuid, action))
        return super().send_power_action(agent, instance, action)

    def sync_instance(self, agent, instance):
        self.calls.append(("sync", instance.uuid))
        return super().sync_instance(agent, instance)


app = create_app("testing")
GRACE = app.config["BILLING_GRACE_DAYS"]
runner = RecordingRunner()
with app.app_context():
    db.create_all()
    set_runner(runner)
    admin = User(username="adm", email="adm@t.local", is_admin=True)
    u1 = User(username="k1", email="k1@t.local")
    u2 = User(username="k2", email="k2@t.local")
    for u in (admin, u1, u2):
        u.set_password("test1234")
    bp = Blueprint(name="mc", docker_image="img", startup_command="run")
    agent = Agent(name="n1", fqdn="n1.test")
    db.session.add_all([admin, u1, u2, bp, agent])
    db.session.commit()
    for i in range(30):
        db.session.add(Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25565 + i))
    db.session.commit()
    ids = dict(admin=admin.id, u1=u1.id, u2=u2.id, bp=bp.id)

c = app.test_client()
AH = {"X-User-Id": str(ids["admin"])}
U1 = {"X-User-Id": str(ids["u1"])}
T0 = datetime.utcnow()
D = timedelta

r = c.post("/api/admin/products", json={"name": "P", "blueprint_id": ids["bp"], "memory": 512, "disk": 1000, "cpu": 50,
                                         "price_cents": 500, "billing_period_days": 30}, headers=AH)
PID = r.json["id"]
n = [0]


def paid_order(user_hdr=U1, ref=None):
    """Bestellung anlegen und bezahlen -> (order_uuid, instance_uuid)."""
    n[0] += 1
    r = c.post("/api/client/orders", json={"product_id": PID, "name": f"srv{n[0]}"}, headers=user_hdr)
    assert r.status_code == 201, r.get_data(as_text=True)
    ou = r.json["uuid"]
    r = c.post(f"/api/admin/orders/{ou}/mark-paid", json={"payment_reference": ref or f"pay-{n[0]}"}, headers=AH)
    assert r.status_code == 200 and r.json["status"] == "active", r.get_data(as_text=True)
    iu = r.json["instance_uuid"]
    with app.app_context():  # Wings meldet die abgeschlossene Installation
        assert report_install(c, iu, True).status_code == 204
    return ou, iu


def order(ou):
    with app.app_context():
        o = Order.query.filter_by(uuid=ou).first()
        return {"status": o.status, "end": o.current_period_end, "past_due_at": o.past_due_at,
                "instance_id": o.instance_id, "cancel": o.cancel_at_period_end, "refs": list(o.payment_references or [])}


def instance(iu):
    with app.app_context():
        i = Instance.query.filter_by(uuid=iu).first()
        return None if i is None else {"status": i.status, "reason": i.suspended_reason, "id": i.id}


def tick(now):
    with app.app_context():
        return run_billing_tick(now=now)


def events(name):
    with app.app_context():
        return ActivityLog.query.filter_by(event=name).count()


check("Standard-Karenzzeit 7 Tage", GRACE == 7)

print("Vor Ablauf passiert nichts")
o1, i1 = paid_order()
end1 = order(o1)["end"]
check("Laufzeit = 30 Tage ab Zahlung", abs((end1 - T0).days - 30) <= 1)
res = tick(T0 + D(days=29))
check("Tick vor Laufzeitende: nichts", res["past_due"] == 0 and res["expired"] == 0 and res["errors"] == [] and res["checked"] >= 1, str(res))
check("Instance unveraendert", instance(i1)["status"] is None)

print("Ablauf -> past_due")
mail.outbox.clear()
runner.calls.clear()
now1 = end1 + D(hours=1)
res = tick(now1)
check("past_due = 1", res["past_due"] == 1 and res["expired"] == 0, str(res))
o = order(o1)
check("Bestellung past_due mit Startzeit der Karenz", o["status"] == "past_due" and o["past_due_at"] == now1, str(o))
ins = instance(i1)
check("Instance suspendiert mit Grund", ins["status"] == "suspended" and ins["reason"] == PAYMENT_SUSPEND_REASON, str(ins))
check("Server wird auf dem Node gestoppt (kill) und Sperre synchronisiert",
      ("power", i1, "kill") in runner.calls and ("sync", i1) in runner.calls, str(runner.calls))
check("Event order:past_due", events("order:past_due") == 1)
check("Mail an den Kunden", len(mail.outbox) == 1 and mail.outbox[0]["to"] == "k1@t.local" and "gesperrt" in mail.outbox[0]["subject"])
res = tick(now1 + D(hours=1))
check("zweiter Tick ist idempotent (keine neue Aktion)", res["past_due"] == 0 and res["expired"] == 0, str(res))
check("keine zweite Mail", len(mail.outbox) == 1)
check("past_due_at bleibt der erste Zeitpunkt", order(o1)["past_due_at"] == now1)
with app.app_context():
    od = Order.query.filter_by(uuid=o1).first().to_dict()
check("API zeigt scheduled_deletion_at = past_due_at + Karenz",
      od["scheduled_deletion_at"] == iso_utc(now1 + D(days=GRACE)), str(od["scheduled_deletion_at"]))

print("Karenzzeit")
res = tick(now1 + D(days=GRACE) - D(minutes=1))
check("kurz vor Ablauf der Karenz: nichts", res["expired"] == 0 and instance(i1) is not None)
runner.calls.clear()
mail.outbox.clear()
res = tick(now1 + D(days=GRACE))
check("nach Karenz: expired = 1", res["expired"] == 1 and res["errors"] == [], str(res))
check("Instance geloescht (Panel + Node)", instance(i1) is None and ("delete_instance", i1) in runner.calls)
o = order(o1)
check("Bestellung expired, von Instance geloest", o["status"] == "expired" and o["instance_id"] is None)
with app.app_context():
    check("Endpoint wieder frei", Endpoint.query.filter(Endpoint.instance_id.isnot(None)).count() == 0)
check("Event order:expired genau einmal", events("order:expired") == 1)
check("Mail zur Loeschung", len(mail.outbox) == 1 and "beendet" in mail.outbox[0]["subject"])
res = tick(now1 + D(days=GRACE + 1))
check("expired Bestellungen werden nicht mehr angefasst", res["checked"] == 0 or (res["expired"] == 0 and res["past_due"] == 0))

print("Tick-Ausfall schuetzt die Karenzzeit")
o2, i2 = paid_order()
late = order(o2)["end"] + D(days=60)
res = tick(late)
check("nach 60 Tagen Ausfall: erst past_due, NICHT sofort expired", res["past_due"] == 1 and res["expired"] == 0, str(res))
check("Instance noch da (gesperrt)", instance(i2)["status"] == "suspended")
res = tick(late + D(days=GRACE))
check("Karenz zaehlt ab past_due_at -> danach expired", res["expired"] == 1 and instance(i2) is None)

print("Verlaengerung")
o3, i3 = paid_order()
end3 = order(o3)["end"]
past = end3 + D(days=2)
tick(past)
check("Vorbedingung: past_due und suspendiert", order(o3)["status"] == "past_due" and instance(i3)["status"] == "suspended")
r = c.post(f"/api/admin/orders/{o3}/mark-paid", headers=AH)
check("Verlaengerung ohne Referenz -> 400", r.status_code == 400 and "payment_reference" in r.json["error"])
check("... und nichts veraendert", order(o3)["status"] == "past_due")
runner.calls.clear()
r = c.post(f"/api/admin/orders/{o3}/mark-paid", json={"payment_reference": "renew-1"}, headers=AH)
check("Verlaengerung -> 200 active", r.status_code == 200 and r.json["status"] == "active", r.get_data(as_text=True)[:200])
o = order(o3)
check("neues Ende zaehlt ab max(jetzt, altes Ende): spaete Zahlung verschenkt keine Zeit",
      o["end"] > datetime.utcnow() + D(days=29) and o["status"] == "active" and o["past_due_at"] is None, str(o))
check("Instance entsperrt", instance(i3)["status"] is None and instance(i3)["reason"] is None)
check("Sperre wird an den Node synchronisiert", ("sync", i3) in runner.calls)
check("Event order:renewed", events("order:renewed") == 1)
end_after = o["end"]
r = c.post(f"/api/admin/orders/{o3}/mark-paid", json={"payment_reference": "renew-1"}, headers=AH)
check("gleiche Referenz nochmal -> No-op", r.status_code == 200 and order(o3)["end"] == end_after and events("order:renewed") == 1)
check("Referenzen gespeichert", order(o3)["refs"] == ["pay-3", "renew-1"], str(order(o3)["refs"]))
r = c.post(f"/api/admin/orders/{o3}/mark-paid", json={"payment_reference": "renew-2"}, headers=AH)
check("Vorauszahlung auf aktive Bestellung: Ende + 30 Tage ab altem Ende",
      r.status_code == 200 and order(o3)["end"] == end_after + D(days=30), str(order(o3)["end"]))
check("Status bleibt active", order(o3)["status"] == "active")

print("Kuendigung zum Laufzeitende")
o4, i4 = paid_order()
check("Kuendigung vormerken", c.post(f"/api/client/orders/{o4}/cancel", headers=U1).json["cancel_at_period_end"] is True)
tick(order(o4)["end"] - D(hours=1))
check("vor Laufzeitende: Server laeuft weiter", instance(i4) is not None and order(o4)["status"] == "active")
with app.app_context():
    od = Order.query.filter_by(uuid=o4).first().to_dict()
check("scheduled_deletion_at = Laufzeitende", od["scheduled_deletion_at"] == iso_utc(order(o4)["end"]))
res = tick(order(o4)["end"] + D(minutes=1))
check("nach Laufzeitende: direkt expired (kein past_due)", res["expired"] == 1 and res["past_due"] == 0 and instance(i4) is None, str(res))
check("Bestellung expired", order(o4)["status"] == "expired")

o5, i5 = paid_order()
past5 = order(o5)["end"] + D(hours=1)
tick(past5)
c.post(f"/api/client/orders/{o5}/cancel", headers=U1)
res = tick(past5 + D(hours=1))
check("Kuendigung nach past_due: naechster Tick beendet sofort (ohne Karenz)", res["expired"] == 1 and instance(i5) is None)

print("Sonderfaelle")
# Admin-Sperre (Missbrauch) darf nicht ueberschrieben werden
o6, i6 = paid_order()
r = c.post(f"/api/admin/instances/{i6}/suspend", json={"reason": "Missbrauch"}, headers=AH)
past6 = order(o6)["end"] + D(hours=1)
runner.calls.clear()
res = tick(past6)
check("Admin-gesperrte Instance: Bestellung wird trotzdem past_due", res["past_due"] == 1 and order(o6)["status"] == "past_due")
check("Admin-Sperre bleibt unveraendert (Grund 'Missbrauch')", instance(i6)["reason"] == "Missbrauch")
check("kein zusaetzlicher kill/sync", not any(call[0] in ("power", "sync") for call in runner.calls), str(runner.calls))
r = c.post(f"/api/admin/orders/{o6}/mark-paid", json={"payment_reference": "renew-x"}, headers=AH)
check("Verlaengerung hebt Admin-Sperre NICHT auf", r.status_code == 200 and instance(i6)["status"] == "suspended" and instance(i6)["reason"] == "Missbrauch")
check("Bestellung trotzdem wieder active", order(o6)["status"] == "active")

# laufende Installation: spaeter erneut
o7, i7 = paid_order()
with app.app_context():
    Instance.query.filter_by(uuid=i7).first().status = "provisioning"
    db.session.commit()
res = tick(order(o7)["end"] + D(hours=1))
check("Instance im Status provisioning: Tick wartet (Bestellung bleibt active)", res["past_due"] == 0 and order(o7)["status"] == "active" and instance(i7)["status"] == "provisioning")
res = tick(order(o7)["end"] + D(days=1, hours=1))
check("haengt die Installation ueber einen Tag: es wird trotzdem gesperrt", res["past_due"] == 1 and instance(i7)["status"] == "suspended")
o7b, i7b = paid_order()
with app.app_context():
    Instance.query.filter_by(uuid=i7b).first().status = "provisioning"
    db.session.commit()
tick(order(o7b)["end"] + D(hours=1))
with app.app_context():
    Instance.query.filter_by(uuid=i7b).first().status = None  # Installation fertig
    db.session.commit()
res = tick(order(o7b)["end"] + D(hours=2))
check("ist die Installation fertig, wird sie beim naechsten Tick ueberfaellig", res["past_due"] == 1 and instance(i7b)["status"] == "suspended")

# Instance fehlt (Daten verloren): expired ohne Runner-Aufruf
o8, i8 = paid_order()
with app.app_context():
    o = Order.query.filter_by(uuid=o8).first()
    o.instance_id = None
    db.session.commit()
runner.calls.clear()
res = tick(order(o8)["end"] + D(hours=1))
check("Instance fehlt -> expired ohne Runner-Aufruf", res["expired"] == 1 and order(o8)["status"] == "expired" and not runner.calls, str(runner.calls))
check("Instance-Daten bleiben unberuehrt (kein Loeschen)", instance(i8) is not None)

# nicht betroffene Status
r = c.post("/api/client/orders", json={"product_id": PID}, headers=U1)
o_pend = r.json["uuid"]
res = tick(T0 + D(days=999))
check("pending_payment wird vom Tick nie angefasst", order(o_pend)["status"] == "pending_payment")

print("Fehler einzelner Bestellungen blockieren nicht")
oa, ia = paid_order()
ob, ib = paid_order()
due = max(order(oa)["end"], order(ob)["end"]) + D(days=60)
tick(due)  # beide past_due
real_delete = None
import app.domain.instances.service as isvc
real_delete = isvc.delete_instance


def flaky_delete(instance, *a, **kw):
    if instance.uuid == ia:
        raise RuntimeError("Datenbank-Hickser")
    return real_delete(instance, *a, **kw)


isvc.delete_instance = flaky_delete
res = tick(due + D(days=GRACE))
isvc.delete_instance = real_delete
check("Fehler wird gemeldet", len(res["errors"]) == 1 and "Hickser" in res["errors"][0]["error"] and res["errors"][0]["order"] == oa, str(res))
check("andere Bestellung wurde trotzdem beendet", order(ob)["status"] == "expired" and instance(ib) is None)
check("fehlerhafte Bestellung unveraendert und Instance noch da", order(oa)["status"] == "past_due" and instance(ia) is not None)
res = tick(due + D(days=GRACE, hours=1))
check("naechster Tick versucht es erneut und schafft es", res["expired"] == 1 and res["errors"] == [] and instance(ia) is None, str(res))

print("Instance manuell geloescht")
oc, ic = paid_order()
r = c.delete(f"/api/admin/instances/{ic}", headers=AH)
check("Admin loescht Instance einer aktiven Bestellung -> 200 (keine FK-Verletzung)", r.status_code == 200, r.get_data(as_text=True)[:150])
check("Bestellung expired und geloest", order(oc)["status"] == "expired" and order(oc)["instance_id"] is None)
with app.app_context():
    ev = ActivityLog.query.filter_by(event="order:expired").order_by(ActivityLog.id.desc()).first()
check("Event nennt Grund instance_deleted", ev is not None and "instance_deleted" in str(ev.properties), str(ev and ev.properties))
od_, id_ = paid_order()
r = c.delete(f"/api/client/instances/{id_}", json={"confirm": f"srv{n[0]}"}, headers=U1)
check("Kunde loescht eigene Instance -> 200, Bestellung expired", r.status_code == 200 and order(od_)["status"] == "expired")
r = c.post(f"/api/admin/orders/{od_}/mark-paid", json={"payment_reference": "spaet"}, headers=AH)
check("expired Bestellung kann nicht verlaengert werden -> 409", r.status_code == 409)

print("Erinnerung vor Laufzeitende")
REM = app.config["BILLING_REMINDER_DAYS"]
check("Standard: 3 Tage", REM == 3)
orr, ir = paid_order()
endr = order(orr)["end"]
mail.outbox.clear()
res = tick(endr - D(days=REM, hours=1))
check("vor dem Erinnerungsfenster: keine Mail", res["reminded"] == 0 and not mail.outbox)
def mails_for(ou):
    return [m for m in mail.outbox if ou in m["body"]]


res = tick(endr - D(days=REM) + D(minutes=1))
check("im Erinnerungsfenster: Mail + Event", res["reminded"] >= 1 and len(mails_for(orr)) == 1 and events("order:reminder") >= 1, str(res))
check("Mail nennt Laufzeitende und Bestellung", mails_for(orr)[0]["to"] == "k1@t.local" and "endet" in mails_for(orr)[0]["subject"])
res = tick(endr - D(days=1))
check("hoechstens einmal pro Periode", len(mails_for(orr)) == 1)
check("Instance bleibt unberuehrt", instance(ir)["status"] is None and order(orr)["status"] == "active")
r = c.post(f"/api/admin/orders/{orr}/mark-paid", json={"payment_reference": "rem-renew"}, headers=AH)
new_end = order(orr)["end"]
res = tick(new_end - D(days=REM) + D(minutes=1))
check("nach Verlaengerung gibt es in der naechsten Periode wieder eine Erinnerung", len(mails_for(orr)) == 2, str(len(mails_for(orr))))
# gekuendigt: keine Erinnerung
ork, ik = paid_order()
c.post(f"/api/client/orders/{ork}/cancel", headers=U1)
res = tick(order(ork)["end"] - D(days=1))
check("gekuendigte Bestellung: statt Erinnerung einmalig 'wird geloescht'-Hinweis",
      len(mails_for(ork)) == 1 and "gelöscht" in mails_for(ork)[0]["subject"] and "endet bald" not in mails_for(ork)[0]["subject"])
with app.app_context():
    ev = ActivityLog.query.filter(ActivityLog.event == "order:reminder").order_by(ActivityLog.id.desc()).first()
check("Event order:reminder mit kind=deletion_notice", "deletion_notice" in str(ev.properties), str(ev.properties))
tick(order(ork)["end"] - D(hours=2))
check("Loeschhinweis nur einmal", len(mails_for(ork)) == 1)
r = c.post(f"/api/admin/orders/{ork}/mark-paid", json={"payment_reference": "cancelled-but-paid"}, headers=AH)
tick(order(ork)["end"] - D(hours=1))
check("nach Verlaengerung gibt es zur neuen Laufzeit wieder einen Hinweis", len(mails_for(ork)) == 2, str(len(mails_for(ork))))
# Erinnerung abschaltbar
app.config["BILLING_REMINDER_DAYS"] = 0
orz, iz2 = paid_order()
res = tick(order(orz)["end"] - D(hours=1))
check("BILLING_REMINDER_DAYS=0 schaltet die Erinnerung ab", len(mails_for(orz)) == 0)
app.config["BILLING_REMINDER_DAYS"] = REM
# ueberfaellige Bestellungen bekommen keine Erinnerung mehr, sondern die past_due-Mail
orp, ip_ = paid_order()
tick(order(orp)["end"] + D(hours=1))
check("nach Ablauf: past_due statt Erinnerung", order(orp)["status"] == "past_due"
      and all("endet bald" not in m["subject"] for m in mails_for(orp)))
# kurze Laufzeit (<= Erinnerungsfenster): keine Erinnerung direkt nach dem Kauf
r = c.post("/api/admin/products", json={"name": "Kurz", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50,
                                         "price_cents": 100, "billing_period_days": 2}, headers=AH)
short_pid = r.json["id"]
rr = c.post("/api/client/orders", json={"product_id": short_pid}, headers=U1).json["uuid"]
c.post(f"/api/admin/orders/{rr}/mark-paid", json={"payment_reference": "short-1"}, headers=AH)
res = tick(datetime.utcnow() + D(hours=1))
check("Laufzeit kuerzer als Erinnerungsfenster: keine Erinnerung", len(mails_for(rr)) == 0)

print("Kostenlose Pakete laufen weiter")
r = c.post("/api/admin/products", json={"name": "Gratis", "blueprint_id": ids["bp"], "memory": 256, "disk": 500, "cpu": 50,
                                         "price_cents": 0, "max_instances_per_user": 3, "billing_period_days": 30}, headers=AH)
free_pid = r.json["id"]
r = c.post("/api/client/orders", json={"product_id": free_pid, "name": "gratis1"}, headers=U1)
ofree = r.json["uuid"]
ifree = r.json["instance_uuid"]
with app.app_context():
    report_install(c, ifree, True)
endf = order(ofree)["end"]
mail.outbox.clear()
res = tick(endf + D(hours=1))
check("Ablauf: automatisch verlaengert (renewed)", res["renewed"] >= 1, str(res))
o = order(ofree)
check("Status active, Instance laeuft, neues Ende ca. 30 Tage", o["status"] == "active" and instance(ifree)["status"] is None
      and o["end"] > endf + D(days=29), str(o))
check("keine Mail an den Kunden bei Gratis-Verlaengerung", len(mails_for(ofree)) == 0)
check("Referenz free-auto vermerkt", any(x.startswith("free-auto:") for x in o["refs"]), str(o["refs"]))
o_before = order(ofree)
tick(endf + D(hours=2))
check("zweiter Tick: nichts mehr (idempotent)", order(ofree)["end"] == o_before["end"] and order(ofree)["refs"] == o_before["refs"])
check("Event order:renewed", events("order:renewed") >= 2)
c.post(f"/api/client/orders/{ofree}/cancel", headers=U1)
tick(order(ofree)["end"] + D(hours=1))
check("gekuendigtes Gratis-Paket laeuft zum Laufzeitende aus", instance(ifree) is None and order(ofree)["status"] == "expired")

print("Konfiguration")
app.config["BILLING_GRACE_DAYS"] = 0
oz, iz = paid_order()
pz = order(oz)["end"] + D(hours=1)
tick(pz)
res = tick(pz)
check("Karenz 0 Tage: naechster Tick loescht sofort", res["expired"] == 1 and instance(iz) is None)
app.config["BILLING_GRACE_DAYS"] = GRACE

print("CLI billing-tick")
with tempfile.TemporaryDirectory() as tmp:
    db_url = f"sqlite:///{tmp}/t.db"
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": db_url, "RUNNER_ADAPTER": "stub"}
    subprocess.run([sys.executable, "-c",
                    "from app import create_app;from app.extensions import db;a=create_app();\n"
                    "with a.app_context(): db.create_all()"], env=env, capture_output=True, check=True,
                   cwd=os.path.dirname(__file__))
    out = subprocess.run([sys.executable, "cli.py", "billing-tick"], env=env, capture_output=True, text=True,
                         cwd=os.path.dirname(__file__))
    line = [l for l in out.stdout.splitlines() if l.startswith("{")]
    summary = json.loads(line[-1]) if line else {}
check("CLI: Exit 0 und JSON-Zusammenfassung", out.returncode == 0 and summary == {"checked": 0, "past_due": 0, "expired": 0, "reminded": 0, "renewed": 0, "provisioned": 0, "errors": []},
      out.stdout[-200:] + out.stderr[-200:])

print(f"\n{passed} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
