#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra – Restore-Skript
#
# Stellt ein Backup wieder her:
#   - PostgreSQL-Datenbank
#   - Konfigurationsdateien (optional)
#   - Uploads (optional)
#
# Verwendung:
#   ./scripts/restore.sh <BACKUP_ARCHIV>
#
# Beispiel:
#   ./scripts/restore.sh ./backups/astra_backup_20260313_120000.tar.gz
# ══════════════════════════════════════════════════════════

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Verwendung: $0 <BACKUP_ARCHIV>"
    echo "Beispiel: $0 ./backups/astra_backup_20260313_120000.tar.gz"
    exit 1
fi

ARCHIVE="$1"
TEMP_DIR=$(mktemp -d)

# Umgebungsvariablen laden
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-astra}"
POSTGRES_DB="${POSTGRES_DB:-astra}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

log() {
    echo "[restore] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

log "Restore aus: ${ARCHIVE}"

# ── 1. Archiv entpacken ────────────────────────────────
log "Entpacke Archiv..."
tar xzf "${ARCHIVE}" -C "${TEMP_DIR}"
BACKUP_DIR=$(ls "${TEMP_DIR}" | head -1)
RESTORE_PATH="${TEMP_DIR}/${BACKUP_DIR}"

if [ ! -d "${RESTORE_PATH}" ]; then
    log "FEHLER: Backup-Verzeichnis nicht gefunden in Archiv."
    exit 1
fi

# ── 2. Datenbank wiederherstellen ──────────────────────
if [ -f "${RESTORE_PATH}/database.dump" ]; then
    log "Stelle Datenbank wieder her..."
    log "WARNUNG: Bestehende Daten werden ueberschrieben!"

    if command -v pg_restore &> /dev/null; then
        pg_restore \
            -h "${POSTGRES_HOST}" \
            -p "${POSTGRES_PORT}" \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            --clean \
            --if-exists \
            "${RESTORE_PATH}/database.dump" 2>&1 || {
            log "WARNUNG: pg_restore mit Warnungen abgeschlossen (kann normal sein)."
        }
    else
        log "pg_restore nicht lokal verfuegbar, nutze Docker..."
        docker compose exec -T postgres pg_restore \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            --clean \
            --if-exists \
            < "${RESTORE_PATH}/database.dump" 2>&1 || {
            log "WARNUNG: pg_restore mit Warnungen abgeschlossen."
        }
    fi
    log "Datenbank wiederhergestellt."
else
    log "Kein Datenbank-Dump im Backup gefunden."
fi

# ── 3. Konfiguration wiederherstellen (nur Info) ──────
if [ -f "${RESTORE_PATH}/env.bak" ]; then
    log "Konfigurationsdatei gefunden: ${RESTORE_PATH}/env.bak"
    log "HINWEIS: .env wird NICHT automatisch ueberschrieben."
    log "         Manuell pruefen: diff .env ${RESTORE_PATH}/env.bak"
fi

# ── 4. Uploads wiederherstellen ────────────────────────
if [ -d "${RESTORE_PATH}/uploads" ]; then
    log "Uploads gefunden. Stelle wieder her..."
    mkdir -p backend/uploads
    cp -r "${RESTORE_PATH}/uploads/"* backend/uploads/ 2>/dev/null || true
    log "Uploads wiederhergestellt."
fi

log "Restore abgeschlossen."
log "Empfehlung: Backend neu starten und Migrationen pruefen."
