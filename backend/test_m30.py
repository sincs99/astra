"""Tests fuer Meilenstein 30 – Echte SFTP-/SSH-Key-Authentifizierung.

Deckt ab:
a) SSH-Key-Matching (find_key_by_fingerprint, find_user_key)
b) Auth-Service (authorize_ssh_key_access – alle Deny/Allow-Pfade)
c) Agent-/SFTP-API (POST /agent/sftp-auth)
d) Security / Serialization
e) Activity / Webhooks (Event-Katalog)
f) Regression (M10–M29, bestehende Endpoints, file.sftp als valide Permission)
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


# ── Synthethische SSH-Keys ────────────────────────────────


def _make_ed25519_public_key(seed: bytes = b"\x01" * 32) -> str:
    """Erzeugt einen synthetischen ssh-ed25519 Public Key im SSH-Wire-Format."""
    key_type = b"ssh-ed25519"
    body = struct.pack(">I", len(key_type)) + key_type
    body += struct.pack(">I", len(seed)) + seed
    b64 = base64.b64encode(body).decode("ascii")
    return f"ssh-ed25519 {b64} test-key"


def _make_ed25519_public_key_2(seed: bytes = b"\x02" * 32) -> str:
    return _make_ed25519_public_key(seed)


def _make_ed25519_public_key_3(seed: bytes = b"\x03" * 32) -> str:
    return _make_ed25519_public_key(seed)


KEY_OWNER = _make_ed25519_public_key(b"\x10" * 32)
KEY_COLLAB = _make_ed25519_public_key(b"\x20" * 32)
KEY_STRANGER = _make_ed25519_public_key(b"\x30" * 32)

app = create_app("testing")
client = app.test_client()

_owner_id = None
_collab_id = None
_admin_id = None
_agent_id = None
_bp_id = None
_ep_id = None
_inst_id = None
_inst_uuid = None
_owner_key_id = None
_collab_key_id = None
_owner_fingerprint = None
_collab_fingerprint = None


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
    from app.domain.collaborators.models import Collaborator
    from app.domain.ssh_keys.models import UserSshKey
    from app.domain.ssh_keys.validator import compute_fingerprint
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    owner = User(username="m30-owner", email="m30owner@test.dev")
    owner.set_password("ownerpass")
    db.session.add(owner)

    collab = User(username="m30-collab", email="m30collab@test.dev")
    collab.set_password("collabpass")
    db.session.add(collab)

    admin = User(username="m30-admin", email="m30admin@test.dev", is_admin=True)
    admin.set_password("adminpass")
    db.session.add(admin)

    db.session.flush()

    agent = Agent(name="m30-agent", fqdn="m30.test.dev", is_active=True)
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m30-bp")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=30000)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m30-instance",
        owner_id=owner.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status=STATUS_READY,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    # SSH-Keys anlegen
    fp_owner = compute_fingerprint(KEY_OWNER)
    fp_collab = compute_fingerprint(KEY_COLLAB)

    owner_key = UserSshKey(
        user_id=owner.id,
        name="m30-owner-key",
        fingerprint=fp_owner,
        public_key=KEY_OWNER,
    )
    collab_key = UserSshKey(
        user_id=collab.id,
        name="m30-collab-key",
        fingerprint=fp_collab,
        public_key=KEY_COLLAB,
    )
    db.session.add_all([owner_key, collab_key])
    db.session.flush()

    # Collaborator mit file.sftp
    collab_entry = Collaborator(
        user_id=collab.id,
        instance_id=inst.id,
        permissions=["file.sftp", "file.read"],
    )
    db.session.add(collab_entry)
    db.session.commit()

    _owner_id = owner.id
    _collab_id = collab.id
    _admin_id = admin.id
    _agent_id = agent.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid
    _owner_key_id = owner_key.id
    _collab_key_id = collab_key.id
    _owner_fingerprint = fp_owner
    _collab_fingerprint = fp_collab


# ================================================================
# a) SSH-Key-Matching
# ================================================================

print("\n=== a) SSH-Key-Matching ===")

with app.app_context():
    from app.domain.ssh_keys.auth_service import (
        find_key_by_fingerprint,
        find_key_by_public_key,
        find_user_key,
    )

    # Fingerprint-Matching – bekannter Key
    key = find_key_by_fingerprint(_owner_id, _owner_fingerprint)
    check("find_key_by_fingerprint: bekannter Key gefunden", key is not None)
    check("find_key_by_fingerprint: korrekte Key-ID", key is not None and key.id == _owner_key_id)

    # Fingerprint-Matching – unbekannter Fingerprint
    key = find_key_by_fingerprint(_owner_id, "SHA256:doesnotexist")
    check("find_key_by_fingerprint: unbekannter Fingerprint -> None", key is None)

    # Fingerprint-Matching – falscher User
    key = find_key_by_fingerprint(_collab_id, _owner_fingerprint)
    check("find_key_by_fingerprint: Key gehoert anderem User -> None", key is None)

    # Public-Key-Matching – exakter Key
    key = find_key_by_public_key(_owner_id, KEY_OWNER)
    check("find_key_by_public_key: bekannter Key gefunden", key is not None)

    # Public-Key-Matching – unbekannter Key
    key = find_key_by_public_key(_owner_id, KEY_STRANGER)
    check("find_key_by_public_key: unbekannter Key -> None", key is None)

    # find_user_key mit public_key (bevorzugt – Fingerprint wird serverseitig berechnet)
    key = find_user_key(_owner_id, public_key=KEY_OWNER)
    check("find_user_key mit public_key: gefunden", key is not None)

    # find_user_key mit fingerprint (Fallback)
    key = find_user_key(_owner_id, fingerprint=_owner_fingerprint)
    check("find_user_key mit fingerprint: gefunden", key is not None)

    # find_user_key mit ungueltigem public_key
    key = find_user_key(_owner_id, public_key="kein-gueltiger-key")
    check("find_user_key mit ungueltigem public_key -> None", key is None)

    # find_user_key ohne Key-Angabe
    key = find_user_key(_owner_id)
    check("find_user_key ohne Angabe -> None", key is None)


# ================================================================
# b) Auth-Service
# ================================================================

print("\n=== b) Auth-Service ===")

with app.app_context():
    from app.domain.ssh_keys.auth_service import (
        authorize_ssh_key_access,
        REASON_OK,
        REASON_USER_UNKNOWN,
        REASON_INSTANCE_NOT_FOUND,
        REASON_KEY_UNKNOWN,
        REASON_PERMISSION_DENIED,
        REASON_INSTANCE_SUSPENDED,
        REASON_MALFORMED,
    )
    from app.domain.instances.models import Instance
    from app.domain.instances.service import suspend_instance, unsuspend_instance

    # ── Owner mit gueltigem Key ─────────────────────────
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        public_key=KEY_OWNER,
    )
    check("Owner mit gueltigem Key -> allowed=True", result.allowed)
    check("Owner: reason=ok", result.reason == REASON_OK)
    check("Owner: username zurueck", result.username == "m30-owner")
    check("Owner: instance_uuid zurueck", result.instance_uuid == _inst_uuid)
    check("Owner: permissions nicht leer", len(result.permissions) > 0)

    # Owner mit Fingerprint statt Public Key
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        fingerprint=_owner_fingerprint,
    )
    check("Owner mit Fingerprint -> allowed=True", result.allowed)

    # ── Collaborator mit file.sftp ──────────────────────
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-collab",
        public_key=KEY_COLLAB,
    )
    check("Collaborator mit file.sftp -> allowed=True", result.allowed)
    check("Collaborator: reason=ok", result.reason == REASON_OK)
    check("Collaborator: permissions enthalten file.sftp", "file.sftp" in result.permissions)

    # ── Collaborator ohne file.sftp ─────────────────────
    # Berechtigung temporaer entfernen
    inst = db.session.get(Instance, _inst_id)
    from app.domain.collaborators.models import Collaborator
    collab_entry = Collaborator.query.filter_by(
        user_id=_collab_id, instance_id=_inst_id
    ).first()
    collab_entry.permissions = ["file.read"]
    db.session.commit()

    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-collab",
        public_key=KEY_COLLAB,
    )
    check("Collaborator ohne file.sftp -> allowed=False", not result.allowed)
    check("Collaborator ohne file.sftp: reason=permission_denied", result.reason == REASON_PERMISSION_DENIED)

    # Berechtigung wiederherstellen
    collab_entry.permissions = ["file.sftp", "file.read"]
    db.session.commit()

    # ── Suspendierte Instance ───────────────────────────
    inst = db.session.get(Instance, _inst_id)
    inst = suspend_instance(inst, _admin_id, reason="Test-Suspension")
    db.session.commit()

    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        public_key=KEY_OWNER,
    )
    check("Suspendierte Instance -> allowed=False", not result.allowed)
    check("Suspendierte Instance: reason=instance_suspended", result.reason == REASON_INSTANCE_SUSPENDED)

    # Auch Collaborator blockiert
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-collab",
        public_key=KEY_COLLAB,
    )
    check("Suspendierte Instance: Collaborator ebenfalls blockiert", not result.allowed)
    check("Suspendierte Instance: Collaborator reason=instance_suspended", result.reason == REASON_INSTANCE_SUSPENDED)

    # Suspension aufheben
    inst = unsuspend_instance(inst, _admin_id)
    db.session.commit()

    # ── Unbekannter User ────────────────────────────────
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="nicht-vorhanden",
        public_key=KEY_OWNER,
    )
    check("Unbekannter User -> allowed=False", not result.allowed)
    check("Unbekannter User: reason=user_unknown", result.reason == REASON_USER_UNKNOWN)

    # ── Unbekannte Instance ─────────────────────────────
    result = authorize_ssh_key_access(
        instance_uuid="00000000-0000-0000-0000-000000000000",
        username="m30-owner",
        public_key=KEY_OWNER,
    )
    check("Unbekannte Instance -> allowed=False", not result.allowed)
    check("Unbekannte Instance: reason=instance_not_found", result.reason == REASON_INSTANCE_NOT_FOUND)

    # ── Unbekannter Key ─────────────────────────────────
    result = authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        public_key=KEY_STRANGER,
    )
    check("Unbekannter Key -> allowed=False", not result.allowed)
    check("Unbekannter Key: reason=key_unknown", result.reason == REASON_KEY_UNKNOWN)

    # ── Malformed Requests ──────────────────────────────
    result = authorize_ssh_key_access(instance_uuid=_inst_uuid, username="", public_key=KEY_OWNER)
    check("Leerer Username -> reason=malformed_request", result.reason == REASON_MALFORMED)

    result = authorize_ssh_key_access(instance_uuid="", username="m30-owner", public_key=KEY_OWNER)
    check("Leere UUID -> reason=malformed_request", result.reason == REASON_MALFORMED)

    result = authorize_ssh_key_access(instance_uuid=_inst_uuid, username="m30-owner")
    check("Kein Key/Fingerprint -> reason=malformed_request", result.reason == REASON_MALFORMED)


# ================================================================
# c) Remote-SFTP-API (POST /api/remote/sftp/auth, Wings-Format)
# ================================================================

print("\n=== c) Remote-SFTP-API ===")


def sftp_auth(body):
    """POST /api/remote/sftp/auth mit Node-Token der Instance (Wings-Format)."""
    with app.app_context():
        return client.post(
            "/api/remote/sftp/auth",
            json=body,
            headers=node_headers_for_instance(_inst_uuid),
        )


def sftp_pubkey(username, uuid, key):
    return sftp_auth({"type": "public_key", "username": f"{username}.{uuid}", "password": key})


from test_helpers import node_headers_for_instance, report_container_state

# Gueltige Anfrage mit Public Key -> 200
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_OWNER)
check("POST /remote/sftp/auth gueltig (Owner) -> 200", resp.status_code == 200)
body = json.loads(resp.data)
check("Response: server = instance uuid", body.get("server") == _inst_uuid)
check("Response: user vorhanden", bool(body.get("user")))
check("Response: permissions liste", isinstance(body.get("permissions"), list) and body["permissions"])

# Collaborator mit file.sftp
resp = sftp_pubkey("m30-collab", _inst_uuid, KEY_COLLAB)
check("POST /remote/sftp/auth Collaborator -> 200", resp.status_code == 200)

# Unbekannter User -> 403
resp = sftp_pubkey("fantasie-user", _inst_uuid, KEY_OWNER)
check("POST /remote/sftp/auth unbekannter User -> 403", resp.status_code == 403)

# Unbekannter Key -> 403
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_STRANGER)
check("POST /remote/sftp/auth unbekannter Key -> 403", resp.status_code == 403)

# Fremder Key eines anderen Users -> 403
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_COLLAB)
check("POST /remote/sftp/auth Key eines anderen Users -> 403", resp.status_code == 403)

# Fehlender username -> 400
resp = sftp_auth({"type": "public_key", "password": KEY_OWNER})
check("POST /remote/sftp/auth ohne username -> 400", resp.status_code == 400)

# Username ohne Server-Kennung -> 400
resp = sftp_auth({"type": "public_key", "username": "m30-owner", "password": KEY_OWNER})
check("POST /remote/sftp/auth ohne Server-Kennung -> 400", resp.status_code == 400)

# Ohne Key/Passwort -> 400
resp = sftp_auth({"type": "public_key", "username": f"m30-owner.{_inst_uuid}"})
check("POST /remote/sftp/auth ohne Key -> 400", resp.status_code == 400)

# Leerer JSON Body -> 400
resp = sftp_auth({})
check("POST /remote/sftp/auth leerer JSON -> 400", resp.status_code == 400)

# Ohne Node-Token -> 401
resp = client.post("/api/remote/sftp/auth", json={"type": "public_key",
                   "username": f"m30-owner.{_inst_uuid}", "password": KEY_OWNER})
check("POST /remote/sftp/auth ohne Node-Token -> 401", resp.status_code == 401)


# ================================================================
# d) Security / Serialization
# ================================================================

print("\n=== d) Security / Serialization ===")

# Keine Secrets im Response bei Erfolg
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_OWNER)
body = json.loads(resp.data)
check("Response bei Erfolg hat kein 'public_key'-Feld", "public_key" not in body)
check("Response bei Erfolg hat kein 'password_hash'-Feld", "password_hash" not in body)
check("Response bei Erfolg hat kein 'mfa_secret'-Feld", "mfa_secret" not in body)

# Kein Key / interne Details im Deny-Response
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_STRANGER)
body = json.loads(resp.data)
check("Deny-Response enthaelt den Key nicht", KEY_STRANGER not in resp.get_data(as_text=True))
check("Deny-Response hat kein 'user_id'-Feld (kein internes Leaken)", "user_id" not in body)

# Keine Stack-Traces oder Exception-Details
resp = sftp_pubkey("m30-owner", "ungueltig-kein-uuid", KEY_OWNER)
body = json.loads(resp.data)
check("Ungueltige UUID -> 403", resp.status_code == 403)
check("Ungueltige UUID: kein traceback im Response", "traceback" not in str(body).lower())
check("Ungueltige UUID: kein 'exception' im Response", "exception" not in str(body).lower())

# Valider Key wird via Fingerprint verglichen (nicht plain-text Key-Vergleich im Log)
with app.app_context():
    from app.domain.ssh_keys.auth_service import find_user_key
    from app.domain.ssh_keys.validator import compute_fingerprint
    fp = compute_fingerprint(KEY_OWNER)
    # find_user_key mit public_key berechnet FP serverseitig
    key_via_pk = find_user_key(_owner_id, public_key=KEY_OWNER)
    key_via_fp = find_user_key(_owner_id, fingerprint=fp)
    check("find_user_key via public_key = via fingerprint (selber Key)",
          key_via_pk is not None and key_via_fp is not None and key_via_pk.id == key_via_fp.id)


# ================================================================
# e) Activity / Webhooks
# ================================================================

print("\n=== e) Activity / Webhooks ===")

with app.app_context():
    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS, is_valid_webhook_event

    check("ssh_key:auth_success im Webhook-Katalog", is_valid_webhook_event("ssh_key:auth_success"))
    check("ssh_key:auth_failed im Webhook-Katalog", is_valid_webhook_event("ssh_key:auth_failed"))

    from app.domain.activity.events import SSH_KEY_AUTH_SUCCESS, SSH_KEY_AUTH_FAILED
    check("SSH_KEY_AUTH_SUCCESS = 'ssh_key:auth_success'", SSH_KEY_AUTH_SUCCESS == "ssh_key:auth_success")
    check("SSH_KEY_AUTH_FAILED  = 'ssh_key:auth_failed'", SSH_KEY_AUTH_FAILED == "ssh_key:auth_failed")
    check("SSH_KEY_AUTH_SUCCESS in WEBHOOK_EVENTS", SSH_KEY_AUTH_SUCCESS in WEBHOOK_EVENTS)
    check("SSH_KEY_AUTH_FAILED  in WEBHOOK_EVENTS", SSH_KEY_AUTH_FAILED in WEBHOOK_EVENTS)

    # Auth-Event wird nach erfolgreichem Auth-Call angelegt
    from app.domain.activity.models import ActivityLog as Activity
    count_before = Activity.query.filter_by(event="ssh_key:auth_success").count()

    from app.domain.ssh_keys.auth_service import authorize_ssh_key_access
    authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        public_key=KEY_OWNER,
    )
    count_after = Activity.query.filter_by(event="ssh_key:auth_success").count()
    check("Activity-Event ssh_key:auth_success wird nach Auth-Erfolg erstellt", count_after > count_before)

    # Failure-Event wird angelegt
    count_fail_before = Activity.query.filter_by(event="ssh_key:auth_failed").count()
    authorize_ssh_key_access(
        instance_uuid=_inst_uuid,
        username="m30-owner",
        public_key=KEY_STRANGER,
    )
    count_fail_after = Activity.query.filter_by(event="ssh_key:auth_failed").count()
    check("Activity-Event ssh_key:auth_failed wird nach Auth-Fehler erstellt", count_fail_after > count_fail_before)

    # Failure-Event enthaelt keinen Public Key (nur Fingerprint oder nichts)
    last_fail = (
        Activity.query.filter_by(event="ssh_key:auth_failed")
        .order_by(Activity.id.desc())
        .first()
    )
    if last_fail and last_fail.properties:
        props_str = json.dumps(last_fail.properties)
        check("Failure-Activity-Event: kein public_key in properties", "public_key" not in props_str)
    else:
        ok("Failure-Activity-Event: properties leer oder kein sensibles Feld")


# ================================================================
# f) Regression (M10–M29)
# ================================================================

print("\n=== f) Regression ===")

# file.sftp ist eine valide Permission
with app.app_context():
    from app.domain.collaborators.permissions import ALL_PERMISSIONS, is_valid_permission
    check("file.sftp ist in ALL_PERMISSIONS", "file.sftp" in ALL_PERMISSIONS)
    check("is_valid_permission('file.sftp') = True", is_valid_permission("file.sftp"))

# Bestehende Permissions unveraendert
with app.app_context():
    from app.domain.collaborators.permissions import ALL_PERMISSIONS
    for perm in ["file.read", "file.update", "file.delete", "control.console",
                 "backup.read", "database.read"]:
        check(f"Bestehende Permission '{perm}' noch vorhanden", perm in ALL_PERMISSIONS)

# M28: SSH-Key-Verwaltungs-Endpunkte noch intakt
resp = client.get("/api/client/account/ssh-keys", headers={"X-User-Id": str(_owner_id)})
check("M28 GET /api/client/account/ssh-keys -> 200", resp.status_code == 200)

resp = client.post(
    "/api/client/account/ssh-keys",
    content_type="application/json",
    data=json.dumps({"name": "regression-key", "public_key": KEY_STRANGER}),
    headers={"X-User-Id": str(_owner_id)},
)
check("M28 POST /api/client/account/ssh-keys -> 201", resp.status_code == 201)

# M29: Suspension-Endpoints noch intakt
resp = client.post(
    f"/api/admin/instances/{_inst_uuid}/suspend",
    content_type="application/json",
    data=json.dumps({"reason": "Regression-Test"}),
    headers={"X-User-Id": str(_admin_id)},
)
check("M29 POST /admin/instances/.../suspend -> 200", resp.status_code == 200)

# Suspendierte Instance blockiert SFTP
resp = sftp_pubkey("m30-owner", _inst_uuid, KEY_OWNER)
check("M29-Guard: Suspendierte Instance blockiert SFTP", resp.status_code == 403)

# Unsuspend wieder
resp = client.post(
    f"/api/admin/instances/{_inst_uuid}/unsuspend",
    headers={"X-User-Id": str(_admin_id)},
)
check("M29 POST /admin/instances/.../unsuspend -> 200", resp.status_code == 200)

# Agent-Callbacks (M13) noch intakt (Wings Remote-API)
with app.app_context():
    resp = report_container_state(client, _inst_uuid, "running")
check("M13 POST /remote/servers/.../container/status -> 200", resp.status_code == 200)

# Client-File-Endpunkte noch zugaenglich (nicht durch M30 gebrochen)
resp = client.get(
    f"/api/client/instances/{_inst_uuid}/files",
    query_string={"directory": "/"},
    headers={"X-User-Id": str(_owner_id)},
)
check("M-File GET /instances/.../files -> 200", resp.status_code == 200)

# Webhook-Katalog enthaelt alle bisherigen Events
with app.app_context():
    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS
    for event in [
        "instance:created", "instance:suspended", "instance:unsuspended",
        "ssh_key:created", "ssh_key:deleted",
        "backup:created", "file:written",
    ]:
        check(f"Webhook-Katalog: '{event}' noch vorhanden", event in WEBHOOK_EVENTS)


# ================================================================
# Ergebnis
# ================================================================

print(f"\n{'='*50}")
print(f"Gesamt: {passed + failed} Tests – {passed} OK, {failed} FEHLGESCHLAGEN")
if failed:
    print("ACHTUNG: Es gibt fehlgeschlagene Tests!")
    sys.exit(1)
else:
    print("Alle Tests bestanden.")
