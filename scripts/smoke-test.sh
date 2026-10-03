#!/bin/bash
# ══════════════════════════════════════════════════════════
# Astra – Smoke-Test gegen ein laufendes Panel
#
# Verwendung:
#   ./scripts/smoke-test.sh https://panel.example.com [ADMIN_USER] [ADMIN_PASSWORD]
#
# Ohne Login-Daten werden nur die oeffentlichen Checks ausgefuehrt.
# Mit Admin-Login werden zusaetzlich Agents gelistet und fuer jeden Agent
# mit Credentials die Wings Remote-API-Authentifizierung geprueft.
# Benoetigt: curl, python3
# ══════════════════════════════════════════════════════════

set -uo pipefail

PANEL="${1:?Panel-URL fehlt, z.B. https://panel.example.com}"
ADMIN_USER="${2:-}"
ADMIN_PASS="${3:-}"
PANEL="${PANEL%/}"

PASSED=0; FAILED=0
ok()   { PASSED=$((PASSED+1)); echo "  OK   $1"; }
fail() { FAILED=$((FAILED+1)); echo "  FAIL $1${2:+ – $2}"; }

code() { curl -s -o /dev/null -w '%{http_code}' -m 10 "$@"; }
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1" 2>/dev/null; }

echo "=== Oeffentliche Checks: $PANEL ==="

c=$(code "$PANEL/health")
[ "$c" = "200" ] && ok "GET /health -> 200" || fail "GET /health" "HTTP $c"

c=$(code "$PANEL/health/ready")
[ "$c" = "200" ] && ok "GET /health/ready -> 200" || fail "GET /health/ready" "HTTP $c"

c=$(code "$PANEL/")
[ "$c" = "200" ] && ok "Frontend / -> 200" || fail "Frontend /" "HTTP $c"

if [[ "$PANEL" == https://* ]]; then
    if curl -fsS -m 10 -o /dev/null "$PANEL/health"; then ok "TLS-Zertifikat gueltig"; else fail "TLS-Zertifikat" "curl lehnt ab"; fi
    c=$(code "${PANEL/https:/http:}/health")
    { [ "$c" = "308" ] || [ "$c" = "301" ] || [ "$c" = "200" ]; } && ok "HTTP -> HTTPS Redirect (HTTP $c)" || fail "HTTP-Redirect" "HTTP $c"
fi

c=$(code "$PANEL/api/remote/servers")
[ "$c" = "401" ] && ok "Remote-API ohne Token -> 401" || fail "Remote-API ohne Token" "HTTP $c (erwartet 401)"

c=$(code -H "Authorization: Bearer falsch.token" "$PANEL/api/remote/servers")
[ "$c" = "403" ] && ok "Remote-API mit falschem Token -> 403" || fail "Remote-API falscher Token" "HTTP $c (erwartet 403)"

c=$(code "$PANEL/api/admin/agents")
{ [ "$c" = "401" ] || [ "$c" = "403" ]; } && ok "Admin-API ohne Login -> $c" || fail "Admin-API ohne Login" "HTTP $c (erwartet 401/403) – Admin-Guard pruefen!"

if [ -z "$ADMIN_USER" ]; then
    echo
    echo "Hinweis: Admin-Login nicht angegeben, Agent-/Remote-Checks uebersprungen."
else
    echo
    echo "=== Admin-Checks als '$ADMIN_USER' ==="
    TOKEN=$(curl -s -m 10 -H 'Content-Type: application/json' \
        -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
        "$PANEL/api/auth/login" | json "d.get('access_token','')")
    if [ -z "$TOKEN" ]; then
        fail "Login" "kein access_token erhalten"
    else
        ok "Login erfolgreich"
        AUTH=(-H "Authorization: Bearer $TOKEN")

        AGENTS=$(curl -s -m 10 "${AUTH[@]}" "$PANEL/api/admin/agents")
        COUNT=$(echo "$AGENTS" | json "len(d)")
        [ -n "$COUNT" ] && ok "GET /api/admin/agents -> $COUNT Agent(s)" || fail "GET /api/admin/agents" "keine Liste"

        for ID in $(echo "$AGENTS" | json "' '.join(str(a['id']) for a in d if a.get('has_daemon_credentials'))"); do
            CFG=$(curl -s -m 10 "${AUTH[@]}" "$PANEL/api/admin/agents/$ID/configuration")
            NAME=$(echo "$AGENTS" | json "[a['name'] for a in d if a['id']==$ID][0]")
            TID=$(echo "$CFG" | json "d['config']['token_id']")
            TOK=$(echo "$CFG" | json "d['config']['token']")
            REMOTE=$(echo "$CFG" | json "d['config']['remote']")
            [ "$REMOTE" = "$PANEL" ] && ok "Agent '$NAME': config.yml remote = $REMOTE" || fail "Agent '$NAME': remote" "$REMOTE != $PANEL (BASE_URL pruefen)"
            c=$(code -H "Authorization: Bearer $TID.$TOK" "$PANEL/api/remote/servers")
            [ "$c" = "200" ] && ok "Agent '$NAME': Node-Token an Remote-API -> 200" || fail "Agent '$NAME': Node-Token" "HTTP $c"
            LAST=$(curl -s -m 10 "${AUTH[@]}" "$PANEL/api/admin/agents/$ID/monitoring" | json "d.get('health_status', d.get('health',{}).get('health_status','?'))")
            echo "       Health laut Panel: $LAST"
        done

        READY=$(curl -s -m 10 "${AUTH[@]}" "$PANEL/api/admin/health/detailed" | json "d.get('status')")
        [ "$READY" = "ok" ] && ok "GET /api/admin/health/detailed -> ok" || fail "health/detailed" "status=$READY"
    fi
fi

echo
echo "=== Ergebnis: $PASSED OK, $FAILED FAIL ==="
[ "$FAILED" -eq 0 ]
