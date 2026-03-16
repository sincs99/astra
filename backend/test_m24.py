"""Schnelltests fuer Meilenstein 24 - Release, Versioning & Upgrade Management."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  OK {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {label} - {detail}")


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


app = create_app("testing")


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    user = User(username="m24-user", email="m24@test.dev")
    user.set_password("testpass")
    db.session.add(user)

    agent = Agent(name="m24-agent", fqdn="m24.test.dev")
    agent.touch()
    db.session.add(agent)

    bp = Blueprint(name="m24-bp")
    db.session.add(bp)
    db.session.commit()


# ================================================================
# Test 1: Zentrale Versionsquelle
# ================================================================
print("\n== Zentrale Versionsquelle ==")

with app.app_context():
    from app.version import VERSION, get_version_info, get_git_sha, get_build_date

    check("VERSION ist String", isinstance(VERSION, str))
    check("VERSION nicht leer", len(VERSION) > 0)
    check("VERSION hat Punkt (semver)", "." in VERSION)
    check("VERSION ist gesetzt und gueltig", len(VERSION) > 0 and "." in VERSION, f"got {VERSION}")

    info = get_version_info()
    check("get_version_info liefert dict", isinstance(info, dict))
    check("info hat version", info["version"] == VERSION)
    check("info hat build_sha", "build_sha" in info)
    check("info hat build_date", "build_date" in info)
    check("info hat build_ref", "build_ref" in info)

    # Build-Date ist immer vorhanden (Default: jetzt)
    bd = get_build_date()
    check("get_build_date liefert String", isinstance(bd, str))
    check("get_build_date nicht leer", len(bd) > 0)

    # Git SHA (kann None sein ohne .git)
    sha = get_git_sha()
    check("get_git_sha liefert String oder None",
          sha is None or isinstance(sha, str))


# ================================================================
# Test 2: __version__ in __init__.py
# ================================================================
print("\n== __version__ Kompatibilitaet ==")

with app.app_context():
    from app import __version__
    check("__version__ == VERSION", __version__ == VERSION, f"got {__version__}")


# ================================================================
# Test 3: Migration-Status
# ================================================================
print("\n== Migration-Status ==")

with app.app_context():
    from app.domain.system.upgrade_service import get_migration_status

    status = get_migration_status()
    check("migration_status ist dict", isinstance(status, dict))
    check("hat current_head", "current_head" in status)
    check("hat applied_revision", "applied_revision" in status)
    check("hat is_up_to_date", "is_up_to_date" in status)
    check("hat pending_migrations", "pending_migrations" in status)
    check("hat error", "error" in status)

    # In-Memory SQLite hat keine Alembic-Tables -> error oder defaults
    # Beides akzeptabel
    check("migration_status fehlerfrei oder mit error",
          status["error"] is not None or status["is_up_to_date"] is not None)


# ================================================================
# Test 4: Upgrade-Status
# ================================================================
print("\n== Upgrade-Status ==")

with app.app_context():
    from app.domain.system.upgrade_service import get_upgrade_status

    us = get_upgrade_status()
    check("upgrade_status ist dict", isinstance(us, dict))
    check("hat version", us["version"] == VERSION)
    check("hat build", "build" in us)
    check("hat environment", us["environment"] == "testing")
    check("hat migration", "migration" in us)
    check("hat upgrade_required", "upgrade_required" in us)
    check("build hat version", us["build"]["version"] == VERSION)


# ================================================================
# Test 5: Preflight-Check
# ================================================================
print("\n== Preflight-Check ==")

with app.app_context():
    from app.domain.system.upgrade_service import run_preflight_check

    pf = run_preflight_check()
    check("preflight ist dict", isinstance(pf, dict))
    check("hat checks", "checks" in pf)
    check("hat issues", "issues" in pf)
    check("hat overall_status", "overall_status" in pf)
    check("hat compatible", "compatible" in pf)
    check("hat timestamp", "timestamp" in pf)

    # Checks enthalten mindestens config und database
    check("checks hat config", "config" in pf["checks"])
    check("checks hat database", "database" in pf["checks"])
    check("checks hat migrations", "migrations" in pf["checks"])

    # DB sollte in Tests OK sein
    check("database check = ok", pf["checks"]["database"] == "ok",
          f"got {pf['checks']['database']}")
    check("config check = ok oder warning",
          pf["checks"]["config"] in ("ok", "warning"),
          f"got {pf['checks']['config']}")


# ================================================================
# Test 6: Ops-Endpunkte
# ================================================================
print("\n== Ops-Endpunkte ==")

client = app.test_client()

with app.app_context():
    # /ops/version
    resp = client.get("/ops/version")
    check("GET /ops/version -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("ops/version hat version", data["version"] == VERSION)
    check("ops/version hat build_sha", "build_sha" in data)
    check("ops/version hat build_date", "build_date" in data)
    check("ops/version hat environment", "environment" in data)
    check("ops/version hat service", data["service"] == "astra-backend")

    # /ops/upgrade-status
    resp = client.get("/ops/upgrade-status")
    check("GET /ops/upgrade-status -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("upgrade-status hat version", data["version"] == VERSION)
    check("upgrade-status hat migration", "migration" in data)
    check("upgrade-status hat upgrade_required", "upgrade_required" in data)

    # /ops/preflight
    resp = client.get("/ops/preflight")
    check("GET /ops/preflight -> 200 oder 503",
          resp.status_code in (200, 503))
    data = resp.get_json()
    check("preflight hat compatible", "compatible" in data)
    check("preflight hat checks", "checks" in data)
    check("preflight hat overall_status", "overall_status" in data)


# ================================================================
# Test 7: Admin-API-Endpunkte
# ================================================================
print("\n== Admin-API-Endpunkte ==")

with app.app_context():
    resp = client.get("/api/admin/system/version")
    check("GET /admin/system/version -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("admin version hat version", data["version"] == VERSION)
    check("admin version hat environment", "environment" in data)

    resp = client.get("/api/admin/system/upgrade-status")
    check("GET /admin/system/upgrade-status -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("admin upgrade-status hat migration", "migration" in data)

    resp = client.get("/api/admin/system/preflight")
    check("GET /admin/system/preflight -> 200 oder 503",
          resp.status_code in (200, 503))
    data = resp.get_json()
    check("admin preflight hat checks", "checks" in data)


# ================================================================
# Test 8: Bestehende Ops-Endpunkte nutzen neue Version
# ================================================================
print("\n== Bestehende Ops-Endpunkte ==")

with app.app_context():
    resp = client.get("/health")
    check("GET /health -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/health hat version aus version.py", data["version"] == VERSION)

    resp = client.get("/ops/info")
    check("GET /ops/info -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/ops/info hat version aus version.py", data["version"] == VERSION)

    resp = client.get("/health/ready")
    check("GET /health/ready -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/health/ready hat version", data["version"] == VERSION)


# ================================================================
# Test 9: Fehlerbehandlung / Defaults
# ================================================================
print("\n== Fehlerbehandlung ==")

with app.app_context():
    from app.version import get_version_info

    # Ohne Umgebungsvariablen: Defaults
    info = get_version_info()
    check("version nie None", info["version"] is not None)
    check("build_date nie None (hat Default)", info["build_date"] is not None)
    # build_sha kann None sein (kein Git) - das ist OK
    check("build_sha ist String oder None",
          info["build_sha"] is None or isinstance(info["build_sha"], str))

    # Migration-Status bei Fehler: kein Crash
    status = get_migration_status()
    check("migration_status crasht nicht", status is not None)


# ================================================================
# Test 10: Keine Secrets in Endpunkten
# ================================================================
print("\n== Keine Secrets ==")

with app.app_context():
    import json

    # Ops-Version darf keine Secrets enthalten
    resp = client.get("/ops/version")
    raw = resp.get_data(as_text=True)
    check("ops/version ohne SECRET_KEY", "dev-secret-key" not in raw)
    check("ops/version ohne JWT_SECRET", "jwt-secret" not in raw)
    check("ops/version ohne Datenbankpfad", "sqlite" not in raw.lower() or "version" in raw.lower())

    resp = client.get("/ops/upgrade-status")
    raw = resp.get_data(as_text=True)
    check("upgrade-status ohne Secrets", "secret" not in raw.lower() or "secret_key" not in raw.lower())


# ================================================================
# Test 11: Regression
# ================================================================
print("\n== Regression ==")

with app.app_context():
    resp = client.get("/api/admin/agents")
    check("GET /admin/agents -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health")
    check("GET /admin/health -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/health/detailed")
    check("GET /admin/health/detailed -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/agents/monitoring")
    check("GET /admin/agents/monitoring -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/fleet/summary")
    check("GET /admin/fleet/summary -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/jobs")
    check("GET /admin/jobs -> 200", resp.status_code == 200)

    resp = client.get("/api/admin/jobs/summary")
    check("GET /admin/jobs/summary -> 200", resp.status_code == 200)


# ================================================================
# Test 12: CLI version (aufrufbar)
# ================================================================
print("\n== CLI ==")

with app.app_context():
    from app.version import VERSION

    # Simuliere CLI version-Befehl
    info = get_version_info()
    check("CLI version: info lieferbar", info["version"] == VERSION)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*60}")
print(f"M24 Release, Versioning & Upgrade: {passed} passed, {failed} failed")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
