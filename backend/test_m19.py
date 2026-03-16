"""Schnelltests fuer Meilenstein 19 - Auth-Haertung, API Keys, MFA-Basis."""

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
_raw_api_key = None
_api_key_id = None


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User

    user = User(username="m19-user", email="m19@test.dev")
    user.set_password("testpass123")
    db.session.add(user)
    db.session.flush()
    _user_id = user.id

    admin = User(username="m19-admin", email="m19admin@test.dev", is_admin=True)
    admin.set_password("adminpass456")
    db.session.add(admin)
    db.session.flush()
    _admin_id = admin.id

    db.session.commit()

    # Login fuer Token
    from app.domain.auth.service import issue_access_token
    _access_token = issue_access_token(user)


# ================================================================
# Test 1: ApiKey-Modell
# ================================================================
print("\n== ApiKey-Modell ==")

with app.app_context():
    from app.domain.auth.models import ApiKey

    # Token generieren
    raw, identifier, token_hash = ApiKey.generate_token()
    check("Raw-Token hat Identifier", raw.startswith("astra_"))
    check("Raw-Token hat Punkt", "." in raw)
    check("Identifier startet mit astra_", identifier.startswith("astra_"))
    check("Token-Hash ist 64 Zeichen (SHA256)", len(token_hash) == 64)

    # Hash pruefen
    check("hash_token stimmt", ApiKey.hash_token(raw) == token_hash)
    check("Falscher Token != Hash", ApiKey.hash_token("wrong") != token_hash)

    # to_dict hat kein token_hash
    key = ApiKey(
        user_id=_user_id,
        identifier=identifier,
        token_hash=token_hash,
        key_type="account",
    )
    db.session.add(key)
    db.session.commit()

    d = key.to_dict()
    check("to_dict kein token_hash", "token_hash" not in d)
    check("to_dict hat identifier", "identifier" in d)
    check("to_dict hat key_type", d.get("key_type") == "account")

    db.session.delete(key)
    db.session.commit()


# ================================================================
# Test 2: ApiKey-Service
# ================================================================
print("\n== ApiKey-Service ==")

with app.app_context():
    from app.domain.auth.apikey_service import (
        create_api_key, validate_api_key, delete_api_key,
        list_user_keys, ApiKeyError,
    )

    # Erstellen
    api_key, raw_token = create_api_key(_user_id, memo="Test-Key")
    check("API Key erstellt", api_key.id is not None)
    check("Raw-Token einmalig", raw_token is not None and len(raw_token) > 20)
    check("Hash gespeichert", len(api_key.token_hash) == 64)
    check("Memo gespeichert", api_key.memo == "Test-Key")
    _raw_api_key = raw_token
    _api_key_id = api_key.id

    # Validieren
    validated = validate_api_key(raw_token)
    check("Validierung korrekt", validated is not None)
    check("Validierung ID stimmt", validated.id == api_key.id)
    check("last_used_at gesetzt", validated.last_used_at is not None)

    # Falsche Validierung
    invalid = validate_api_key("wrong.token")
    check("Falscher Token -> None", invalid is None)

    invalid2 = validate_api_key("")
    check("Leerer Token -> None", invalid2 is None)

    # Auflisten
    keys = list_user_keys(_user_id)
    check("list_user_keys >= 1", len(keys) >= 1)

    # Zweiten Key erstellen
    key2, raw2 = create_api_key(_user_id, key_type="application", memo="App-Key")
    check("Zweiter Key erstellt", key2.id is not None)

    # Loeschen
    delete_api_key(key2.id, _user_id)
    keys_after = list_user_keys(_user_id)
    check("Nach Loeschung weniger Keys", len(keys_after) < len(keys) + 1)

    # Falscher User -> 404
    try:
        delete_api_key(api_key.id, 99999)
        fail("Falscher User sollte 404 werfen")
    except ApiKeyError as e:
        check("Falscher User -> 404", e.status_code == 404)


# ================================================================
# Test 3: API-Key Auth
# ================================================================
print("\n== API-Key Auth ==")

with app.app_context():
    client = app.test_client()

    # Client-Endpunkt mit API Key
    resp = client.get("/api/client/instances", headers={
        "Authorization": f"Bearer {_raw_api_key}",
    })
    check("Client mit API Key -> 200", resp.status_code == 200)

    # /auth/me mit API Key
    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {_raw_api_key}",
    })
    check("/me mit API Key -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("/me API Key username", data.get("username") == "m19-user")

    # Falscher API Key
    resp = client.get("/api/auth/me", headers={
        "Authorization": "Bearer astra_fake.invalidtoken",
    })
    check("Falscher API Key -> 401", resp.status_code == 401)


# ================================================================
# Test 4: MFA-Basis
# ================================================================
print("\n== MFA-Basis ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.auth.mfa_service import (
        setup_mfa, verify_and_enable_mfa, verify_totp, disable_mfa, MfaError,
    )
    import pyotp

    user = db.session.get(User, _user_id)

    # MFA-Felder vorhanden
    check("mfa_secret Attribut", hasattr(user, "mfa_secret"))
    check("mfa_enabled Attribut", hasattr(user, "mfa_enabled"))
    check("mfa_recovery_codes Attribut", hasattr(user, "mfa_recovery_codes"))

    # to_dict hat keine MFA-Secrets
    d = user.to_dict()
    check("to_dict hat mfa_enabled", "mfa_enabled" in d)
    check("to_dict kein mfa_secret", "mfa_secret" not in d)
    check("to_dict keine recovery_codes", "mfa_recovery_codes" not in d)

    # MFA-Setup
    result = setup_mfa(user)
    check("Setup hat secret", "secret" in result)
    check("Setup hat provisioning_uri", "provisioning_uri" in result)
    check("mfa_secret gesetzt", user.mfa_secret is not None)
    check("mfa_enabled noch False", user.mfa_enabled is not True)

    # Falscher Code
    try:
        verify_and_enable_mfa(user, "000000")
        fail("Falscher Code sollte MfaError werfen")
    except MfaError:
        ok("Falscher Code -> MfaError")

    # Korrekter Code
    totp = pyotp.TOTP(user.mfa_secret)
    correct_code = totp.now()
    result = verify_and_enable_mfa(user, correct_code)
    check("MFA aktiviert", result.get("mfa_enabled") is True)
    check("Recovery-Codes vorhanden", len(result.get("recovery_codes", [])) > 0)
    check("User mfa_enabled = True", user.mfa_enabled is True)

    # verify_totp mit korrektem Code
    check("verify_totp korrekt", verify_totp(user, totp.now()))

    # verify_totp mit falschem Code
    check("verify_totp falsch", not verify_totp(user, "000000"))

    # Recovery-Code verwenden
    if user.mfa_recovery_codes:
        recovery = user.mfa_recovery_codes[0]
        check("Recovery-Code OK", verify_totp(user, recovery))

    # Doppeltes Setup -> Fehler
    try:
        setup_mfa(user)
        fail("Doppeltes Setup sollte Fehler werfen")
    except MfaError:
        ok("Doppeltes MFA-Setup -> Fehler")

    # MFA deaktivieren
    result = disable_mfa(user)
    check("MFA deaktiviert", result.get("mfa_enabled") is False)
    check("mfa_secret geloescht", user.mfa_secret is None)

    # Deaktivieren wenn nicht aktiv -> Fehler
    try:
        disable_mfa(user)
        fail("Doppelte Deaktivierung sollte Fehler werfen")
    except MfaError:
        ok("MFA-Disable wenn nicht aktiv -> Fehler")


# ================================================================
# Test 5: Auth-Routen API Keys
# ================================================================
print("\n== Auth-Routen API Keys ==")

with app.app_context():
    client = app.test_client()
    auth = {"Authorization": f"Bearer {_access_token}"}

    # GET /api-keys
    resp = client.get("/api/auth/api-keys", headers=auth)
    check("GET api-keys -> 200", resp.status_code == 200)
    check("api-keys ist Liste", isinstance(resp.get_json(), list))

    # POST /api-keys
    resp = client.post("/api/auth/api-keys", json={
        "memo": "Route-Test-Key",
        "key_type": "account",
    }, headers=auth)
    check("POST api-key -> 201", resp.status_code == 201)
    data = resp.get_json()
    check("Response hat raw_token", "raw_token" in data)
    check("Response hat identifier", "identifier" in data)
    check("Response kein token_hash", "token_hash" not in data)
    route_key_id = data["id"]
    route_raw_token = data["raw_token"]

    # Neuer Key funktioniert
    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {route_raw_token}",
    })
    check("Neuer Key funktioniert", resp.status_code == 200)

    # DELETE /api-keys
    resp = client.delete(f"/api/auth/api-keys/{route_key_id}", headers=auth)
    check("DELETE api-key -> 200", resp.status_code == 200)

    # Geloeschter Key funktioniert nicht mehr
    resp = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {route_raw_token}",
    })
    check("Geloeschter Key -> 401", resp.status_code == 401)

    # Ohne Auth
    resp = client.get("/api/auth/api-keys")
    check("API Keys ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 6: Auth-Routen MFA
# ================================================================
print("\n== Auth-Routen MFA ==")

with app.app_context():
    client = app.test_client()
    auth = {"Authorization": f"Bearer {_access_token}"}

    # MFA Setup
    resp = client.post("/api/auth/mfa/setup", headers=auth)
    check("MFA Setup -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Setup hat secret", "secret" in data)
    check("Setup hat provisioning_uri", "provisioning_uri" in data)

    # MFA Verify mit korrektem Code
    import pyotp
    totp = pyotp.TOTP(data["secret"])
    resp = client.post("/api/auth/mfa/verify", json={
        "code": totp.now(),
    }, headers=auth)
    check("MFA Verify -> 200", resp.status_code == 200)
    check("MFA aktiviert", resp.get_json().get("mfa_enabled") is True)

    # MFA Disable
    resp = client.post("/api/auth/mfa/disable", headers=auth)
    check("MFA Disable -> 200", resp.status_code == 200)

    # Ohne Auth
    resp = client.post("/api/auth/mfa/setup")
    check("MFA Setup ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 7: Login mit MFA
# ================================================================
print("\n== Login mit MFA ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.auth.mfa_service import setup_mfa, verify_and_enable_mfa
    import pyotp

    client = app.test_client()
    user = db.session.get(User, _user_id)

    # MFA aktivieren
    result = setup_mfa(user)
    secret = result["secret"]
    totp = pyotp.TOTP(secret)
    verify_and_enable_mfa(user, totp.now())

    # Login ohne MFA-Code -> requires_mfa
    resp = client.post("/api/auth/login", json={
        "login": "m19-user",
        "password": "testpass123",
    })
    check("Login ohne MFA-Code -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("requires_mfa = True", data.get("requires_mfa") is True)

    # Login mit falschem MFA-Code -> 401
    resp = client.post("/api/auth/login", json={
        "login": "m19-user",
        "password": "testpass123",
        "mfa_code": "000000",
    })
    check("Login falscher MFA-Code -> 401", resp.status_code == 401)

    # Login mit korrektem MFA-Code -> Token
    resp = client.post("/api/auth/login", json={
        "login": "m19-user",
        "password": "testpass123",
        "mfa_code": totp.now(),
    })
    check("Login mit MFA-Code -> 200", resp.status_code == 200)
    check("Login hat access_token", "access_token" in resp.get_json())

    # MFA deaktivieren fuer restliche Tests
    from app.domain.auth.mfa_service import disable_mfa
    disable_mfa(user)


# ================================================================
# Test 8: Logout
# ================================================================
print("\n== Logout ==")

with app.app_context():
    client = app.test_client()

    resp = client.post("/api/auth/logout", headers={
        "Authorization": f"Bearer {_access_token}",
    })
    check("Logout -> 200", resp.status_code == 200)

    resp = client.post("/api/auth/logout")
    check("Logout ohne Auth -> 401", resp.status_code == 401)


# ================================================================
# Test 9: Activity-Events
# ================================================================
print("\n== Activity-Events ==")

with app.app_context():
    from app.domain.activity.events import (
        AUTH_LOGIN_SUCCESS, AUTH_LOGIN_FAILED, AUTH_LOGOUT,
        AUTH_API_KEY_CREATED, AUTH_API_KEY_DELETED,
        AUTH_MFA_ENABLED, AUTH_MFA_DISABLED,
    )
    from app.domain.activity.models import ActivityLog

    check("AUTH_LOGOUT definiert", AUTH_LOGOUT == "auth:logout")
    check("AUTH_API_KEY_CREATED definiert", AUTH_API_KEY_CREATED == "auth:api_key_created")
    check("AUTH_API_KEY_DELETED definiert", AUTH_API_KEY_DELETED == "auth:api_key_deleted")
    check("AUTH_MFA_ENABLED definiert", AUTH_MFA_ENABLED == "auth:mfa_enabled")
    check("AUTH_MFA_DISABLED definiert", AUTH_MFA_DISABLED == "auth:mfa_disabled")

    # Logs aus vorherigen Tests
    key_created = ActivityLog.query.filter_by(event="auth:api_key_created").count()
    check("Mindestens 1 api_key_created Log", key_created >= 1)

    mfa_enabled = ActivityLog.query.filter_by(event="auth:mfa_enabled").count()
    check("Mindestens 1 mfa_enabled Log", mfa_enabled >= 1)

    login_success = ActivityLog.query.filter_by(event="auth:login_success").count()
    check("Mindestens 1 login_success Log", login_success >= 1)

    logout_logs = ActivityLog.query.filter_by(event="auth:logout").count()
    check("Mindestens 1 logout Log", logout_logs >= 1)


# ================================================================
# Test 10: Security - Serialisierung
# ================================================================
print("\n== Security Serialisierung ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.auth.models import ApiKey

    user = db.session.get(User, _user_id)
    d = user.to_dict()
    check("User: kein password_hash", "password_hash" not in d)
    check("User: kein mfa_secret", "mfa_secret" not in d)
    check("User: keine recovery_codes", "mfa_recovery_codes" not in d)
    check("User: hat mfa_enabled", "mfa_enabled" in d)

    keys = ApiKey.query.filter_by(user_id=_user_id).all()
    for key in keys:
        d = key.to_dict()
        check(f"ApiKey {key.identifier}: kein token_hash", "token_hash" not in d)


# ================================================================
# Test 11: Regression
# ================================================================
print("\n== Regression ==")

with app.app_context():
    from app.domain.instances.service import get_runner, VALID_CONTAINER_STATES, set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter
    from app.infrastructure.runner.protocol import RunnerProtocol

    set_runner(StubRunnerAdapter())
    runner = get_runner()
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))

    client = app.test_client()
    check("Agent Health -> 200", client.get("/api/agent/health").status_code == 200)
    check("Client Health -> 200", client.get("/api/client/health").status_code == 200)
    check("Admin Health -> 200", client.get("/api/admin/health").status_code == 200)
    check("Auth Health -> 200", client.get("/api/auth/health").status_code == 200)

    # JWT Login weiterhin funktional
    resp = client.post("/api/auth/login", json={
        "login": "m19-user",
        "password": "testpass123",
    })
    check("Login weiterhin OK", resp.status_code == 200)
    check("Login hat Token", "access_token" in resp.get_json())


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M19 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
