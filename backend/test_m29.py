"""Tests fuer Meilenstein 29 – Suspension / Unsuspend & Administrative Instance Locks.

Deckt ab:
a) Suspension-Service (suspend, unsuspend, Idempotenz)
b) Admin-API (/suspend, /unsuspend, Auth-Schutz)
c) Zugriffssperre (Power, File-Write, Backup, DB, Routine, WebSocket)
d) Status-/Konsistenzregeln
e) Activity / Webhooks
f) Regression (M10-M28 Kompatibilitaet)
"""

import sys
import os
import json
import struct
import base64

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  OK  {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {label}" + (f" – {detail}" if detail else ""))


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


app = create_app("testing")
client = app.test_client()

_user_id = None
_admin_id = None
_agent_id = None
_bp_id = None
_ep_id = None
_inst_id = None
_inst_uuid = None


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner, STATUS_READY
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    user = User(username="m29-user", email="m29@test.dev")
    user.set_password("testpass")
    db.session.add(user)

    admin = User(username="m29-admin", email="m29admin@test.dev", is_admin=True)
    admin.set_password("adminpass")
    db.session.add(admin)

    db.session.flush()

    agent = Agent(name="m29-agent", fqdn="m29.test.dev", is_active=True)
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m29-bp")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=29000)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m29-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status=STATUS_READY,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    _user_id = user.id
    _admin_id = admin.id
    _agent_id = agent.id
    _bp_id = bp.id
    _ep_id = ep.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid


# ================================================================
# a) Suspension-Service
# ================================================================

print("\n=== a) Suspension-Service ===")

with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import (
        suspend_instance, unsuspend_instance, is_instance_suspended,
        STATUS_SUSPENDED, STATUS_READY,
    )

    inst = db.session.get(Instance, _inst_id)
    check("Instance ist initial nicht suspendiert", not is_instance_suspended(inst))

    # Suspend
    inst = suspend_instance(inst, _admin_id, reason="Zahlungsrueckstand")
    check("Status nach suspend = 'suspended'", inst.status == STATUS_SUSPENDED)
    check("is_instance_suspended = True", is_instance_suspended(inst))
    check("suspended_reason gespeichert", inst.suspended_reason == "Zahlungsrueckstand")
    check("suspended_at gesetzt", inst.suspended_at is not None)
    check("suspended_by_user_id gesetzt", inst.suspended_by_user_id == _admin_id)

    # to_dict enthaelt Suspension-Felder
    d = inst.to_dict()
    check("to_dict hat suspended_reason", d["suspended_reason"] == "Zahlungsrueckstand")
    check("to_dict hat suspended_at", d["suspended_at"] is not None)
    check("to_dict hat suspended_by_user_id", d["suspended_by_user_id"] == _admin_id)

    # Idempotentes Suspend (erneutes Suspend aktualisiert Grund)
    inst = suspend_instance(inst, _admin_id, reason="Neuer Grund")
    check("Idempotentes Suspend: Status bleibt suspended", inst.status == STATUS_SUSPENDED)
    check("Idempotentes Suspend: Grund aktualisiert", inst.suspended_reason == "Neuer Grund")

    # Unsuspend
    inst = unsuspend_instance(inst, _admin_id)
    check("Status nach unsuspend = ready (None)", inst.status == STATUS_READY)
    check("is_instance_suspended = False nach unsuspend", not is_instance_suspended(inst))
    check("suspended_reason geleert", inst.suspended_reason is None)
    check("suspended_at geleert", inst.suspended_at is None)
    check("suspended_by_user_id geleert", inst.suspended_by_user_id is None)

    # Idempotentes Unsuspend (auf bereits unsuspendierter Instance)
    inst = unsuspend_instance(inst, _admin_id)
    check("Idempotentes Unsuspend: Status bleibt ready", inst.status == STATUS_READY)

    # Suspend ohne Grund
    inst = suspend_instance(inst, _admin_id, reason=None)
    check("Suspend ohne Grund: reason = None", inst.suspended_reason is None)
    check("Suspend ohne Grund: Status = suspended", inst.status == STATUS_SUSPENDED)

    # Wieder freigeben fuer naechste Tests
    inst = unsuspend_instance(inst, _admin_id)
    db.session.commit()


# ================================================================
# b) Admin-API
# ================================================================

print("\n=== b) Admin-API ===")

# Suspend ohne Auth -> 401
resp = client.post(f"/api/admin/instances/{_inst_uuid}/suspend")
check("POST /suspend ohne Auth -> 401", resp.status_code == 401)

# Unsuspend ohne Auth -> 401
resp = client.post(f"/api/admin/instances/{_inst_uuid}/unsuspend")
check("POST /unsuspend ohne Auth -> 401", resp.status_code == 401)

# Suspend durch Nicht-Admin -> 403
resp = client.post(
    f"/api/admin/instances/{_inst_uuid}/suspend",
    content_type="application/json",
    data=json.dumps({"reason": "Test"}),
    headers={"X-User-Id": str(_user_id)},
)
check("POST /suspend durch Nicht-Admin -> 403", resp.status_code == 403)

# Suspend durch Admin -> 200
with app.app_context():
    from app.domain.auth.service import issue_access_token
    from app.domain.users.models import User
    admin_obj = db.session.get(User, _admin_id)
    admin_token = issue_access_token(admin_obj)

resp = client.post(
    f"/api/admin/instances/{_inst_uuid}/suspend",
    content_type="application/json",
    data=json.dumps({"reason": "API-Test"}),
    headers={"Authorization": f"Bearer {admin_token}"},
)
check("POST /suspend durch Admin -> 200", resp.status_code == 200)
data = resp.get_json()
check("Suspend Response hat message", "message" in data)
check("Suspend Response hat instance", "instance" in data)
check("Instance status = suspended", data["instance"]["status"] == "suspended")
check("Suspend reason gesetzt", data["instance"]["suspended_reason"] == "API-Test")

# Unsuspend durch Admin -> 200
resp = client.post(
    f"/api/admin/instances/{_inst_uuid}/unsuspend",
    headers={"Authorization": f"Bearer {admin_token}"},
)
check("POST /unsuspend durch Admin -> 200", resp.status_code == 200)
data = resp.get_json()
check("Unsuspend Response hat instance", "instance" in data)
check("Instance status nach unsuspend = None (ready)", data["instance"]["status"] is None)

# Nicht vorhandene Instance -> 404
resp = client.post(
    "/api/admin/instances/00000000-0000-0000-0000-000000000000/suspend",
    headers={"Authorization": f"Bearer {admin_token}"},
)
check("POST /suspend unbekannte Instance -> 404", resp.status_code == 404)


# ================================================================
# c) Zugriffssperre
# ================================================================

print("\n=== c) Zugriffssperre ===")

# Instance suspendieren
with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import suspend_instance
    inst = db.session.get(Instance, _inst_id)
    suspend_instance(inst, _admin_id, reason="Sperrtest")

# Power-Aktionen -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/power",
    content_type="application/json",
    data=json.dumps({"signal": "start"}),
    headers={"X-User-Id": str(_user_id)},
)
check("Power-Aktion auf suspendierter Instance -> 409", resp.status_code == 409)
check("Fehlermeldung enthaelt 'suspendiert'", "suspendiert" in (resp.get_json() or {}).get("error", "").lower())

# Reinstall -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/reinstall",
    headers={"X-User-Id": str(_user_id)},
)
check("Reinstall auf suspendierter Instance -> 409", resp.status_code == 409)

# Build-Update -> 409
resp = client.patch(
    f"/api/client/instances/{_inst_uuid}/build",
    content_type="application/json",
    data=json.dumps({"memory": 1024}),
    headers={"X-User-Id": str(_user_id)},
)
check("Build-Update auf suspendierter Instance -> 409", resp.status_code == 409)

# Variable-Update -> 409
resp = client.patch(
    f"/api/client/instances/{_inst_uuid}/variables",
    content_type="application/json",
    data=json.dumps({"SOME_VAR": "value"}),
    headers={"X-User-Id": str(_user_id)},
)
check("Variable-Update auf suspendierter Instance -> 409", resp.status_code == 409)

# Sync -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/sync",
    headers={"X-User-Id": str(_user_id)},
)
check("Sync auf suspendierter Instance -> 409", resp.status_code == 409)

# WebSocket -> 409
resp = client.get(
    f"/api/client/instances/{_inst_uuid}/websocket",
    headers={"X-User-Id": str(_user_id)},
)
check("WebSocket auf suspendierter Instance -> 409", resp.status_code == 409)

# File-Write -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/files/write",
    content_type="application/json",
    data=json.dumps({"path": "/test.txt", "content": "hello"}),
    headers={"X-User-Id": str(_user_id)},
)
check("File-Write auf suspendierter Instance -> 409", resp.status_code == 409)

# File-Delete -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/files/delete",
    content_type="application/json",
    data=json.dumps({"path": "/test.txt"}),
    headers={"X-User-Id": str(_user_id)},
)
check("File-Delete auf suspendierter Instance -> 409", resp.status_code == 409)

# Backup-Create -> 409
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/backups",
    content_type="application/json",
    data=json.dumps({"name": "test-backup"}),
    headers={"X-User-Id": str(_user_id)},
)
check("Backup-Create auf suspendierter Instance -> 409", resp.status_code == 409)

# Routine-Execute -> 409 (Routine muss nicht existieren – Sperre kommt zuerst)
resp = client.post(
    f"/api/client/instances/{_inst_uuid}/routines/9999/execute",
    headers={"X-User-Id": str(_user_id)},
)
check("Routine-Execute auf suspendierter Instance -> 409", resp.status_code == 409)

# Lesender Zugriff bleibt erlaubt
resp = client.get(
    f"/api/client/instances/{_inst_uuid}",
    headers={"X-User-Id": str(_user_id)},
)
check("GET Instance-Detail auf suspendierter Instance -> 200", resp.status_code == 200)
check("Response zeigt status = suspended", resp.get_json().get("status") == "suspended")

resp = client.get(
    f"/api/client/instances/{_inst_uuid}/activity",
    headers={"X-User-Id": str(_user_id)},
)
check("Activity-Log auf suspendierter Instance -> 200", resp.status_code == 200)

# Instance wieder freigeben
with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import unsuspend_instance
    inst = db.session.get(Instance, _inst_id)
    unsuspend_instance(inst, _admin_id)


# ================================================================
# d) Status-/Konsistenzregeln
# ================================================================

print("\n=== d) Konsistenzregeln ===")

with app.app_context():
    from app.domain.instances.models import Instance
    from app.domain.instances.service import (
        suspend_instance, unsuspend_instance,
        update_container_status, STATUS_SUSPENDED,
    )

    inst = db.session.get(Instance, _inst_id)

    # container_state bleibt unabhaengig von Suspension
    inst.container_state = "running"
    db.session.commit()

    inst = suspend_instance(inst, _admin_id)
    check("Suspension aendert container_state nicht", inst.container_state == "running")
    check("container_state und status sind unabhaengig", inst.status == STATUS_SUSPENDED and inst.container_state == "running")

    # container_state-Update bei suspendierter Instance bleibt moeglich
    inst = update_container_status(inst, "stopped")
    check("container_state-Update bei suspendierter Instance moeglich", inst.container_state == "stopped")
    check("Suspension bleibt nach container_state-Update erhalten", inst.status == STATUS_SUSPENDED)

    # Unsuspend setzt keinen falschen container_state
    inst = unsuspend_instance(inst, _admin_id)
    check("Unsuspend setzt container_state nicht zurueck", inst.container_state == "stopped")
    check("Status nach unsuspend = None (ready)", inst.status is None)


# ================================================================
# e) Activity / Webhooks
# ================================================================

print("\n=== e) Activity / Webhooks ===")

with app.app_context():
    from app.domain.activity.events import INSTANCE_SUSPENDED, INSTANCE_UNSUSPENDED
    check("INSTANCE_SUSPENDED Event definiert", INSTANCE_SUSPENDED == "instance:suspended")
    check("INSTANCE_UNSUSPENDED Event definiert", INSTANCE_UNSUSPENDED == "instance:unsuspended")

    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS, get_event_catalog
    check("instance:suspended im Webhook-Katalog", "instance:suspended" in WEBHOOK_EVENTS)
    check("instance:unsuspended im Webhook-Katalog", "instance:unsuspended" in WEBHOOK_EVENTS)

    catalog = [e["event"] for e in get_event_catalog()]
    check("Katalog enthaelt instance:suspended", "instance:suspended" in catalog)
    check("Katalog enthaelt instance:unsuspended", "instance:unsuspended" in catalog)

    from app.domain.activity.models import ActivityLog
    from app.domain.instances.models import Instance
    from app.domain.instances.service import suspend_instance, unsuspend_instance

    inst = db.session.get(Instance, _inst_id)

    cnt_sus_before = ActivityLog.query.filter_by(event="instance:suspended").count()
    inst = suspend_instance(inst, _admin_id, reason="Event-Test")
    cnt_sus_after = ActivityLog.query.filter_by(event="instance:suspended").count()
    check("instance:suspended Activity-Event wird erzeugt", cnt_sus_after == cnt_sus_before + 1)

    cnt_uns_before = ActivityLog.query.filter_by(event="instance:unsuspended").count()
    inst = unsuspend_instance(inst, _admin_id)
    cnt_uns_after = ActivityLog.query.filter_by(event="instance:unsuspended").count()
    check("instance:unsuspended Activity-Event wird erzeugt", cnt_uns_after == cnt_uns_before + 1)


# ================================================================
# f) Regression
# ================================================================

print("\n=== f) Regression ===")

resp = client.get("/api/auth/health")
check("GET /api/auth/health -> 200", resp.status_code == 200)

resp = client.get("/api/admin/health")
check("GET /api/admin/health -> 200", resp.status_code == 200)

resp = client.get("/api/admin/instances", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/instances -> 200", resp.status_code == 200)

resp = client.get("/api/admin/agents", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/agents -> 200", resp.status_code == 200)

resp = client.get("/api/admin/webhooks", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/webhooks -> 200", resp.status_code == 200)

resp = client.get("/api/client/instances", headers={"X-User-Id": str(_user_id)})
check("GET /api/client/instances -> 200", resp.status_code == 200)

resp = client.get("/api/client/account/ssh-keys", headers={"X-User-Id": str(_user_id)})
check("GET /api/client/account/ssh-keys -> 200 (M28)", resp.status_code == 200)

# Webhook-Katalog: bisherige Events unveraendert vorhanden
with app.app_context():
    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS
    for event in [
        "instance:created", "backup:created", "database:created",
        "collaborator:added", "routine:created", "agent:maintenance_enabled",
        "ssh_key:created",
    ]:
        check(f"Webhook-Katalog: {event} noch vorhanden", event in WEBHOOK_EVENTS)

# Instance-Lifecycle-Konstanten unveraendert
with app.app_context():
    from app.domain.instances.service import (
        STATUS_PROVISIONING, STATUS_PROVISION_FAILED, STATUS_REINSTALLING,
        STATUS_REINSTALL_FAILED, STATUS_RESTORING, STATUS_SUSPENDED,
        STATUS_TRANSFERRING, STATUS_TRANSFER_FAILED, STATUS_READY,
    )
    check("STATUS_SUSPENDED = 'suspended'", STATUS_SUSPENDED == "suspended")
    check("STATUS_READY = None", STATUS_READY is None)
    check("STATUS_PROVISIONING = 'provisioning'", STATUS_PROVISIONING == "provisioning")


# ================================================================
# Ergebnis
# ================================================================

print(f"\n{'='*50}")
print(f"  Gesamt: {passed + failed} Tests | {passed} bestanden | {failed} fehlgeschlagen")
print(f"{'='*50}")

if failed > 0:
    sys.exit(1)
