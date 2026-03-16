"""Schnelltests fuer Meilenstein 17 - Authentifizierung & Session-Management."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
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


app = create_app("testing")

_user_id = None
_admin_id = None
_access_token = None
_admin_token = None


# ================================================================
# Setup: Users mit echten Passwoertern anlegen
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User

    # Normaler User
    user = User(username="m17-user", email="m17@test.dev")
    user.set_password("testpass123")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    # Admin User
    admin = User(username="m17-admin", email="m17admin@test.dev", is_admin=True)
    admin.set_password("adminpass456")
    db.session.add(admin)
    db.session.flush()
    _admin_id = admin.id

    db.session.commit()


# ================================================================
# Test 1: Passwort-Hashing
# ================================================================
print("\n== Passwort-Hashing ==")

with app.app_context():
    from app.domain.users.models import User

    user = db.session.get(User, _user_id)

    check("password_hash ist nicht Klartext",
          user.password_hash != "testpass123")
    check("password_hash ist nicht placeholder",
          user.password_hash != "placeholder")
    check("password_hash ist lang (gehasht)",
          len(user.password_hash) > 20)
    check("check_password korrekt → True",
          user.check_password("testpass123"))
    check("check_password falsch → False",
          not user.check_password("wrongpass"))
    check("check_password leer → False",
          not user.check_password(""))

    # to_dict enthaelt kein password_hash
    d = user.to_dict()
    check("to_dict hat KEIN password_hash",
          "password_hash" not in d)
    check("to_dict hat username", "username" in d)
    check("to_dict hat email", "email" in d)

    # Placeholder-Passwort schlaegt fehl
    temp = User(username="temp", email="temp@t.dev", password_hash="placeholder")
    check("placeholder check_password → False",
          not temp.check_password("anything"))


# ================================================================
# Test 2: Login-Endpunkt
# ================================================================
print("\n== Login-Endpunkt ==")

with app.app_context():
    client = app.test_client()

    # Login mit Username
    resp = client.post("/api/auth/login", json={
        "login": "m17-user",
        "password": "testpass123",
    })
    check("Login Username -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Response hat access_token", "access_token" in data)
    check("Response hat token_type", data.get("token_type") == "Bearer")
    check("Response hat user", "user" in data)
    check("Response user hat username", data["user"].get("username") == "m17-user")
    check("Response user hat KEIN password_hash", "password_hash" not in data["user"])

    _access_token = data["access_token"]

    # Login mit Email
    resp = client.post("/api/auth/login", json={
        "login": "m17@test.dev",
        "password": "testpass123",
    })
    check("Login Email -> 200", resp.status_code == 200)

    # Login Admin
    resp = client.post("/api/auth/login", json={
        "login": "m17-admin",
        "password": "adminpass456",
    })
    check("Login Admin -> 200", resp.status_code == 200)
    _admin_token = resp.get_json()["access_token"]

    # Falsches Passwort
    resp = client.post("/api/auth/login", json={
        "login": "m17-user",
        "password": "wrongpassword",
    })
    check("Falsches Passwort -> 401", resp.status_code == 401)

    # Nicht existierender User
    resp = client.post("/api/auth/login", json={
        "login": "nonexistent",
        "password": "whatever",
    })
    check("Unbekannter User -> 401", resp.status_code == 401)

    # Fehlende Felder
    resp = client.post("/api/auth/login", json={"login": "m17-user"})
    check("Fehlende Felder -> 400", resp.status_code == 400)

    resp = client.post("/api/auth/login", json={})
    check("Leerer Body -> 400", resp.status_code == 400)

    resp = client.post("/api/auth/login", content_type="application/json")
    check("Kein Body -> 400", resp.status_code == 400)


# ================================================================
# Test 3: Current User (/auth/me)
# ================================================================
print("\n== Current User /auth/me ==")

with app.app_context():
    client = app.test_client()

    # Mit gueltigem Token
    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {_access_token}",
    })
    check("GET /me -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/me username korrekt", data.get("username") == "m17-user")
    check("/me email korrekt", data.get("email") == "m17@test.dev")
    check("/me hat KEIN password_hash", "password_hash" not in data)

    # Ohne Token → 401
    resp = client.get("/api/auth/me")
    check("GET /me ohne Token -> 401", resp.status_code == 401)

    # Mit ungueltigem Token → 401
    resp = client.get("/api/auth/me", headers={
        "Authorization": "Bearer invalid.token.here",
    })
    check("GET /me ungueltiger Token -> 401", resp.status_code == 401)

    # Auth Health bleibt erreichbar
    resp = client.get("/api/auth/health")
    check("Auth Health -> 200", resp.status_code == 200)


# ================================================================
# Test 4: Geschuetzte Client-Routen mit JWT
# ================================================================
print("\n== Geschuetzte Client-Routen ==")

with app.app_context():
    client = app.test_client()

    # Client-Endpunkt mit JWT
    resp = client.get("/api/client/instances", headers={
        "Authorization": f"Bearer {_access_token}",
    })
    check("Client /instances mit JWT -> 200", resp.status_code == 200)

    # Client-Endpunkt ohne Auth → 401
    resp = client.get("/api/client/instances")
    check("Client ohne Auth -> 401", resp.status_code == 401)

    # Client-Endpunkt mit X-User-Id (Dev/Test Fallback)
    resp = client.get("/api/client/instances", headers={
        "X-User-Id": str(_user_id),
    })
    check("Client X-User-Id Fallback -> 200", resp.status_code == 200)


# ================================================================
# Test 5: Admin User-Erstellung mit Passwort
# ================================================================
print("\n== Admin User-Erstellung ==")

with app.app_context():
    client = app.test_client()

    # User erstellen mit Passwort
    resp = client.post("/api/admin/users", json={
        "username": "m17-created",
        "email": "m17created@test.dev",
        "password": "newpass789",
    })
    check("User erstellen -> 201", resp.status_code == 201)
    data = resp.get_json()
    check("Neuer User hat username", data.get("username") == "m17-created")
    check("Neuer User hat KEIN password_hash", "password_hash" not in data)

    # Login mit neuem User
    resp = client.post("/api/auth/login", json={
        "login": "m17-created",
        "password": "newpass789",
    })
    check("Login neuer User -> 200", resp.status_code == 200)

    # Ohne Passwort → 400
    resp = client.post("/api/admin/users", json={
        "username": "m17-nopass",
        "email": "nopass@test.dev",
    })
    check("Ohne Passwort -> 400", resp.status_code == 400)

    # Zu kurzes Passwort → 400
    resp = client.post("/api/admin/users", json={
        "username": "m17-short",
        "email": "short@test.dev",
        "password": "ab",
    })
    check("Kurzes Passwort -> 400", resp.status_code == 400)


# ================================================================
# Test 6: Auth-Service Funktionen
# ================================================================
print("\n== Auth-Service ==")

with app.app_context():
    from app.domain.auth.service import authenticate_user, issue_access_token
    from app.domain.users.models import User

    # authenticate_user
    user = authenticate_user("m17-user", "testpass123")
    check("authenticate_user korrekt -> User", user is not None)
    check("authenticate_user username", user.username == "m17-user")

    user = authenticate_user("m17@test.dev", "testpass123")
    check("authenticate_user via Email", user is not None)

    user = authenticate_user("m17-user", "wrong")
    check("authenticate_user falsch -> None", user is None)

    user = authenticate_user("nonexistent", "whatever")
    check("authenticate_user unbekannt -> None", user is None)

    # issue_access_token
    user = db.session.get(User, _user_id)
    token = issue_access_token(user)
    check("issue_access_token ist String", isinstance(token, str))
    check("issue_access_token nicht leer", len(token) > 0)


# ================================================================
# Test 7: Activity-Events
# ================================================================
print("\n== Activity-Events ==")

with app.app_context():
    from app.domain.activity.events import AUTH_LOGIN_SUCCESS, AUTH_LOGIN_FAILED
    from app.domain.activity.models import ActivityLog

    check("AUTH_LOGIN_SUCCESS definiert",
          AUTH_LOGIN_SUCCESS == "auth:login_success")
    check("AUTH_LOGIN_FAILED definiert",
          AUTH_LOGIN_FAILED == "auth:login_failed")

    # Login-Erfolg-Logs aus vorherigen Tests
    success_logs = ActivityLog.query.filter_by(event="auth:login_success").count()
    check("Mindestens 1 Login-Success-Log", success_logs >= 1)

    # Login-Fail-Logs aus vorherigen Tests
    fail_logs = ActivityLog.query.filter_by(event="auth:login_failed").count()
    check("Mindestens 1 Login-Failed-Log", fail_logs >= 1)


# ================================================================
# Test 8: Agent-Routen NICHT auf User-Auth umgestellt
# ================================================================
print("\n== Agent-Routen unberuehrt ==")

with app.app_context():
    client = app.test_client()

    # Agent Health ohne Auth
    resp = client.get("/api/agent/health")
    check("Agent Health ohne Auth -> 200", resp.status_code == 200)

    # Agent Install-Callback ohne User-Auth (agent-auth bleibt eigene Logik)
    from app.domain.instances.models import Instance
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint

    agent = Agent(name="m17-agent", fqdn="m17.test.dev")
    db.session.add(agent)
    db.session.flush()

    bprint = Blueprint(name="m17-bp")
    db.session.add(bprint)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25700)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m17-inst",
        owner_id=_user_id,
        agent_id=agent.id,
        blueprint_id=bprint.id,
        status="provisioning",
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    # Container-Status Callback ohne User-Auth
    resp = client.post(
        f"/api/agent/instances/{inst.uuid}/container/status",
        json={"state": "running"},
    )
    check("Agent container_status ohne Auth -> 200", resp.status_code == 200)


# ================================================================
# Test 9: Regression – bestehende Flows
# ================================================================
print("\n== Regression ==")

with app.app_context():
    from app.domain.instances.service import (
        set_runner,
        get_runner,
        VALID_CONTAINER_STATES,
        VALID_LIFECYCLE_STATUSES,
    )
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol

    set_runner(StubRunnerAdapter())

    # Runner funktioniert
    runner = get_runner()
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))

    # Konstanten vorhanden
    check("VALID_CONTAINER_STATES vorhanden", len(VALID_CONTAINER_STATES) >= 5)
    check("VALID_LIFECYCLE_STATUSES vorhanden", len(VALID_LIFECYCLE_STATUSES) >= 5)

    # Client Health mit JWT
    client = app.test_client()
    resp = client.get("/api/client/health")
    check("Client Health -> 200", resp.status_code == 200)

    # Admin Health
    resp = client.get("/api/admin/health")
    check("Admin Health -> 200", resp.status_code == 200)

    # Webhook-Events (sollten die neuen M16 Events enthalten)
    from app.domain.webhooks.event_catalog import get_event_catalog
    catalog = get_event_catalog()
    check("Webhook-Katalog >= 20 Events", len(catalog) >= 20)


# ================================================================
# Test 10: Token-Erneuerung und Auth-Kontext
# ================================================================
print("\n== Token-Kontext ==")

with app.app_context():
    from flask_jwt_extended import decode_token

    # Token decodieren und Claims pruefen
    decoded = decode_token(_access_token)
    check("Token hat sub (identity)", "sub" in decoded)
    check("Token sub = user_id", decoded["sub"] == str(_user_id))
    check("Token hat username Claim",
          decoded.get("username") == "m17-user")
    check("Token hat is_admin Claim",
          decoded.get("is_admin") is False)
    check("Token hat exp", "exp" in decoded)

    # Admin-Token pruefen
    decoded_admin = decode_token(_admin_token)
    check("Admin Token is_admin = True",
          decoded_admin.get("is_admin") is True)


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M17 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
