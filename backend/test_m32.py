"""Tests fuer Meilenstein 32 – Pilotbetrieb & v1.0-Rollout.

Deckt ab:
a) Version korrekt aktualisiert auf 0.32.0-rc
b) RELEASE_PHASE vorhanden und korrekt
c) get_version_info() enthaelt release_phase
d) /ops/info liefert release_phase
e) /admin/system/version liefert release_phase
f) /health und /health/ready funktionieren weiterhin
g) Regression: Bestehende Admin-/Client-/Agent-Endpunkte funktionieren
"""

import sys
import os
import json

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


# ── App Setup ────────────────────────────────────────────

app = create_app()
app.config["TESTING"] = True
client = app.test_client()

with app.app_context():
    db.create_all()


def get_auth_headers():
    """Erstellt Admin-User und gibt Auth-Header zurueck."""
    from app.domain.users.models import User
    with app.app_context():
        user = User.query.filter_by(username="m32_admin").first()
        if not user:
            user = User(username="m32_admin", email="m32@test.local", is_admin=True)
            user.set_password("test1234")
            db.session.add(user)
            db.session.commit()

    resp = client.post("/api/auth/login", json={
        "username": "m32_admin",
        "password": "test1234",
    })
    data = resp.get_json()
    token = data.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ── a) Version korrekt ──────────────────────────────────

print("\n=== a) Version ===")

from app.version import VERSION, RELEASE_PHASE, get_version_info

check("VERSION ist 0.32.0-rc", VERSION == "0.32.0-rc", f"got: {VERSION}")
check("VERSION beginnt mit 0.32", VERSION.startswith("0.32"), f"got: {VERSION}")


# ── b) RELEASE_PHASE ────────────────────────────────────

print("\n=== b) RELEASE_PHASE ===")

check("RELEASE_PHASE existiert", RELEASE_PHASE is not None)
check("RELEASE_PHASE ist 'pilot'", RELEASE_PHASE == "pilot", f"got: {RELEASE_PHASE}")
check("RELEASE_PHASE ist gueltiger Wert",
      RELEASE_PHASE in ("development", "rc", "pilot", "stable"),
      f"got: {RELEASE_PHASE}")


# ── c) get_version_info() ───────────────────────────────

print("\n=== c) get_version_info() ===")

with app.app_context():
    info = get_version_info()
    check("get_version_info hat 'version'", "version" in info)
    check("get_version_info hat 'release_phase'", "release_phase" in info)
    check("get_version_info version == VERSION", info["version"] == VERSION)
    check("get_version_info release_phase == RELEASE_PHASE", info["release_phase"] == RELEASE_PHASE)
    check("get_version_info hat 'build_sha'", "build_sha" in info)
    check("get_version_info hat 'build_date'", "build_date" in info)
    check("get_version_info hat 'build_ref'", "build_ref" in info)


# ── d) /ops/info Endpunkt ───────────────────────────────

print("\n=== d) /ops/info ===")

with app.app_context():
    resp = client.get("/ops/info")
    check("/ops/info -> 200", resp.status_code == 200, f"got: {resp.status_code}")
    data = resp.get_json()
    check("/ops/info hat 'release_phase'", "release_phase" in data, f"keys: {list(data.keys())}")
    check("/ops/info release_phase == 'pilot'", data.get("release_phase") == "pilot",
          f"got: {data.get('release_phase')}")
    check("/ops/info hat 'version'", "version" in data)
    check("/ops/info version == 0.32.0-rc", data.get("version") == "0.32.0-rc",
          f"got: {data.get('version')}")
    check("/ops/info hat 'service'", data.get("service") == "astra-backend")


# ── e) /admin/system/version Endpunkt ───────────────────

print("\n=== e) /admin/system/version ===")

with app.app_context():
    headers = get_auth_headers()
    resp = client.get("/api/admin/system/version", headers=headers)
    check("/admin/system/version -> 200", resp.status_code == 200, f"got: {resp.status_code}")
    data = resp.get_json()
    check("/admin/system/version hat 'release_phase'", "release_phase" in data,
          f"keys: {list(data.keys())}")
    check("/admin/system/version release_phase == 'pilot'",
          data.get("release_phase") == "pilot", f"got: {data.get('release_phase')}")
    check("/admin/system/version version korrekt", data.get("version") == "0.32.0-rc",
          f"got: {data.get('version')}")


# ── f) Health-Endpunkte ─────────────────────────────────

print("\n=== f) Health-Endpunkte ===")

with app.app_context():
    resp = client.get("/health")
    check("/health -> 200", resp.status_code == 200, f"got: {resp.status_code}")
    data = resp.get_json()
    check("/health status=ok", data.get("status") == "ok", f"got: {data.get('status')}")

    resp = client.get("/health/ready")
    check("/health/ready -> 200", resp.status_code == 200, f"got: {resp.status_code}")
    data = resp.get_json()
    check("/health/ready hat status", "status" in data)


# ── g) Regression: Basis-Endpunkte ──────────────────────

print("\n=== g) Regression ===")

with app.app_context():
    headers = get_auth_headers()

    # Admin Health
    resp = client.get("/api/admin/health", headers=headers)
    check("Admin /health -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Users
    resp = client.get("/api/admin/users", headers=headers)
    check("Admin /users -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Agents
    resp = client.get("/api/admin/agents", headers=headers)
    check("Admin /agents -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Blueprints
    resp = client.get("/api/admin/blueprints", headers=headers)
    check("Admin /blueprints -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Instances
    resp = client.get("/api/admin/instances", headers=headers)
    check("Admin /instances -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Jobs
    resp = client.get("/api/admin/jobs", headers=headers)
    check("Admin /jobs -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Admin Health Detailed
    resp = client.get("/api/admin/health/detailed", headers=headers)
    check("Admin /health/detailed -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Ops Endpunkte
    resp = client.get("/ops/version")
    check("/ops/version -> 200", resp.status_code == 200, f"got: {resp.status_code}")

    # Preflight
    resp = client.get("/api/admin/system/preflight", headers=headers)
    check("Admin /system/preflight -> 200 oder 503",
          resp.status_code in (200, 503), f"got: {resp.status_code}")


# ── Ergebnis ─────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  M32 Tests: {passed} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(1 if failed else 0)
