"""Upgrade- und Preflight-Service (M24).

Prueft Migrations-Status, Konfiguration und Betriebsbereitschaft.
Keine sensitiven Daten in den Ergebnissen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_migration_status() -> dict:
    """Prueft den aktuellen DB-Migrationsstatus.

    Returns:
        dict mit current_head, applied_revision, is_up_to_date, error
    """
    result = {
        "current_head": None,
        "applied_revision": None,
        "is_up_to_date": False,
        "pending_migrations": 0,
        "error": None,
    }

    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        from alembic.migration import MigrationContext
        from app.extensions import db
        import os

        # Alembic-Konfiguration laden
        migrations_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "migrations"
        )
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", migrations_dir)

        # Code-seitige Head-Revision
        script_dir = ScriptDirectory.from_config(alembic_cfg)
        heads = script_dir.get_heads()
        result["current_head"] = heads[0] if heads else None

        # DB-seitige angewendete Revision
        connection = db.engine.connect()
        context = MigrationContext.configure(connection)
        current_revs = context.get_current_heads()
        result["applied_revision"] = current_revs[0] if current_revs else None
        connection.close()

        # Up-to-date pruefen
        if result["current_head"] and result["applied_revision"]:
            result["is_up_to_date"] = result["current_head"] == result["applied_revision"]
        elif not result["current_head"] and not result["applied_revision"]:
            # Keine Migrationen vorhanden = up to date
            result["is_up_to_date"] = True

        # Pending Migrations zaehlen (best-effort)
        if not result["is_up_to_date"] and result["applied_revision"]:
            try:
                revisions = list(script_dir.iterate_revisions(
                    result["current_head"], result["applied_revision"]
                ))
                result["pending_migrations"] = len(revisions)
            except Exception:
                result["pending_migrations"] = -1  # unbekannt

    except ImportError:
        result["error"] = "Alembic nicht verfuegbar"
    except Exception as e:
        result["error"] = f"Migrationsstatus nicht lesbar: {type(e).__name__}"
        logger.warning("Migrationsstatus-Fehler: %s", str(e))

    return result


def run_preflight_check() -> dict:
    """Fuehrt einen umfassenden Preflight-/Compatibility-Check durch.

    Prueft:
    - App-Konfiguration
    - DB-Erreichbarkeit
    - Migrationen aktuell
    - Redis/Queue erreichbar (optional)

    Returns:
        dict mit checks, overall_status, compatible, timestamp
    """
    checks = {}
    issues = []

    # 1. App-Konfiguration
    try:
        from flask import current_app
        config = current_app.config
        checks["config"] = "ok"

        # Kritische Werte pruefen
        if config.get("SECRET_KEY") == "dev-secret-key" and config.get("APP_ENV") == "production":
            issues.append("SECRET_KEY verwendet Default in Produktion")
            checks["config"] = "warning"
    except Exception as e:
        checks["config"] = f"error: {type(e).__name__}"
        issues.append(f"Konfiguration nicht lesbar: {type(e).__name__}")

    # 2. Datenbank
    try:
        from app.extensions import db
        db.session.execute(db.text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        issues.append(f"Datenbank nicht erreichbar: {type(e).__name__}")

    # 3. Migrationen
    migration = get_migration_status()
    if migration.get("error"):
        checks["migrations"] = f"error: {migration['error']}"
        issues.append(f"Migrations-Check fehlgeschlagen: {migration['error']}")
    elif migration.get("is_up_to_date"):
        checks["migrations"] = "ok"
    else:
        checks["migrations"] = "pending"
        pending = migration.get("pending_migrations", "?")
        issues.append(f"Migrationen nicht aktuell ({pending} ausstehend)")

    # 4. Redis/Queue (optional, nicht kritisch)
    try:
        from flask import current_app
        redis_url = current_app.config.get("REDIS_URL", "")
        if redis_url and current_app.config.get("JOB_QUEUE_BACKEND") == "redis":
            try:
                import redis
                r = redis.from_url(redis_url)
                r.ping()
                checks["redis"] = "ok"
            except ImportError:
                checks["redis"] = "not_installed"
            except Exception:
                checks["redis"] = "unreachable"
                issues.append("Redis nicht erreichbar")
        else:
            checks["redis"] = "not_configured"
    except Exception:
        checks["redis"] = "unknown"

    # Gesamtstatus
    has_errors = any(v.startswith("error") for v in checks.values() if isinstance(v, str))
    has_pending = checks.get("migrations") == "pending"

    if has_errors:
        overall = "error"
        compatible = False
    elif has_pending:
        overall = "pending_upgrade"
        compatible = False
    elif issues:
        overall = "warning"
        compatible = True
    else:
        overall = "ok"
        compatible = True

    return {
        "checks": checks,
        "issues": issues,
        "overall_status": overall,
        "compatible": compatible,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_upgrade_status() -> dict:
    """Kombinierte Upgrade-Status-Antwort.

    Enthaelt Version, Build-Info, Environment, Migration und Preflight.
    """
    from app.version import get_version_info, VERSION

    version_info = get_version_info()
    migration = get_migration_status()

    try:
        from flask import current_app
        environment = current_app.config.get("APP_ENV", "unknown")
    except Exception:
        environment = "unknown"

    return {
        "version": VERSION,
        "build": version_info,
        "environment": environment,
        "migration": migration,
        "upgrade_required": not migration.get("is_up_to_date", True),
    }
