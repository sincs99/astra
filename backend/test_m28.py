"""Tests fuer Meilenstein 28 – SSH Keys & SFTP Access Management.

Deckt ab:
a) Modell / Migration
b) Key-Validierung
c) Fingerprint
d) Service
e) API (GET / POST / PATCH / DELETE)
f) Activity / Webhook-Katalog
g) Regression (M10-M27 Kompatibilitaet)
"""

import sys
import os
import json
import struct
import base64
import hashlib

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
_user2_id = None


# ── Hilfsfunktionen: Valide Test-Keys bauen ──────────────────────────

def _make_ed25519_key(material: bytes = None, comment: str = "test") -> str:
    """Erzeugt einen synthetisch gueltigen ssh-ed25519 Public Key."""
    if material is None:
        material = b"\x42" * 32
    key_type = b"ssh-ed25519"
    data = (
        struct.pack(">I", len(key_type)) + key_type
        + struct.pack(">I", len(material)) + material
    )
    return f"ssh-ed25519 {base64.b64encode(data).decode()} {comment}"


def _make_rsa_key(comment: str = "test") -> str:
    """Erzeugt einen synthetisch gueltigen ssh-rsa Public Key."""
    key_type = b"ssh-rsa"
    # exponent 65537
    e_bytes = b"\x01\x00\x01"
    # 1024-bit modulus: leading zero so high bit is 0
    n_bytes = b"\x00" + b"\x01" * 128
    data = (
        struct.pack(">I", len(key_type)) + key_type
        + struct.pack(">I", len(e_bytes)) + e_bytes
        + struct.pack(">I", len(n_bytes)) + n_bytes
    )
    return f"ssh-rsa {base64.b64encode(data).decode()} {comment}"


def _expected_fingerprint(public_key: str) -> str:
    """Berechnet den erwarteten SHA256-Fingerprint fuer einen Public Key."""
    key_body_b64 = public_key.strip().split()[1]
    key_bytes = base64.b64decode(key_body_b64)
    digest = hashlib.sha256(key_bytes).digest()
    b64 = base64.b64encode(digest).decode().rstrip("=")
    return f"SHA256:{b64}"


# ================================================================
# Setup – User anlegen
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User

    user = User(username="m28-user", email="m28@test.dev")
    user.set_password("testpass")
    db.session.add(user)

    user2 = User(username="m28-user2", email="m28b@test.dev")
    user2.set_password("testpass")
    db.session.add(user2)

    db.session.commit()
    _user_id = user.id
    _user2_id = user2.id


# ================================================================
# a) Modell / Migration
# ================================================================

print("\n=== a) Modell / Migration ===")

with app.app_context():
    from app.domain.ssh_keys.models import UserSshKey

    check("UserSshKey Klasse importierbar", UserSshKey is not None)

    # Tabelle existiert – direktes Anlegen testen
    key = UserSshKey(
        user_id=_user_id,
        name="Test Key",
        fingerprint="SHA256:test000",
        public_key="ssh-ed25519 AAAA test",
    )
    db.session.add(key)
    db.session.commit()

    check("UserSshKey speicherbar", key.id is not None)
    check("UserSshKey.user_id korrekt", key.user_id == _user_id)
    check("UserSshKey.name korrekt", key.name == "Test Key")
    check("UserSshKey.fingerprint korrekt", key.fingerprint == "SHA256:test000")
    check("UserSshKey.created_at gesetzt", key.created_at is not None)
    check("UserSshKey.updated_at gesetzt", key.updated_at is not None)

    # to_dict
    d = key.to_dict()
    check("to_dict hat id", "id" in d)
    check("to_dict hat name", d["name"] == "Test Key")
    check("to_dict hat fingerprint", d["fingerprint"] == "SHA256:test000")
    check("to_dict hat public_key", "public_key" in d)
    check("to_dict hat created_at", "created_at" in d)

    # Unique Constraint: gleicher Fingerprint pro User muss scheitern
    dup = UserSshKey(
        user_id=_user_id,
        name="Duplicate",
        fingerprint="SHA256:test000",
        public_key="ssh-ed25519 AAAA dup",
    )
    db.session.add(dup)
    try:
        db.session.commit()
        fail("Unique Constraint auf (user_id, fingerprint) greift")
    except Exception:
        db.session.rollback()
        ok("Unique Constraint auf (user_id, fingerprint) greift")

    # Gleicher Fingerprint bei anderem User muss erlaubt sein
    other_key = UserSshKey(
        user_id=_user2_id,
        name="Other User Key",
        fingerprint="SHA256:test000",
        public_key="ssh-ed25519 AAAA other",
    )
    db.session.add(other_key)
    try:
        db.session.commit()
        ok("Gleicher Fingerprint bei anderem User erlaubt")
    except Exception as e:
        db.session.rollback()
        fail("Gleicher Fingerprint bei anderem User erlaubt", str(e))

    # Beziehung User → ssh_keys
    user_obj = db.session.get(User, _user_id)
    check("User.ssh_keys Beziehung existiert", hasattr(user_obj, "ssh_keys"))

    # Aufraeumen fuer naechste Tests
    UserSshKey.query.delete()
    db.session.commit()


# ================================================================
# b) Key-Validierung
# ================================================================

print("\n=== b) Key-Validierung ===")

with app.app_context():
    from app.domain.ssh_keys.validator import validate_and_parse, SshKeyValidationError

    # Gueltiger ssh-ed25519 Key
    valid_ed = _make_ed25519_key()
    try:
        key_type, fp = validate_and_parse(valid_ed)
        check("Gueltiger ed25519 Key akzeptiert", key_type == "ssh-ed25519")
        check("ed25519 Fingerprint beginnt mit SHA256:", fp.startswith("SHA256:"))
    except SshKeyValidationError as e:
        fail("Gueltiger ed25519 Key akzeptiert", str(e))

    # Gueltiger ssh-rsa Key
    valid_rsa = _make_rsa_key()
    try:
        key_type, fp = validate_and_parse(valid_rsa)
        check("Gueltiger rsa Key akzeptiert", key_type == "ssh-rsa")
    except SshKeyValidationError as e:
        fail("Gueltiger rsa Key akzeptiert", str(e))

    # Leerer Key → Fehler
    try:
        validate_and_parse("")
        fail("Leerer Key wird abgelehnt")
    except SshKeyValidationError:
        ok("Leerer Key wird abgelehnt")

    # Nicht unterstuetzter Typ → Fehler
    try:
        validate_and_parse("ssh-dss AAAAB3NzaC1kc3M test")
        fail("Unbekannter Key-Typ wird abgelehnt")
    except SshKeyValidationError:
        ok("Unbekannter Key-Typ wird abgelehnt")

    # Kaputtes Base64 → Fehler
    try:
        validate_and_parse("ssh-ed25519 !!!KEIN_BASE64!!! test")
        fail("Kaputtes Base64 wird abgelehnt")
    except SshKeyValidationError:
        ok("Kaputtes Base64 wird abgelehnt")

    # Body mit falschem Typ-Token (Header ed25519, Body rsa) → Fehler
    rsa_body = _make_rsa_key().split()[1]
    mismatched = f"ssh-ed25519 {rsa_body} test"
    try:
        validate_and_parse(mismatched)
        fail("Mismatched Key-Typ im Body wird abgelehnt")
    except SshKeyValidationError:
        ok("Mismatched Key-Typ im Body wird abgelehnt")

    # Zu kurzer Body → Fehler
    tiny = base64.b64encode(b"\x00\x01").decode()
    try:
        validate_and_parse(f"ssh-ed25519 {tiny} test")
        fail("Zu kurzer Key-Body wird abgelehnt")
    except SshKeyValidationError:
        ok("Zu kurzer Key-Body wird abgelehnt")


# ================================================================
# c) Fingerprint
# ================================================================

print("\n=== c) Fingerprint ===")

with app.app_context():
    from app.domain.ssh_keys.validator import validate_and_parse

    key1 = _make_ed25519_key(material=b"\xAB" * 32)
    key2 = _make_ed25519_key(material=b"\xAB" * 32)  # identisches Material
    key3 = _make_ed25519_key(material=b"\xCD" * 32)  # anderes Material

    _, fp1 = validate_and_parse(key1)
    _, fp2 = validate_and_parse(key2)
    _, fp3 = validate_and_parse(key3)

    check("Gleicher Key → gleicher Fingerprint", fp1 == fp2)
    check("Anderes Key-Material → anderer Fingerprint", fp1 != fp3)
    check("Fingerprint Format SHA256:...", fp1.startswith("SHA256:") and len(fp1) > 10)

    # Fingerprint stimmt mit manueller Berechnung ueberein
    expected = _expected_fingerprint(key1)
    check("Fingerprint stimmt mit SHA256-Berechnung ueberein", fp1 == expected)


# ================================================================
# d) Service
# ================================================================

print("\n=== d) Service ===")

_key_id = None

with app.app_context():
    from app.domain.ssh_keys.service import (
        list_user_ssh_keys,
        create_user_ssh_key,
        delete_user_ssh_key,
        update_user_ssh_key_name,
        SshKeyError,
    )

    ed_key = _make_ed25519_key(material=b"\x11" * 32, comment="laptop")

    # Erstellen
    key = create_user_ssh_key(_user_id, "My Laptop", ed_key)
    _key_id = key.id
    check("SSH Key erstellen", key.id is not None)
    check("SSH Key name korrekt", key.name == "My Laptop")
    check("SSH Key fingerprint gesetzt", key.fingerprint.startswith("SHA256:"))
    check("SSH Key user_id korrekt", key.user_id == _user_id)

    # Listen
    keys = list_user_ssh_keys(_user_id)
    check("SSH Keys listen", len(keys) == 1)
    check("Listeneintrag hat korrekten Namen", keys[0].name == "My Laptop")

    # Duplikat verhindern
    try:
        create_user_ssh_key(_user_id, "Duplikat", ed_key)
        fail("Duplikat-Fingerprint wird abgelehnt (409)")
    except SshKeyError as e:
        check("Duplikat-Fingerprint wird abgelehnt (409)", e.status_code == 409)

    # Ungültiger Key
    try:
        create_user_ssh_key(_user_id, "Kaputt", "ssh-ed25519 KEINBASE64 test")
        fail("Ungueltiger Key wird abgelehnt (400)")
    except SshKeyError as e:
        check("Ungueltiger Key wird abgelehnt (400)", e.status_code == 400)

    # Name-Update
    key = update_user_ssh_key_name(_user_id, _key_id, "Renamed Laptop")
    check("SSH Key umbenennen", key.name == "Renamed Laptop")

    # Löschen
    delete_user_ssh_key(_user_id, _key_id)
    keys_after = list_user_ssh_keys(_user_id)
    check("SSH Key geloescht", len(keys_after) == 0)

    # Nochmals loeschen → 404
    try:
        delete_user_ssh_key(_user_id, _key_id)
        fail("Loeschen nicht-existenter Key → 404")
    except SshKeyError as e:
        check("Loeschen nicht-existenter Key → 404", e.status_code == 404)

    # Fremder Key nicht zugaenglich
    foreign = create_user_ssh_key(_user2_id, "User2 Key", _make_ed25519_key(material=b"\x99" * 32))
    try:
        delete_user_ssh_key(_user_id, foreign.id)
        fail("Fremder Key nicht zugaenglich → 404")
    except SshKeyError as e:
        check("Fremder Key nicht zugaenglich → 404", e.status_code == 404)

    # Aufraeumen
    from app.domain.ssh_keys.models import UserSshKey
    UserSshKey.query.delete()
    db.session.commit()


# ================================================================
# e) API
# ================================================================

print("\n=== e) API ===")

_api_key_id = None

# Ohne Auth → 401
resp = client.get("/api/client/account/ssh-keys")
check("GET /ssh-keys ohne Auth → 401", resp.status_code == 401)

resp = client.post("/api/client/account/ssh-keys", content_type="application/json",
                   data=json.dumps({"name": "x", "public_key": "y"}))
check("POST /ssh-keys ohne Auth → 401", resp.status_code == 401)

# GET – leer
resp = client.get("/api/client/account/ssh-keys",
                  headers={"X-User-Id": str(_user_id)})
check("GET /ssh-keys leer → 200", resp.status_code == 200)
check("GET /ssh-keys gibt Liste zurueck", isinstance(resp.get_json(), list))
check("GET /ssh-keys leer = []", resp.get_json() == [])

# POST – gueltiger Key
ed_key_api = _make_ed25519_key(material=b"\xAA" * 32, comment="api-test")
resp = client.post(
    "/api/client/account/ssh-keys",
    content_type="application/json",
    data=json.dumps({"name": "API Test Key", "public_key": ed_key_api}),
    headers={"X-User-Id": str(_user_id)},
)
check("POST /ssh-keys gueltiger Key → 201", resp.status_code == 201)
data = resp.get_json()
check("POST Response hat id", "id" in data)
check("POST Response hat fingerprint", data.get("fingerprint", "").startswith("SHA256:"))
check("POST Response hat name", data.get("name") == "API Test Key")
check("POST Response hat public_key", "public_key" in data)
check("POST Response hat created_at", "created_at" in data)
_api_key_id = data.get("id")

# POST – Duplikat → 409
resp = client.post(
    "/api/client/account/ssh-keys",
    content_type="application/json",
    data=json.dumps({"name": "Duplikat", "public_key": ed_key_api}),
    headers={"X-User-Id": str(_user_id)},
)
check("POST /ssh-keys Duplikat → 409", resp.status_code == 409)

# POST – ungueltiger Key → 400
resp = client.post(
    "/api/client/account/ssh-keys",
    content_type="application/json",
    data=json.dumps({"name": "Kaputt", "public_key": "ssh-ed25519 !!!KEIN_BASE64!!!"}),
    headers={"X-User-Id": str(_user_id)},
)
check("POST /ssh-keys ungueltiger Key → 400", resp.status_code == 400)

# POST – fehlender Name → 400
resp = client.post(
    "/api/client/account/ssh-keys",
    content_type="application/json",
    data=json.dumps({"name": "", "public_key": ed_key_api}),
    headers={"X-User-Id": str(_user_id)},
)
check("POST /ssh-keys fehlender Name → 400", resp.status_code == 400)

# GET – jetzt ein Key
resp = client.get("/api/client/account/ssh-keys",
                  headers={"X-User-Id": str(_user_id)})
check("GET /ssh-keys nach POST → 1 Eintrag", len(resp.get_json()) == 1)

# PATCH – umbenennen
if _api_key_id:
    resp = client.patch(
        f"/api/client/account/ssh-keys/{_api_key_id}",
        content_type="application/json",
        data=json.dumps({"name": "Renamed Via API"}),
        headers={"X-User-Id": str(_user_id)},
    )
    check("PATCH /ssh-keys/<id> → 200", resp.status_code == 200)
    check("PATCH Response hat neuen Namen", resp.get_json().get("name") == "Renamed Via API")

    # PATCH fremder Key → 404
    resp = client.patch(
        f"/api/client/account/ssh-keys/{_api_key_id}",
        content_type="application/json",
        data=json.dumps({"name": "Hack"}),
        headers={"X-User-Id": str(_user2_id)},
    )
    check("PATCH fremder Key → 404", resp.status_code == 404)

# DELETE fremder Key → 404
if _api_key_id:
    resp = client.delete(
        f"/api/client/account/ssh-keys/{_api_key_id}",
        headers={"X-User-Id": str(_user2_id)},
    )
    check("DELETE fremder Key → 404", resp.status_code == 404)

# DELETE – loeschen
if _api_key_id:
    resp = client.delete(
        f"/api/client/account/ssh-keys/{_api_key_id}",
        headers={"X-User-Id": str(_user_id)},
    )
    check("DELETE /ssh-keys/<id> → 200", resp.status_code == 200)

    # Nochmals loeschen → 404
    resp = client.delete(
        f"/api/client/account/ssh-keys/{_api_key_id}",
        headers={"X-User-Id": str(_user_id)},
    )
    check("DELETE nochmals → 404", resp.status_code == 404)

# GET nach DELETE → leer
resp = client.get("/api/client/account/ssh-keys",
                  headers={"X-User-Id": str(_user_id)})
check("GET /ssh-keys nach DELETE → leer", resp.get_json() == [])


# ================================================================
# f) Activity / Webhook-Katalog
# ================================================================

print("\n=== f) Activity / Webhook-Katalog ===")

with app.app_context():
    from app.domain.activity.events import SSH_KEY_CREATED, SSH_KEY_UPDATED, SSH_KEY_DELETED

    check("SSH_KEY_CREATED Event definiert", SSH_KEY_CREATED == "ssh_key:created")
    check("SSH_KEY_UPDATED Event definiert", SSH_KEY_UPDATED == "ssh_key:updated")
    check("SSH_KEY_DELETED Event definiert", SSH_KEY_DELETED == "ssh_key:deleted")

    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS, get_event_catalog

    check("ssh_key:created im Webhook-Katalog", "ssh_key:created" in WEBHOOK_EVENTS)
    check("ssh_key:deleted im Webhook-Katalog", "ssh_key:deleted" in WEBHOOK_EVENTS)

    catalog = get_event_catalog()
    catalog_events = [e["event"] for e in catalog]
    check("Katalog enthaelt ssh_key:created", "ssh_key:created" in catalog_events)
    check("Katalog enthaelt ssh_key:deleted", "ssh_key:deleted" in catalog_events)

    # Activity-Eintrag wird bei create erzeugt
    from app.domain.activity.models import ActivityLog
    from app.domain.ssh_keys.service import create_user_ssh_key
    from app.domain.ssh_keys.models import UserSshKey

    count_before = ActivityLog.query.filter_by(event="ssh_key:created").count()
    new_key = create_user_ssh_key(
        _user_id, "Event-Test Key",
        _make_ed25519_key(material=b"\xEE" * 32, comment="event-test")
    )
    count_after = ActivityLog.query.filter_by(event="ssh_key:created").count()
    check("Activity-Event ssh_key:created wird erzeugt", count_after == count_before + 1)

    # Activity-Eintrag bei delete
    from app.domain.ssh_keys.service import delete_user_ssh_key
    count_del_before = ActivityLog.query.filter_by(event="ssh_key:deleted").count()
    delete_user_ssh_key(_user_id, new_key.id)
    count_del_after = ActivityLog.query.filter_by(event="ssh_key:deleted").count()
    check("Activity-Event ssh_key:deleted wird erzeugt", count_del_after == count_del_before + 1)

    # Aufraeumen
    UserSshKey.query.delete()
    db.session.commit()


# ================================================================
# g) Regression – M10-M27 Kompatibilitaet
# ================================================================

print("\n=== g) Regression ===")

resp = client.get("/api/auth/health")
check("GET /api/auth/health → 200", resp.status_code == 200)

resp = client.get("/api/admin/health")
check("GET /api/admin/health → 200", resp.status_code == 200)

resp = client.get("/api/admin/agents", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/agents → 200", resp.status_code == 200)

resp = client.get("/api/admin/blueprints", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/blueprints → 200", resp.status_code == 200)

resp = client.get("/api/admin/instances", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/instances → 200", resp.status_code == 200)

resp = client.get("/api/admin/webhooks", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/webhooks → 200", resp.status_code == 200)

resp = client.get("/api/client/instances", headers={"X-User-Id": str(_user_id)})
check("GET /api/client/instances → 200", resp.status_code == 200)

resp = client.get("/api/admin/jobs", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/jobs → 200", resp.status_code == 200)

resp = client.get("/api/admin/system/version", headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/system/version → 200", resp.status_code == 200)

# Webhook-Katalog hat unveraendert alle alten Events
with app.app_context():
    from app.domain.webhooks.event_catalog import WEBHOOK_EVENTS
    for event in [
        "instance:created", "backup:created", "database:created",
        "collaborator:added", "routine:created", "agent:maintenance_enabled",
    ]:
        check(f"Webhook-Katalog: {event} noch vorhanden", event in WEBHOOK_EVENTS)


# ================================================================
# Ergebnis
# ================================================================

print(f"\n{'='*50}")
print(f"  Gesamt: {passed + failed} Tests | {passed} bestanden | {failed} fehlgeschlagen")
print(f"{'='*50}")

if failed > 0:
    sys.exit(1)
