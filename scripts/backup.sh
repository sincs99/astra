#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra – Backup-Skript
#
# Sichert:
#   - PostgreSQL-Datenbank
#   - .env Konfiguration
#   - Uploads (falls vorhanden)
#
# Verwendung:
#   ./scripts/backup.sh [BACKUP_DIR]
#
# Standard-Backup-Verzeichnis: ./backups/
# ══════════════════════════════════════════════════════════

set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="astra_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Umgebungsvariablen laden
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

POSTGRES_USER="${POSTGRES_USER:-astra}"
POSTGRES_DB="${POSTGRES_DB:-astra}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

log() {
    echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log "Backup wird erstellt: ${BACKUP_PATH}"
mkdir -p "${BACKUP_PATH}"

# ── 1. PostgreSQL-Dump ──────────────────────────────────
log "Erstelle PostgreSQL-Dump..."
if command -v pg_dump &> /dev/null; then
    pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --format=custom \
        --file="${BACKUP_PATH}/database.dump" \
        2>&1 || {
        log "WARNUNG: pg_dump fehlgeschlagen. Versuche Docker-Variante..."
        docker compose exec -T postgres pg_dump \
            -U "${POSTGRES_USER}" \
            -d "${POSTGRES_DB}" \
            --format=custom \
            > "${BACKUP_PATH}/database.dump" 2>&1 || {
            log "FEHLER: Datenbank-Backup fehlgeschlagen!"
        }
    }
else
    log "pg_dump nicht lokal verfuegbar, nutze Docker..."
    docker compose exec -T postgres pg_dump \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --format=custom \
        > "${BACKUP_PATH}/database.dump" 2>&1 || {
        log "FEHLER: Datenbank-Backup fehlgeschlagen!"
    }
fi

# ── 2. Konfigurationsdateien ───────────────────────────
log "Sichere Konfigurationsdateien..."
if [ -f .env ]; then
    cp .env "${BACKUP_PATH}/env.bak"
fi
if [ -f backend/.env ]; then
    cp backend/.env "${BACKUP_PATH}/backend_env.bak"
fi
if [ -f docker-compose.yml ]; then
    cp docker-compose.yml "${BACKUP_PATH}/docker-compose.yml.bak"
fi
if [ -f docker-compose.prod.yml ]; then
    cp docker-compose.prod.yml "${BACKUP_PATH}/docker-compose.prod.yml.bak"
fi

# ── 3. Uploads (falls vorhanden) ───────────────────────
if [ -d backend/uploads ]; then
    log "Sichere Uploads..."
    cp -r backend/uploads "${BACKUP_PATH}/uploads"
fi

# ── 4. Archiv erstellen ────────────────────────────────
log "Erstelle Archiv..."
cd "${BACKUP_DIR}"
tar czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"

log "Backup erfolgreich: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# ── 5. Alte Backups bereinigen (optional, Standard: 30 Tage)
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
log "Bereinige Backups aelter als ${RETENTION_DAYS} Tage..."
find "${BACKUP_DIR}" -name "astra_backup_*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete 2>/dev/null || true

log "Backup abgeschlossen."
