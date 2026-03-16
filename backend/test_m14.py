"""Schnelltests fuer Meilenstein 14 - Websocket/Console-Integration."""

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

# ================================================================
# Test 1: Token-Service - Wings-kompatibles JWT
# ================================================================
print("\n== Token-Service - Wings-kompatibles JWT ==")

with app.app_context():
    db.create_all()
    import jwt
    from app.infrastructure.tokens.service import create_websocket_token, build_socket_url
    from app.domain.agents.models import Agent

    agent = Agent(
        name="ws-agent", fqdn="ws.test.dev",
        scheme="https", daemon_connect=8080,
        daemon_token="test-daemon-secret-key-123",
        daemon_token_id="tok123",
    )
    db.session.add(agent)
    db.session.commit()

    # Token mit Agent (Wings-kompatibel)
    token = create_websocket_token(
        instance_uuid="inst-uuid-test",
        user_id=42,
        agent=agent,
    )
    check("Token ist String", isinstance(token, str))
    check("Token nicht leer", len(token) > 0)

    # Token decodieren und Claims pruefen
    decoded = jwt.decode(token, agent.daemon_token, algorithms=["HS256"],
                         options={"verify_aud": False})
    check("Claim server_uuid", decoded.get("server_uuid") == "inst-uuid-test")
    check("Claim user_id", decoded.get("user_id") == 42)
    check("Claim permissions ist Liste", isinstance(decoded.get("permissions"), list))
    check("Claim permissions hat Eintraege", len(decoded.get("permissions", [])) > 0)
    check("Claim jti vorhanden", "jti" in decoded)
    check("Claim unique_id vorhanden", "unique_id" in decoded)
    check("Claim iss vorhanden", "iss" in decoded)
    check("Claim aud vorhanden", "aud" in decoded)
    check("Claim aud = Agent URL", decoded["aud"] == "https://ws.test.dev:8080")
    check("Claim exp vorhanden", "exp" in decoded)
    check("Claim iat vorhanden", "iat" in decoded)
    check("Claim nbf vorhanden", "nbf" in decoded)

    # Token ohne Agent (Fallback)
    token_fallback = create_websocket_token(
        instance_uuid="inst-uuid-test",
        user_id=42,
    )
    check("Fallback-Token ist String", isinstance(token_fallback, str))
    fallback_secret = app.config.get("JWT_SECRET_KEY", "dev-jwt-secret-key")
    decoded_fb = jwt.decode(token_fallback, fallback_secret, algorithms=["HS256"])
    check("Fallback-Token hat server_uuid", decoded_fb.get("server_uuid") == "inst-uuid-test")

    # Token mit Agent MUSS mit daemon_token signiert sein (nicht Panel-Secret)
    try:
        jwt.decode(token, fallback_secret, algorithms=["HS256"], options={"verify_aud": False})
        check("Token NICHT mit Panel-Secret verifizierbar", False, "Sollte fehlschlagen")
    except jwt.InvalidSignatureError:
        check("Token NICHT mit Panel-Secret verifizierbar", True)
    except Exception:
        check("Token NICHT mit Panel-Secret verifizierbar", True)

    # Benutzerdefinierte Permissions
    token_custom = create_websocket_token(
        instance_uuid="inst-uuid-test",
        user_id=1,
        agent=agent,
        permissions=["control.console", "websocket.connect"],
    )
    decoded_custom = jwt.decode(token_custom, agent.daemon_token, algorithms=["HS256"],
                                options={"verify_aud": False})
    check("Custom permissions", decoded_custom["permissions"] == ["control.console", "websocket.connect"])


# ================================================================
# Test 2: Socket-URL-Building
# ================================================================
print("\n== Socket-URL-Building ==")

with app.app_context():
    # Mit Agent-Objekt (https -> wss)
    url = build_socket_url(agent, "inst-uuid-123")
    check("URL mit Agent (wss)", url == "wss://ws.test.dev:8080/api/servers/inst-uuid-123/ws",
          f"Got: {url}")

    # Mit Agent (http -> ws)
    http_agent = Agent(name="http-agent", fqdn="http.test.dev",
                       scheme="http", daemon_connect=8080)
    url_http = build_socket_url(http_agent, "inst-uuid-123")
    check("URL mit http Agent (ws)", url_http == "ws://http.test.dev:8080/api/servers/inst-uuid-123/ws",
          f"Got: {url_http}")

    # Fallback mit FQDN-String
    url_legacy = build_socket_url("legacy.test.dev", "inst-uuid-456")
    check("URL mit FQDN-String (legacy)", url_legacy == "wss://legacy.test.dev/api/servers/inst-uuid-456/ws",
          f"Got: {url_legacy}")


# ================================================================
# Test 3: Websocket-Credentials-Endpunkt
# ================================================================
print("\n== Websocket-Credentials-Endpunkt ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.blueprints.models import Blueprint as BPModel
    from app.domain.instances.models import Instance
    from app.domain.endpoints.models import Endpoint

    user = User(username="wsuser", email="ws@test.dev", password_hash="x")
    db.session.add(user)
    db.session.flush()

    bp = BPModel(name="WS-Blueprint", docker_image="test:latest")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="10.0.0.1", port=25565)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="WsTestServer", owner_id=user.id,
        agent_id=agent.id, blueprint_id=bp.id,
        memory=512, disk=1024, cpu=100,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    inst_uuid = inst.uuid
    user_id = user.id

    client = app.test_client()

    # Erfolgreiche Credentials-Abfrage
    r = client.get(f"/api/client/instances/{inst_uuid}/websocket",
                   headers={"X-User-Id": str(user_id)})
    check("GET /websocket - 200", r.status_code == 200, f"Got: {r.status_code}")
    data = r.get_json()
    check("Response hat token", "token" in data)
    check("Response hat socket", "socket" in data)
    check("Socket-URL enthaelt ws.test.dev", "ws.test.dev" in data["socket"])
    check("Socket-URL enthaelt /api/servers/", "/api/servers/" in data["socket"])
    check("Socket-URL enthaelt /ws", data["socket"].endswith("/ws"))
    check("Socket-URL startet mit wss://", data["socket"].startswith("wss://"))

    # Token verifizieren
    decoded_ws = jwt.decode(data["token"], agent.daemon_token, algorithms=["HS256"],
                            options={"verify_aud": False})
    check("WS-Token server_uuid korrekt", decoded_ws["server_uuid"] == inst_uuid)
    check("WS-Token user_id korrekt", decoded_ws["user_id"] == user_id)

    # Ohne Auth-Header
    r = client.get(f"/api/client/instances/{inst_uuid}/websocket")
    check("GET /websocket ohne Auth - 401", r.status_code == 401)

    # Fremder User
    r = client.get(f"/api/client/instances/{inst_uuid}/websocket",
                   headers={"X-User-Id": "99999"})
    check("GET /websocket fremder User - 404", r.status_code == 404)


# ================================================================
# Test 4: Resources-Endpunkt
# ================================================================
print("\n== Resources-Endpunkt ==")

with app.app_context():
    r = client.get(f"/api/client/instances/{inst_uuid}/resources",
                   headers={"X-User-Id": str(user_id)})
    check("GET /resources - 200", r.status_code == 200)
    res = r.get_json()
    check("Resources hat cpu_percent", "cpu_percent" in res)
    check("Resources hat container_status", "container_status" in res)

    # Ohne Auth
    r = client.get(f"/api/client/instances/{inst_uuid}/resources")
    check("GET /resources ohne Auth - 401", r.status_code == 401)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*50}")
print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*50}\n")

sys.exit(1 if failed else 0)
