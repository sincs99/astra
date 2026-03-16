#!/usr/bin/env python3
"""Astra CLI – Verwaltungsbefehle fuer Installation, Bootstrap und Betrieb.

Verwendung:
    python cli.py bootstrap [--username admin] [--email admin@astra.local] [--password admin]
    python cli.py check-config
    python cli.py db-status
    python cli.py worker [--poll-interval 1]
"""

import argparse
import sys
import os

# Sicherstellen, dass das Backend-Verzeichnis im Pfad ist
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_bootstrap(args):
    """Erstellt den initialen Admin-User."""
    from app import create_app, bootstrap_admin
    from app.extensions import db

    app = create_app()
    with app.app_context():
        db.create_all()
        result = bootstrap_admin(
            username=args.username,
            email=args.email,
            password=args.password,
            force=args.force,
        )
        print(f"[Bootstrap] {result['message']}")
        if result["created"]:
            print("[Bootstrap] WICHTIG: Passwort nach dem ersten Login aendern!")
        return 0 if result["created"] or "existiert" in result["message"] else 1


def cmd_check_config(args):
    """Prueft die aktuelle Konfiguration auf Probleme."""
    from app import create_app
    from app.config import config_by_name

    config_name = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
    print(f"[Config] Umgebung: {config_name}")

    config_cls = config_by_name.get(config_name)
    if not config_cls:
        print(f"[Config] FEHLER: Unbekannte Umgebung '{config_name}'")
        return 1

    issues = config_cls.validate_production()
    if issues:
        print(f"[Config] {len(issues)} Problem(e) gefunden:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("[Config] Keine Probleme gefunden.")
        return 0


def cmd_db_status(args):
    """Zeigt den Status der Datenbankmigrationen."""
    from app import create_app

    app = create_app()
    with app.app_context():
        from flask_migrate import current as flask_migrate_current
        print("[DB] Aktuelle Migration:")
        flask_migrate_current()
    return 0


def cmd_worker(args):
    """Startet den Job-Queue-Worker (M23)."""
    from app import create_app
    from app.infrastructure.jobs.worker import run_worker

    app = create_app()
    print(f"[Worker] Starte Queue-Worker (poll_interval={args.poll_interval}s)")
    run_worker(app, poll_interval=args.poll_interval)
    return 0


def cmd_version(args):
    """Zeigt die aktuelle Astra-Version und Build-Informationen (M24)."""
    from app.version import get_version_info
    info = get_version_info()
    print(f"[Version] Astra {info['version']}")
    if info.get("build_sha"):
        print(f"[Version] Build SHA: {info['build_sha']}")
    if info.get("build_date"):
        print(f"[Version] Build Date: {info['build_date']}")
    if info.get("build_ref"):
        print(f"[Version] Build Ref: {info['build_ref']}")
    return 0


def cmd_preflight(args):
    """Fuehrt einen Preflight-Check durch (M24)."""
    from app import create_app
    from app.domain.system.upgrade_service import run_preflight_check, get_migration_status

    app = create_app()
    with app.app_context():
        print("[Preflight] Starte Preflight-Check...")

        result = run_preflight_check()
        for name, status in result["checks"].items():
            symbol = "OK" if status == "ok" else "!!"
            print(f"  [{symbol}] {name}: {status}")

        if result["issues"]:
            print(f"\n[Preflight] {len(result['issues'])} Problem(e):")
            for issue in result["issues"]:
                print(f"  - {issue}")

        migration = get_migration_status()
        print(f"\n[Migration] Head: {migration.get('current_head', '?')}")
        print(f"[Migration] Applied: {migration.get('applied_revision', '?')}")
        print(f"[Migration] Up to date: {migration.get('is_up_to_date', '?')}")

        overall = result["overall_status"]
        print(f"\n[Preflight] Status: {overall} (compatible={result['compatible']})")
        return 0 if result["compatible"] else 1


def cmd_upgrade_status(args):
    """Zeigt den Upgrade-Status (M24)."""
    from app import create_app
    from app.domain.system.upgrade_service import get_upgrade_status

    app = create_app()
    with app.app_context():
        status = get_upgrade_status()
        print(f"[Upgrade] Version: {status['version']}")
        print(f"[Upgrade] Environment: {status['environment']}")
        print(f"[Upgrade] Migration up to date: {status['migration'].get('is_up_to_date', '?')}")
        print(f"[Upgrade] Upgrade required: {status['upgrade_required']}")
        if status["migration"].get("error"):
            print(f"[Upgrade] Migration error: {status['migration']['error']}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Astra CLI - Verwaltungsbefehle",
        prog="astra-cli",
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfuegbare Befehle")

    # ── bootstrap ───────────────────────────────────────
    bp = subparsers.add_parser("bootstrap", help="Erstellt den initialen Admin-User")
    bp.add_argument("--username", default="admin", help="Admin-Username (default: admin)")
    bp.add_argument("--email", default="admin@astra.local", help="Admin-Email")
    bp.add_argument("--password", default="admin", help="Admin-Passwort")
    bp.add_argument("--force", action="store_true", help="Bestehenden User zum Admin machen")

    # ── check-config ────────────────────────────────────
    subparsers.add_parser("check-config", help="Prueft die Konfiguration")

    # ── db-status ───────────────────────────────────────
    subparsers.add_parser("db-status", help="Zeigt DB-Migrationsstatus")

    # ── worker (M23) ───────────────────────────────────
    wp = subparsers.add_parser("worker", help="Startet den Job-Queue-Worker")
    wp.add_argument(
        "--poll-interval", type=float, default=1.0,
        help="Sekunden zwischen Queue-Polls (default: 1.0)"
    )

    # ── version (M24) ──────────────────────────────────
    subparsers.add_parser("version", help="Zeigt Astra-Version und Build-Info")

    # ── preflight (M24) ────────────────────────────────
    subparsers.add_parser("preflight", help="Fuehrt Preflight-/Kompatibilitaets-Check durch")

    # ── upgrade-status (M24) ───────────────────────────
    subparsers.add_parser("upgrade-status", help="Zeigt Upgrade-/Migrationsstatus")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "bootstrap": cmd_bootstrap,
        "check-config": cmd_check_config,
        "db-status": cmd_db_status,
        "worker": cmd_worker,
        "version": cmd_version,
        "preflight": cmd_preflight,
        "upgrade-status": cmd_upgrade_status,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
