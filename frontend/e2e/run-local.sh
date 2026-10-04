#!/usr/bin/env bash
# Startet Backend (SQLite, Stub-Runner, manuelle Zahlung) und Frontend-Preview und fuehrt e2e/flow.mjs aus.
# Voraussetzungen: Python-Umgebung mit backend/requirements.txt (PYTHON=...), npm ci, Frontend wird bei jedem Lauf gebaut,
# Chromium (CHROMIUM_PATH, Standard /opt/pw-browsers/chromium).
set -euo pipefail
set -m  # Job-Kontrolle: jeder Hintergrundprozess bekommt eine eigene Prozessgruppe (sauberes Aufraeumen)

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
WORK="$(mktemp -d)"
BACKEND_PORT="${BACKEND_PORT:-5000}"
FRONTEND_PORT="${FRONTEND_PORT:-4190}"
ADMIN_PASSWORD="${E2E_ADMIN_PASSWORD:-adminpass123}"

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

export APP_ENV=development
export SECRET_KEY=e2e-secret JWT_SECRET_KEY=e2e-jwt-secret-key-with-enough-length-32b
export DATABASE_URL="sqlite:///$WORK/e2e.db"
export RUNNER_ADAPTER=stub PAYMENT_PROVIDER=manual REGISTRATION_ENABLED=true EMAIL_VERIFICATION_REQUIRED=false

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if curl -s -o /dev/null "http://127.0.0.1:$port/"; then echo "[e2e] Port $port ist belegt, bitte freigeben"; exit 1; fi
done

echo "[e2e] Backend vorbereiten (DB: $WORK/e2e.db)"
(cd "$ROOT/backend" && "$PYTHON" cli.py bootstrap --username admin --email admin@e2e.local --password "$ADMIN_PASSWORD" >/dev/null)

echo "[e2e] Backend starten (Port $BACKEND_PORT)"
(cd "$ROOT/backend" && "$PYTHON" -c "from app import create_app; create_app().run(host='127.0.0.1', port=$BACKEND_PORT, debug=False)" >"$WORK/backend.log" 2>&1) &
pids+=($!)

cd "$ROOT/frontend"
npm run build >/dev/null
echo "[e2e] Frontend starten (Port $FRONTEND_PORT)"
npx vite preview --port "$FRONTEND_PORT" --strictPort >"$WORK/frontend.log" 2>&1 &
pids+=($!)

for url in "http://127.0.0.1:$BACKEND_PORT/health" "http://127.0.0.1:$FRONTEND_PORT/"; do
  for _ in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && break
    sleep 0.5
  done
  curl -fsS "$url" >/dev/null || { echo "[e2e] $url nicht erreichbar"; tail -20 "$WORK"/*.log; exit 1; }
done

E2E_BASE_URL="http://localhost:$FRONTEND_PORT" E2E_API_URL="http://localhost:$BACKEND_PORT/api" \
E2E_ADMIN_PASSWORD="$ADMIN_PASSWORD" node e2e/flow.mjs || { echo "[e2e] FEHLGESCHLAGEN, Backend-Log:"; tail -30 "$WORK/backend.log"; exit 1; }
