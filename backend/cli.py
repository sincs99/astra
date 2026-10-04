#!/usr/bin/env python3
"""Astra CLI – Verwaltungsbefehle fuer Installation, Bootstrap und Betrieb.

Verwendung:
    python cli.py bootstrap [--username admin] [--email admin@astra.local] [--password admin]
    python cli.py check-config
    python cli.py db-init
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


def cmd_import_blueprint(args):
    """Importiert ein Pterodactyl/Pelican-Egg (JSON/YAML) oder natives Blueprint-JSON."""
    import json

    from app import create_app
    from app.extensions import db
    from app.domain.blueprints.egg_import import EggImportError, import_blueprint

    try:
        with open(args.file, encoding="utf-8") as fh:
            raw = fh.read()
        if args.file.lower().endswith((".yaml", ".yml")):
            import yaml
            data = yaml.safe_load(raw)
        else:
            data = json.loads(raw)
    except (OSError, ValueError) as exc:
        print(f"[Import] Datei konnte nicht gelesen werden: {exc}")
        return 1

    app = create_app()
    with app.app_context():
        db.create_all()
        try:
            blueprint = import_blueprint(data)
        except EggImportError as exc:
            print(f"[Import] Fehler: {exc}")
            return 1
        print(f"[Import] Blueprint '{blueprint.name}' angelegt (ID {blueprint.id})")
    return 0


def cmd_db_init(args):
    """Bringt die Datenbank idempotent auf den aktuellen Stand (fuer AUTO_MIGRATE/Entrypoint).

    - Frische Datenbank (keine alembic_version-Tabelle): Schema per create_all() anlegen
      und auf den Migrations-Head stampen. Die Migrationen setzen die Basistabellen voraus
      und legen sie nicht selbst an.
    - Bestehende Datenbank mit alembic_version: regulaeres `flask db upgrade`.
    """
    from sqlalchemy import inspect as sa_inspect
    from flask_migrate import upgrade as fm_upgrade, stamp as fm_stamp

    from app import create_app
    from app.extensions import db

    app = create_app()
    with app.app_context():
        tables = set(sa_inspect(db.engine).get_table_names())
        if "alembic_version" in tables:
            print("[DB] alembic_version vorhanden – fuehre Migrationen aus (flask db upgrade) ...")
            fm_upgrade()
        else:
            if tables:
                print(f"[DB] {len(tables)} Tabellen ohne Migrationsstand gefunden – ergaenze fehlende Tabellen und stampe Head.")
            else:
                print("[DB] Frische Datenbank – lege Schema an (create_all) und stampe Head.")
            db.create_all()
            fm_stamp()
        from flask_migrate import current as fm_current
        print("[DB] Stand:")
        fm_current()
    return 0


def cmd_billing_tick(args):
    """Setzt Laufzeiten durch (ueberfaellig -> suspendiert, Karenzzeit vorbei -> geloescht). Fuer Cron/Compose."""
    import json

    from app import create_app
    from app.domain.billing.service import run_billing_tick

    app = create_app()
    with app.app_context():
        summary = run_billing_tick()
    print(json.dumps(summary, ensure_ascii=False))
    # Exit-Code 1 bei Fehlern, damit Cron/Monitoring sie bemerkt (betroffene Bestellungen werden erneut versucht)
    return 1 if summary["errors"] else 0


def cmd_cleanup_jobs(args):
    """Loescht alte, beendete Job-Eintraege (completed/failed)."""
    import json

    from app import create_app
    from app.infrastructure.jobs.cleanup import cleanup_jobs

    app = create_app()
    with app.app_context():
        try:
            summary = cleanup_jobs(days=args.days, dry_run=args.dry_run)
        except ValueError as e:
            print(f"Fehler: {e}")
            return 2
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def cmd_alert_test(args):
    """Schickt eine Testnachricht an die konfigurierten Admin-Kanaele (ADMIN_ALERT_EMAIL, ADMIN_ALERT_WEBHOOK_URL)."""
    import json

    from app import create_app
    from app.domain.system.alerts import configured_channels, send_admin_alert

    app = create_app()
    with app.app_context():
        channels = configured_channels()
        if not channels["email"] and not channels["webhook"]:
            print("Kein Kanal konfiguriert (ADMIN_ALERT_EMAIL und ADMIN_ALERT_WEBHOOK_URL sind leer).")
            return 1
        result = send_admin_alert("Astra: Testnachricht", "Das ist eine Testnachricht der Admin-Benachrichtigung.")
    print(json.dumps(result))
    return 0 if all(v is not False for v in result.values()) else 1


def cmd_alert_check(args):
    """Prueft die Betriebsausloeser und meldet Stoerungen (unabhaengig vom Billing-Tick, z.B. per Cron)."""
    import json

    from app import create_app
    from app.domain.system.alerts import check_alerts

    app = create_app()
    with app.app_context():
        result = check_alerts()
    print(json.dumps(result))
    return 0


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

    # ── import-blueprint ────────────────────────────────
    ip = subparsers.add_parser(
        "import-blueprint", help="Importiert ein Pterodactyl/Pelican-Egg als Blueprint"
    )
    ip.add_argument("file", help="Pfad zur Egg- oder Blueprint-Datei (.json, .yaml)")

    # ── billing-tick (M46) ──────────────────────────────
    subparsers.add_parser(
        "billing-tick", help="Billing-Tick: Laufzeiten durchsetzen (idempotent, alle paar Minuten ausfuehren)"
    )

    # ── cleanup-jobs ────────────────────────────────────
    p_cleanup = subparsers.add_parser(
        "cleanup-jobs", help="Loescht beendete Job-Eintraege (completed/failed), die aelter als N Tage sind"
    )
    p_cleanup.add_argument("--days", type=int, default=30, help="Aufbewahrung in Tagen (Standard 30)")
    p_cleanup.add_argument("--dry-run", action="store_true", help="Nur zaehlen, nichts loeschen")

    # ── alert-test / alert-check ─────────────────────────
    subparsers.add_parser("alert-test", help="Testnachricht an die Admin-Benachrichtigungskanaele senden")
    subparsers.add_parser(
        "alert-check", help="Betriebsausloeser pruefen und melden (z.B. per Cron, unabhaengig vom Billing-Tick)"
    )

    # ── check-config ────────────────────────────────────
    subparsers.add_parser("check-config", help="Prueft die Konfiguration")

    # ── db-init ─────────────────────────────────────────
    subparsers.add_parser("db-init", help="Datenbank anlegen/migrieren (idempotent, fuer AUTO_MIGRATE)")

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
        "import-blueprint": cmd_import_blueprint,
        "billing-tick": cmd_billing_tick,
        "cleanup-jobs": cmd_cleanup_jobs,
        "alert-test": cmd_alert_test,
        "alert-check": cmd_alert_check,
        "check-config": cmd_check_config,
        "db-init": cmd_db_init,
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
