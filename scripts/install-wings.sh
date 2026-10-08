#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra – Wings-Node einrichten (auf dem NODE ausfuehren, als root)
#
# Installiert Wings, holt die config.yml aus dem Astra-Panel und richtet Wings als
# systemd-Dienst ein. Docker muss vorhanden sein (oder mit --install-docker installiert werden).
#
# Verwendung:
#   sudo ./scripts/install-wings.sh --panel https://panel.example.com --agent-id 1 \
#        --token <ADMIN-JWT-oder-API-Key>
#
#   oder mit fertiger config.yml:
#   sudo ./scripts/install-wings.sh --config /pfad/config.yml
#
# Den Admin-Token bekommst du per Login:
#   curl -s -H 'Content-Type: application/json' \
#        -d '{"username":"admin","password":"..."}' https://panel.example.com/api/auth/login
#   (Feld access_token) – oder ueber einen API-Key aus dem Panel.
#
# Optionen:
#   --pelican          Pelican-Wings statt Pterodactyl-Wings installieren
#   --install-docker   Docker mit get.docker.com installieren, wenn es fehlt (ohne diese Option
#                      wird nichts am System installiert; fehlt Docker, bricht das Skript ab)
#   --grub-swapaccount swapaccount=1 in /etc/default/grub setzen (nur cgroup v1 noetig,
#                      wirkt nach Reboot; ohne Option gibt es nur einen Hinweis)
#   --no-docker        veraltet, ohne Wirkung (Docker wird seit M78 nie mehr automatisch installiert)
#   --no-start         Wings nur installieren, nicht starten
# ══════════════════════════════════════════════════════════

set -euo pipefail

log() { echo "[wings] $(date '+%H:%M:%S') $*"; }
die() { echo "[wings] FEHLER: $*" >&2; exit 1; }

PANEL=""; AGENT_ID=""; TOKEN=""; CONFIG_SRC=""
FLAVOR="pterodactyl"; INSTALL_DOCKER=false; GRUB_SWAP=false; START=true

while [ $# -gt 0 ]; do
    case "$1" in
        --panel)     PANEL="${2%/}"; shift 2 ;;
        --agent-id)  AGENT_ID="$2"; shift 2 ;;
        --token)     TOKEN="$2"; shift 2 ;;
        --config)    CONFIG_SRC="$2"; shift 2 ;;
        --pelican)   FLAVOR="pelican"; shift ;;
        --install-docker)   INSTALL_DOCKER=true; shift ;;
        --grub-swapaccount) GRUB_SWAP=true; shift ;;
        --no-docker) shift ;;  # veraltet: ist seit M78 der Standard
        --no-start)  START=false; shift ;;
        -h|--help)   sed -n 2,34p "$0"; exit 0 ;;
        *) die "Unbekannte Option: $1" ;;
    esac
done

[ "$(id -u)" -eq 0 ] || die "Bitte als root ausfuehren (sudo)."
[ -n "$CONFIG_SRC" ] || { [ -n "$PANEL" ] && [ -n "$AGENT_ID" ] && [ -n "$TOKEN" ]; } \
    || die "Entweder --config <datei> oder --panel + --agent-id + --token angeben."

if [ "$FLAVOR" = "pelican" ]; then
    CONF_DIR=/etc/pelican
    RELEASE_URL="https://github.com/pelican-dev/wings/releases/latest/download"
else
    CONF_DIR=/etc/pterodactyl
    RELEASE_URL="https://github.com/pterodactyl/wings/releases/latest/download"
fi

# ── Voraussetzungen ─────────────────────────────────────
command -v curl >/dev/null || die "curl fehlt."
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  WINGS_ARCH=amd64 ;;
    aarch64|arm64) WINGS_ARCH=arm64 ;;
    *) die "Nicht unterstuetzte Architektur: $ARCH" ;;
esac

# ── Docker ──────────────────────────────────────────────
# Es wird nichts still installiert oder umkonfiguriert: Docker nur mit --install-docker,
# GRUB nur mit --grub-swapaccount.
if ! command -v docker >/dev/null; then
    if $INSTALL_DOCKER; then
        log "Installiere Docker (get.docker.com) ..."
        curl -fsSL https://get.docker.com | sh
    else
        die "Docker fehlt. Installiere Docker selbst (https://docs.docker.com/engine/install/) oder starte dieses Skript mit --install-docker."
    fi
else
    log "Docker vorhanden: $(docker --version)"
fi
if ! systemctl is-active --quiet docker; then
    if $INSTALL_DOCKER; then
        systemctl enable --now docker
    else
        die "Der Docker-Dienst laeuft nicht. Starte ihn (systemctl enable --now docker) oder nutze --install-docker."
    fi
fi
# Swap-Accounting fuer Wings-Speicherlimits: nur auf cgroup v1 noetig (cgroup v2, z.B. Ubuntu 22.04+, braucht nichts)
if [ "$(stat -fc %T /sys/fs/cgroup 2>/dev/null || true)" != "cgroup2fs" ] && ! grep -q "swapaccount=1" /proc/cmdline; then
    if $GRUB_SWAP && [ -f /etc/default/grub ]; then
        if ! grep -q "swapaccount=1" /etc/default/grub; then
            sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 swapaccount=1"/' /etc/default/grub
            command -v update-grub >/dev/null && update-grub >/dev/null 2>&1 || true
            log "swapaccount=1 in GRUB gesetzt (wirkt nach Reboot)."
        fi
    else
        log "Hinweis: cgroup v1 ohne swapaccount=1 – Speicherlimits mit Swap greifen evtl. nicht. Mit --grub-swapaccount setzt das Skript es in GRUB (Reboot noetig)."
    fi
fi

# ── Wings-Binary ────────────────────────────────────────
log "Lade Wings ($FLAVOR, $WINGS_ARCH) ..."
mkdir -p "$CONF_DIR"
curl -fL -o /usr/local/bin/wings "${RELEASE_URL}/wings_linux_${WINGS_ARCH}"
chmod u+x /usr/local/bin/wings
log "Wings: $(/usr/local/bin/wings version 2>/dev/null | head -1 || echo 'installiert')"

# ── config.yml ──────────────────────────────────────────
if [ -n "$CONFIG_SRC" ]; then
    cp "$CONFIG_SRC" "$CONF_DIR/config.yml"
    log "config.yml aus $CONFIG_SRC uebernommen."
else
    log "Hole config.yml fuer Agent $AGENT_ID von $PANEL ..."
    RESP=$(curl -fsS -m 15 -H "Authorization: Bearer $TOKEN" "$PANEL/api/admin/agents/$AGENT_ID/configuration") \
        || die "config.yml konnte nicht geladen werden (Token, Agent-ID, Panel-URL pruefen)."
    # Hinweis: Heredoc und Here-String zugleich funktionieren nicht (die Antwort wuerde als Python-Code gelesen)
    printf '%s' "$RESP" | python3 -c 'import json, sys; open(sys.argv[1], "w").write(json.load(sys.stdin)["yaml"])' "$CONF_DIR/config.yml" \
        || die "Antwort des Panels konnte nicht gelesen werden."
    log "config.yml geschrieben."
fi
chmod 600 "$CONF_DIR/config.yml"

REMOTE=$(grep -E '^remote:' "$CONF_DIR/config.yml" | awk '{print $2}')
SFTP_PORT=$(grep -E 'bind_port:' "$CONF_DIR/config.yml" | awk '{print $2}')
API_PORT=$(grep -E '^\s+port:' "$CONF_DIR/config.yml" | head -1 | awk '{print $2}')
DATA_DIR=$(grep -E '^\s+data:' "$CONF_DIR/config.yml" | awk '{print $2}')
mkdir -p "${DATA_DIR:-/var/lib/pterodactyl/volumes}"

# ── systemd ─────────────────────────────────────────────
cat > /etc/systemd/system/wings.service <<UNIT
[Unit]
Description=Wings Daemon (Astra Node)
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
User=root
WorkingDirectory=$CONF_DIR
LimitNOFILE=4096
PIDFile=/var/run/wings/daemon.pid
ExecStart=/usr/local/bin/wings
Restart=on-failure
StartLimitInterval=180
StartLimitBurst=30
RestartSec=5s

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload

if $START; then
    systemctl enable --now wings
    sleep 3
    if systemctl is-active --quiet wings; then
        log "Wings laeuft."
    else
        journalctl -u wings --no-pager -n 30
        die "Wings startet nicht. Logs oben pruefen (haeufig: Token/remote in config.yml, Port belegt, Docker)."
    fi
else
    systemctl enable wings
    log "Wings installiert, nicht gestartet (--no-start)."
fi

# ── Zusammenfassung ─────────────────────────────────────
echo
log "Panel (remote):   ${REMOTE:-?}"
log "Wings-API-Port:   ${API_PORT:-8080}  (muss vom Panel erreichbar sein, bzw. via Caddy-NODE_DOMAIN)"
log "SFTP-Port:        ${SFTP_PORT:-2022}  (eingehend offen fuer Kunden)"
log "Datenverzeichnis: ${DATA_DIR:-?}"
log "Logs:             journalctl -u wings -f"
log "Firewall-Beispiel (ufw): ufw allow ${API_PORT:-8080}/tcp; ufw allow ${SFTP_PORT:-2022}/tcp; ufw allow 25565:25600/tcp"
