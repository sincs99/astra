#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra Backend – Entrypoint
# Unterstuetzte Befehle:
#   serve       – Startet Gunicorn (Produktion) oder Flask Dev-Server
#   migrate     – Fuehrt DB-Migrationen aus
#   seed        – Erstellt initialen Admin-User
#   shell       – Startet Flask-Shell
#   healthcheck – Prueft ob die App bereit ist
# ══════════════════════════════════════════════════════════

set -e

APP_ENV="${APP_ENV:-development}"
PORT="${PORT:-5000}"
WORKERS="${GUNICORN_WORKERS:-4}"

log() {
    echo "[entrypoint] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# ── Migrationen ─────────────────────────────────────────
run_migrate() {
    log "Starte Datenbankmigrationen..."
    flask db upgrade
    RESULT=$?
    if [ $RESULT -ne 0 ]; then
        log "FEHLER: Migration fehlgeschlagen (Exit-Code: $RESULT)"
        log "Bitte pruefen Sie die Migrationsdateien und die Datenbank."
        exit $RESULT
    fi
    log "Migrationen erfolgreich abgeschlossen."
}

# ── Seed / Bootstrap ───────────────────────────────────
run_seed() {
    log "Starte Bootstrap (Admin-Erzeugung)..."
    python cli.py bootstrap \
        --username "${ADMIN_USERNAME:-admin}" \
        --email "${ADMIN_EMAIL:-admin@astra.local}" \
        --password "${ADMIN_PASSWORD:-admin}"
    log "Bootstrap abgeschlossen."
}

# ── Server starten ──────────────────────────────────────
run_serve() {
    # Optional: Migrationen automatisch ausfuehren
    if [ "${AUTO_MIGRATE:-false}" = "true" ]; then
        run_migrate
    fi

    if [ "$APP_ENV" = "production" ]; then
        log "Starte Gunicorn (Produktion) auf Port $PORT mit $WORKERS Workers..."
        exec gunicorn \
            --bind "0.0.0.0:$PORT" \
            --workers "$WORKERS" \
            --timeout 120 \
            --access-logfile - \
            --error-logfile - \
            --log-level info \
            "run:app"
    else
        log "Starte Flask Development Server auf Port $PORT..."
        exec flask run --host=0.0.0.0 --port="$PORT"
    fi
}

# ── Hauptprogramm ──────────────────────────────────────
CMD="${1:-serve}"

case "$CMD" in
    serve)
        run_serve
        ;;
    migrate)
        run_migrate
        ;;
    seed|bootstrap)
        run_seed
        ;;
    shell)
        log "Starte Flask Shell..."
        exec flask shell
        ;;
    healthcheck)
        python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/health')"
        ;;
    *)
        log "Unbekannter Befehl: $CMD"
        log "Verfuegbar: serve | migrate | seed | shell | healthcheck"
        exec "$@"
        ;;
esac
