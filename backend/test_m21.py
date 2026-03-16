"""Schnelltests fuer Meilenstein 21 – Deployment & Operations Readiness.

Deckt ab:
a) Config / Environment
b) Startup / Bootstrap
c) Health / Readiness
d) Proxy / URL-Building
e) Security Headers / Rate Limiting
f) Ops-Endpunkte
g) Regression (M10-M20 Kompatibilitaet)
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

# Sicherstellen, dass wir im Testing-Modus starten
os.environ["APP_ENV"] = "testing"

from app import create_app, build_base_url, build_websocket_url, bootstrap_admin, __version__
from app.config import Config, DevelopmentConfig, ProductionConfig, TestingConfig, config_by_name
from app.extensions import db

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  OK {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {label} - {detail}")


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


# ================================================================
# Config / Environment Tests
# ================================================================

print("\n=== a) Config / Environment ===")

# Pruefe dass config_by_name alle Umgebungen enthaelt
check("config_by_name hat development", "development" in config_by_name)
check("config_by_name hat production", "production" in config_by_name)
check("config_by_name hat testing", "testing" in config_by_name)

# Testing-Config
check("TestingConfig.TESTING ist True", TestingConfig.TESTING is True)
check("TestingConfig.SQLALCHEMY_DATABASE_URI ist memory",
      TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:")
check("TestingConfig.RATELIMIT_ENABLED ist False", TestingConfig.RATELIMIT_ENABLED is False)
check("TestingConfig.SECRET_KEY ist nicht default",
      TestingConfig.SECRET_KEY != "dev-secret-key")
check("TestingConfig.JWT_SECRET_KEY ist nicht default",
      TestingConfig.JWT_SECRET_KEY != "dev-jwt-secret-key")
check("TestingConfig.APP_ENV ist testing", TestingConfig.APP_ENV == "testing")

# Development-Config
check("DevelopmentConfig.DEBUG ist True", DevelopmentConfig.DEBUG is True)
check("DevelopmentConfig.APP_ENV ist development", DevelopmentConfig.APP_ENV == "development")

# Production-Config
check("ProductionConfig.DEBUG ist False", ProductionConfig.DEBUG is False)
check("ProductionConfig.APP_ENV ist production", ProductionConfig.APP_ENV == "production")
check("ProductionConfig.PROXY_FIX_ENABLED ist True (default in Prod)",
      ProductionConfig.PROXY_FIX_ENABLED is True)
check("ProductionConfig.SESSION_COOKIE_SECURE ist True (default in Prod)",
      ProductionConfig.SESSION_COOKIE_SECURE is True)

# Production-Validierung
prod_issues = ProductionConfig.validate_production()
check("Production-Validierung erkennt unsicheren SECRET_KEY",
      any("SECRET_KEY" in i for i in prod_issues))
check("Production-Validierung erkennt unsicheren JWT_SECRET_KEY",
      any("JWT_SECRET_KEY" in i for i in prod_issues))

# Basis-Config Felder vorhanden
check("Config hat REDIS_URL", hasattr(Config, "REDIS_URL"))
check("Config hat WEBHOOK_MAX_RETRIES", hasattr(Config, "WEBHOOK_MAX_RETRIES"))
check("Config hat WEBHOOK_RETRY_DELAYS", hasattr(Config, "WEBHOOK_RETRY_DELAYS"))
check("Config hat WEBHOOK_REQUEST_TIMEOUT", hasattr(Config, "WEBHOOK_REQUEST_TIMEOUT"))
check("Config hat JWT_ACCESS_TOKEN_EXPIRES_HOURS", hasattr(Config, "JWT_ACCESS_TOKEN_EXPIRES_HOURS"))
check("Config hat MFA_ISSUER_NAME", hasattr(Config, "MFA_ISSUER_NAME"))
check("Config hat CORS_ORIGINS", hasattr(Config, "CORS_ORIGINS"))
check("Config hat ALLOWED_HOSTS", hasattr(Config, "ALLOWED_HOSTS"))
check("Config hat BASE_URL", hasattr(Config, "BASE_URL"))
check("Config hat FRONTEND_URL", hasattr(Config, "FRONTEND_URL"))
check("Config hat PROXY_FIX_ENABLED", hasattr(Config, "PROXY_FIX_ENABLED"))
check("Config hat RATELIMIT_ENABLED", hasattr(Config, "RATELIMIT_ENABLED"))
check("Config hat RATELIMIT_AUTH_PER_MINUTE", hasattr(Config, "RATELIMIT_AUTH_PER_MINUTE"))
check("Config hat LOG_LEVEL", hasattr(Config, "LOG_LEVEL"))
check("Config hat MAINTENANCE_MODE", hasattr(Config, "MAINTENANCE_MODE"))
check("Config hat MAX_API_KEYS_PER_USER", hasattr(Config, "MAX_API_KEYS_PER_USER"))

# Config.is_production()
check("Config.is_production() bei development ist False",
      not DevelopmentConfig.is_production())
check("ProductionConfig.is_production() ist True",
      ProductionConfig.is_production())

# Default-Werte sinnvoll
check("WEBHOOK_MAX_RETRIES default ist 3", Config.WEBHOOK_MAX_RETRIES == 3)
check("RATELIMIT_AUTH_PER_MINUTE default ist 20", Config.RATELIMIT_AUTH_PER_MINUTE == 20)
check("JWT_ACCESS_TOKEN_EXPIRES_HOURS default ist 24", Config.JWT_ACCESS_TOKEN_EXPIRES_HOURS == 24)
check("RUNNER_ADAPTER default ist stub", Config.RUNNER_ADAPTER == "stub")


# ================================================================
# App erstellen und Setup
# ================================================================

print("\n=== b) Startup / Bootstrap ===")

app = create_app("testing")

check("App wurde erstellt", app is not None)
check("App hat __version__", __version__ is not None and len(__version__) > 0)
check("App Config TESTING ist True", app.config.get("TESTING") is True)
check("App Config APP_ENV ist testing", app.config.get("APP_ENV") == "testing")

# Setup Datenbank
with app.app_context():
    db.create_all()

    # Bootstrap-Test
    from app.domain.users.models import User

    result = bootstrap_admin(
        username="m21-admin",
        email="m21-admin@test.dev",
        password="testpass123",
    )
    check("Bootstrap erstellt Admin-User", result["created"] is True)
    check("Bootstrap-Nachricht enthaelt Username", "m21-admin" in result["message"])

    # Pruefe ob User tatsaechlich existiert
    admin = User.query.filter_by(username="m21-admin").first()
    check("Admin-User existiert in DB", admin is not None)
    check("Admin-User ist Admin", admin.is_admin is True if admin else False)
    check("Admin-User Passwort funktioniert",
          admin.check_password("testpass123") if admin else False)

    # Doppelter Bootstrap soll keinen neuen User erstellen
    result2 = bootstrap_admin(
        username="m21-admin2",
        email="m21-admin2@test.dev",
        password="testpass",
    )
    check("Zweiter Bootstrap erkennt bestehenden Admin",
          result2["created"] is False)

    # Standard-Testdaten fuer weitere Tests
    user = User(username="m21-user", email="m21@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id  # ID merken fuer spaetere Nutzung ausserhalb Context

    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    agent = Agent(name="m21-agent", fqdn="m21.test.dev")
    db.session.add(agent)
    db.session.flush()

    bp_obj = Blueprint(name="m21-bp")
    db.session.add(bp_obj)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25900)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m21-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp_obj.id,
    )
    db.session.add(inst)
    db.session.commit()
    _inst_id = inst.id


# ================================================================
# Health / Readiness Tests
# ================================================================

print("\n=== c) Health / Readiness ===")

client = app.test_client()

# Liveness
resp = client.get("/health")
check("GET /health -> 200", resp.status_code == 200)
data = resp.get_json()
check("/health gibt status=ok", data.get("status") == "ok")
check("/health gibt service=astra-backend", data.get("service") == "astra-backend")
check("/health enthaelt version", "version" in data)

# Readiness
resp = client.get("/health/ready")
check("GET /health/ready -> 200", resp.status_code == 200)
data = resp.get_json()
check("/health/ready gibt status", "status" in data)
check("/health/ready gibt checks", "checks" in data)
check("/health/ready checks hat database", "database" in data.get("checks", {}))
check("/health/ready checks.database ist ok", data.get("checks", {}).get("database") == "ok")
check("/health/ready gibt version", "version" in data)
check("/health/ready gibt environment", "environment" in data)
check("/health/ready gibt timestamp", "timestamp" in data)

# Ops-Info
resp = client.get("/ops/info")
check("GET /ops/info -> 200", resp.status_code == 200)
data = resp.get_json()
check("/ops/info gibt service", data.get("service") == "astra-backend")
check("/ops/info gibt version", "version" in data)
check("/ops/info gibt environment", "environment" in data)
check("/ops/info gibt runner_adapter", "runner_adapter" in data)
check("/ops/info gibt debug", "debug" in data)
check("/ops/info gibt maintenance_mode", "maintenance_mode" in data)


# ================================================================
# Proxy / URL-Building Tests
# ================================================================

print("\n=== d) Proxy / URL-Building ===")

with app.app_context():
    base = build_base_url(app)
    check("build_base_url gibt String zurueck", isinstance(base, str))
    check("build_base_url enthaelt http", "http" in base)

    ws = build_websocket_url(app)
    check("build_websocket_url gibt String zurueck", isinstance(ws, str))
    check("build_websocket_url enthaelt ws", "ws" in ws)

# HTTPS -> wss Test
app.config["BASE_URL"] = "https://astra.example.com"
with app.app_context():
    ws = build_websocket_url(app)
    check("HTTPS Base -> wss WebSocket", ws.startswith("wss://"))
    check("wss URL enthaelt Host", "astra.example.com" in ws)

# HTTP -> ws Test
app.config["BASE_URL"] = "http://localhost:5000"
with app.app_context():
    ws = build_websocket_url(app)
    check("HTTP Base -> ws WebSocket", ws.startswith("ws://"))

# Trailing Slash entfernt
app.config["BASE_URL"] = "https://astra.example.com/"
with app.app_context():
    base = build_base_url(app)
    check("build_base_url entfernt trailing slash", not base.endswith("/"))


# ================================================================
# Security Headers Tests
# ================================================================

print("\n=== e) Security Headers / Rate Limiting ===")

# Security Headers (Testing-Modus – Headers werden nicht gesetzt)
# Im Non-Testing Modus pruefen wir mit einer separaten App
non_test_app = create_app("development")
with non_test_app.app_context():
    db.create_all()

non_test_client = non_test_app.test_client()
resp = non_test_client.get("/health")
check("Security Header X-Content-Type-Options gesetzt",
      resp.headers.get("X-Content-Type-Options") == "nosniff")
check("Security Header X-Frame-Options gesetzt",
      resp.headers.get("X-Frame-Options") == "DENY")
check("Security Header X-XSS-Protection gesetzt",
      "1" in (resp.headers.get("X-XSS-Protection") or ""))
check("Security Header Referrer-Policy gesetzt",
      resp.headers.get("Referrer-Policy") is not None)
check("Server Header entfernt",
      resp.headers.get("Server") is None)

# API-Response Cache-Control
resp = non_test_client.get("/api/admin/health")
check("API-Responses haben Cache-Control no-store",
      "no-store" in (resp.headers.get("Cache-Control") or ""))

# Rate Limiting ist in Testing deaktiviert
check("Rate Limiting in Testing deaktiviert",
      app.config.get("RATELIMIT_ENABLED") is False)

# Rate Limiting Config in Dev-App vorhanden
check("Rate Limiting in Dev-App aktiv",
      non_test_app.config.get("RATELIMIT_ENABLED") is True)


# ================================================================
# Bestehende API-Endpunkte (Regression)
# ================================================================

print("\n=== f) Regression – Bestehende Endpunkte ===")

# Auth-Endpunkte
resp = client.get("/api/auth/health")
check("GET /api/auth/health -> 200", resp.status_code == 200)

# Admin-Endpunkte
resp = client.get("/api/admin/health")
check("GET /api/admin/health -> 200", resp.status_code == 200)

# Admin Detailed Health (existierte vor M21)
with app.app_context():
    resp = client.get("/api/admin/health/detailed")
    check("GET /api/admin/health/detailed -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/api/admin/health/detailed hat checks", "checks" in data)

# Login-Endpunkt (ohne Body = 4xx)
resp = client.post("/api/auth/login")
check("POST /api/auth/login ohne Body -> 4xx", resp.status_code >= 400)

# Login mit falschen Daten -> 401
resp = client.post("/api/auth/login",
                   data=json.dumps({"login": "nonexist", "password": "wrong"}),
                   content_type="application/json")
check("POST /api/auth/login falsche Daten -> 401", resp.status_code == 401)

# Login mit korrektem User
token = None
with app.app_context():
    resp = client.post("/api/auth/login",
                       data=json.dumps({"login": "m21-user", "password": "testpass"}),
                       content_type="application/json")
    check("POST /api/auth/login korrekt -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Login gibt access_token", "access_token" in data)
    token = data.get("access_token")

# Auth /me mit Token
if token:
    resp = client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {token}"})
    check("GET /api/auth/me mit Token -> 200", resp.status_code == 200)

# X-User-Id Header (Dev/Test Fallback)
resp = client.get("/api/auth/me",
                  headers={"X-User-Id": str(_user_id)})
check("X-User-Id Fallback in Testing funktioniert", resp.status_code == 200)

# Admin-Routes mit X-User-Id
resp = client.get("/api/admin/users",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/users -> 200", resp.status_code == 200)

resp = client.get("/api/admin/agents",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/agents -> 200", resp.status_code == 200)

resp = client.get("/api/admin/blueprints",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/blueprints -> 200", resp.status_code == 200)

# Client-Routes
resp = client.get("/api/client/instances",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/client/instances -> 200", resp.status_code == 200)

# Webhooks
resp = client.get("/api/admin/webhooks",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/admin/webhooks -> 200", resp.status_code == 200)

# API Keys
resp = client.get("/api/auth/api-keys",
                  headers={"X-User-Id": str(_user_id)})
check("GET /api/auth/api-keys -> 200", resp.status_code == 200)


# ================================================================
# Konfiguration ueber App-Context
# ================================================================

print("\n=== g) App-Config-Validierung ===")

check("App hat SQLALCHEMY_DATABASE_URI", "SQLALCHEMY_DATABASE_URI" in app.config)
check("App hat SECRET_KEY", "SECRET_KEY" in app.config)
check("App hat JWT_SECRET_KEY", "JWT_SECRET_KEY" in app.config)
check("App hat RUNNER_ADAPTER", "RUNNER_ADAPTER" in app.config)
check("App hat CORS_ORIGINS", "CORS_ORIGINS" in app.config)
check("App hat BASE_URL", "BASE_URL" in app.config)
check("App hat LOG_LEVEL", "LOG_LEVEL" in app.config)
check("App hat RATELIMIT_ENABLED", "RATELIMIT_ENABLED" in app.config)
check("App hat PROXY_FIX_ENABLED", "PROXY_FIX_ENABLED" in app.config)
check("App hat WEBHOOK_MAX_RETRIES", "WEBHOOK_MAX_RETRIES" in app.config)
check("App hat _RUNNER_ADAPTER_NAME", "_RUNNER_ADAPTER_NAME" in app.config)

# Runner ist korrekt gesetzt
check("Runner-Adapter-Name ist stub", app.config["_RUNNER_ADAPTER_NAME"] == "stub")

# DB-URL-Maskierung testen
from app import _mask_db_url
masked = _mask_db_url("postgresql://user:secret@host:5432/db")
check("DB-URL-Maskierung versteckt Passwort", "secret" not in masked)
check("DB-URL-Maskierung behaelt User", "user" in masked)
check("DB-URL-Maskierung behaelt Host", "host" in masked)

masked2 = _mask_db_url("sqlite:///astra.db")
check("DB-URL-Maskierung laesst SQLite unberuehrt", masked2 == "sqlite:///astra.db")


# ================================================================
# Datei-Existenz-Checks
# ================================================================

print("\n=== h) Datei- und Struktur-Checks ===")

base_dir = os.path.dirname(__file__)
project_dir = os.path.dirname(base_dir)

check("backend/Dockerfile existiert",
      os.path.isfile(os.path.join(base_dir, "Dockerfile")))
check("backend/entrypoint.sh existiert",
      os.path.isfile(os.path.join(base_dir, "entrypoint.sh")))
check("backend/cli.py existiert",
      os.path.isfile(os.path.join(base_dir, "cli.py")))
check("backend/.env.example existiert",
      os.path.isfile(os.path.join(base_dir, ".env.example")))

check("docker-compose.yml existiert",
      os.path.isfile(os.path.join(project_dir, "docker-compose.yml")))
check("docker-compose.prod.yml existiert",
      os.path.isfile(os.path.join(project_dir, "docker-compose.prod.yml")))
check("docs/operations.md existiert",
      os.path.isfile(os.path.join(project_dir, "docs", "operations.md")))
check("scripts/backup.sh existiert",
      os.path.isfile(os.path.join(project_dir, "scripts", "backup.sh")))
check("scripts/restore.sh existiert",
      os.path.isfile(os.path.join(project_dir, "scripts", "restore.sh")))
check("frontend/Dockerfile existiert",
      os.path.isfile(os.path.join(project_dir, "frontend", "Dockerfile")))
check("frontend/nginx.conf existiert",
      os.path.isfile(os.path.join(project_dir, "frontend", "nginx.conf")))

# .env.example Vollstaendigkeits-Check
env_example_path = os.path.join(base_dir, ".env.example")
with open(env_example_path, encoding="utf-8") as f:
    env_content = f.read()

required_env_vars = [
    "APP_ENV", "SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
    "REDIS_URL", "RUNNER_ADAPTER", "CORS_ORIGINS", "BASE_URL",
    "PROXY_FIX_ENABLED", "RATELIMIT_ENABLED", "LOG_LEVEL",
    "WEBHOOK_MAX_RETRIES", "MFA_ISSUER_NAME", "SESSION_COOKIE_SECURE",
]
for var in required_env_vars:
    check(f".env.example enthaelt {var}", var in env_content)


# ================================================================
# Zusammenfassung
# ================================================================

print(f"\n{'='*60}")
total = passed + failed
print(f"M21 Deployment & Operations Readiness: {passed}/{total} Tests bestanden")
if failed > 0:
    print(f"  {failed} Test(s) fehlgeschlagen!")
    sys.exit(1)
else:
    print("  Alle Tests bestanden!")
    sys.exit(0)
