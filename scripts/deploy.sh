#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra – Deploy-Skript (Produktion, auf dem Panel-Server ausfuehren)
#
# Verwendung:
#   ./scripts/deploy.sh                 Build + Start/Update aller Container
#   ./scripts/deploy.sh --bootstrap     zusaetzlich ersten Admin anlegen (ADMIN_* aus .env)
#   ./scripts/deploy.sh --no-build      nur neu starten, ohne Images zu bauen
#   ./scripts/deploy.sh --status        Status, Health und Logs-Hinweis
#
# Voraussetzungen: Docker + Compose-Plugin, .env aus .env.prod.example,
# DNS fuer PANEL_DOMAIN (und optional NODE_DOMAIN) zeigt auf diesen Server.
# ══════════════════════════════════════════════════════════

set -euo pipefail

cd "$(dirname "$0")/.."

log()  { echo "[deploy] $(date '+%H:%M:%S') $*"; }
die()  { echo "[deploy] FEHLER: $*" >&2; exit 1; }

BOOTSTRAP=false
BUILD=true
STATUS_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --bootstrap) BOOTSTRAP=true ;;
        --no-build)  BUILD=false ;;
        --status)    STATUS_ONLY=true ;;
        -h|--help)   sed -n 2,15p "$0"; exit 0 ;;
        *) die "Unbekannte Option: $arg" ;;
    esac
done

# ── Voraussetzungen ─────────────────────────────────────
command -v docker >/dev/null || die "Docker ist nicht installiert (siehe docs/deploy-runbook.md)."
docker compose version >/dev/null 2>&1 || die "Docker Compose Plugin fehlt."
[ -f .env ] || die ".env fehlt. Erzeugen mit: cp .env.prod.example .env && nano .env"

# .env laden (nur fuer dieses Skript; Compose liest sie selbst)
set -a; # shellcheck disable=SC1091
source .env; set +a

export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

for var in PANEL_DOMAIN SECRET_KEY JWT_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD; do
    val="${!var:-}"
    [ -n "$val" ] || die "$var ist in .env nicht gesetzt."
    [ "$val" != "change-me" ] || die "$var steht noch auf 'change-me'. Bitte Secret setzen."
done

if $STATUS_ONLY; then
    docker compose ps
    echo
    log "Health: $(curl -fsS -m 5 "https://${PANEL_DOMAIN}/health" 2>/dev/null || echo 'nicht erreichbar')"
    log "Logs:   docker compose logs -f backend caddy"
    exit 0
fi

# ── Caddy-Site fuer den Wings-Node (optional) ───────────
mkdir -p deploy/sites
if [ -n "${NODE_DOMAIN:-}" ]; then
    sed "s/__NODE_DOMAIN__/${NODE_DOMAIN}/" deploy/node.caddy.template > deploy/sites/node.caddy
    log "Caddy-Site fuer Wings-Node erzeugt: ${NODE_DOMAIN} -> host:8080"
else
    rm -f deploy/sites/node.caddy
    log "NODE_DOMAIN leer – kein Wings-Proxy ueber Caddy."
fi

# ── Caddy-Site fuer Weiterleitungs-Domains (optional, M75) ──
# REDIRECT_DOMAINS: kommagetrennt, z.B. "www.astrahost.ch,astrahost.gg,www.astrahost.gg" -> 301 auf https://PANEL_DOMAIN
REDIRECT_LIST=""
IFS=',' read -ra _redirects <<< "${REDIRECT_DOMAINS:-}"
for d in "${_redirects[@]:-}"; do
    d="$(echo "$d" | tr -d '[:space:]')"
    [ -n "$d" ] || continue
    [[ "$d" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || die "REDIRECT_DOMAINS: '$d' ist kein gueltiger Domainname."
    [ "$d" != "$PANEL_DOMAIN" ] || die "REDIRECT_DOMAINS enthaelt PANEL_DOMAIN ($d) – das waere eine Weiterleitungsschleife."
    [ "$d" != "${NODE_DOMAIN:-}" ] || die "REDIRECT_DOMAINS enthaelt NODE_DOMAIN ($d)."
    REDIRECT_LIST="${REDIRECT_LIST:+$REDIRECT_LIST, }$d"
done
if [ -n "$REDIRECT_LIST" ]; then
    sed "s/__REDIRECT_DOMAINS__/${REDIRECT_LIST}/" deploy/redirect.caddy.template > deploy/sites/redirect.caddy
    log "Caddy-Site fuer Weiterleitungen erzeugt: ${REDIRECT_LIST} -> https://${PANEL_DOMAIN}"
else
    rm -f deploy/sites/redirect.caddy
    log "REDIRECT_DOMAINS leer – keine Weiterleitungs-Domains."
fi

mkdir -p backups/postgres

# ── Build + Start ───────────────────────────────────────
if $BUILD; then
    log "Baue Images (backend, frontend) ..."
    docker compose build --pull backend frontend
fi

log "Starte Container ..."
docker compose up -d --remove-orphans

# ── Warten bis Backend bereit ───────────────────────────
log "Warte auf Backend (Migrationen laufen automatisch) ..."
for i in $(seq 1 60); do
    if docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health/ready', timeout=3)" >/dev/null 2>&1; then
        log "Backend bereit."
        break
    fi
    if [ "$i" -eq 60 ]; then
        docker compose logs --tail=50 backend
        die "Backend wurde nicht bereit. Logs oben pruefen."
    fi
    sleep 3
done

# ── Bootstrap-Admin ─────────────────────────────────────
if $BOOTSTRAP; then
    log "Lege Admin '${ADMIN_USERNAME:-admin}' an ..."
    docker compose exec -T backend ./entrypoint.sh seed
    log "WICHTIG: Admin-Passwort nach dem ersten Login aendern!"
fi

# ── Zusammenfassung ─────────────────────────────────────
docker compose exec -T backend python cli.py check-config || log "WARNUNG: check-config meldet Probleme (siehe oben)."
echo
docker compose ps
echo
log "Panel:  https://${PANEL_DOMAIN}"
[ -n "${NODE_DOMAIN:-}" ] && log "Node:   https://${NODE_DOMAIN}  (Wings auf dem Host, Port 8080, siehe scripts/install-wings.sh)"
log "Logs:   docker compose logs -f backend caddy"
log "Smoke:  ./scripts/smoke-test.sh https://${PANEL_DOMAIN}"
