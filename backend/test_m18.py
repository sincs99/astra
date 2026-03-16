"""Schnelltests fuer Meilenstein 18 - Database Provisioning."""

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
_agent_id = None
_bp_id = None
_ep_id = None
_inst_id = None
_inst_uuid = None
_provider_id = None
_db_id = None


# ================================================================
# Setup
# ================================================================

with app.app_context():
    db.create_all()

    from app.domain.users.models import User
    from app.domain.agents.models import Agent
    from app.domain.blueprints.models import Blueprint
    from app.domain.endpoints.models import Endpoint
    from app.domain.instances.models import Instance
    from app.domain.instances.service import set_runner
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    user = User(username="m18-user", email="m18@test.dev")
    user.set_password("testpass")
    db.session.add(user)
    db.session.flush()

    agent = Agent(name="m18-agent", fqdn="m18.test.dev")
    db.session.add(agent)
    db.session.flush()

    bp = Blueprint(name="m18-bp")
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="0.0.0.0", port=25800)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="m18-instance",
        owner_id=user.id,
        agent_id=agent.id,
        blueprint_id=bp.id,
        status=None,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    _user_id = user.id
    _agent_id = agent.id
    _bp_id = bp.id
    _ep_id = ep.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid


# ================================================================
# Test 1: Modelle existieren
# ================================================================
print("\n== Modelle ==")

with app.app_context():
    from app.domain.databases.models import DatabaseProvider, Database

    check("DatabaseProvider Klasse", DatabaseProvider is not None)
    check("Database Klasse", Database is not None)

    # Provider erstellen
    provider = DatabaseProvider(
        name="test-mysql",
        host="db.test.dev",
        port=3306,
        admin_user="root",
        admin_password="secret",
        max_databases=10,
    )
    db.session.add(provider)
    db.session.commit()
    _provider_id = provider.id

    check("Provider ID", provider.id is not None)
    check("Provider name", provider.name == "test-mysql")

    # to_dict hat kein admin_password
    d = provider.to_dict()
    check("to_dict kein admin_password", "admin_password" not in d)
    check("to_dict hat host", d["host"] == "db.test.dev")
    check("to_dict hat database_count", "database_count" in d)

    # has_capacity
    check("has_capacity = True", provider.has_capacity())

    # Database erstellen (direkt)
    database = Database(
        instance_id=_inst_id,
        provider_id=provider.id,
        db_name="test_db_1",
        username="test_u_1",
        password="testpass123",
    )
    db.session.add(database)
    db.session.commit()
    _db_id = database.id

    check("Database ID", database.id is not None)

    # to_dict ohne password
    d = database.to_dict(include_password=False)
    check("DB to_dict kein password", "password" not in d)
    check("DB to_dict hat db_name", d["db_name"] == "test_db_1")
    check("DB to_dict hat provider_host", "provider_host" in d)

    # to_dict mit password
    d = database.to_dict(include_password=True)
    check("DB to_dict mit password", d.get("password") == "testpass123")

    # generate_password
    pw = Database.generate_password()
    check("generate_password hat Laenge", len(pw) > 10)

    # Aufraemen
    db.session.delete(database)
    db.session.commit()


# ================================================================
# Test 2: Provider-Service
# ================================================================
print("\n== Provider-Service ==")

with app.app_context():
    from app.domain.databases.service import (
        create_provider, update_provider, delete_provider,
        list_providers, get_provider, DatabaseError,
    )

    # Erstellen
    p = create_provider(name="svc-mysql", host="svc.test.dev", port=3307)
    check("Provider erstellt", p.id is not None)
    check("Provider host", p.host == "svc.test.dev")

    # Auflisten
    providers = list_providers()
    check("list_providers >= 2", len(providers) >= 2)

    # Abrufen
    p2 = get_provider(p.id)
    check("get_provider", p2.name == "svc-mysql")

    # Aktualisieren
    p3 = update_provider(p.id, name="svc-mysql-updated", port=3308)
    check("update name", p3.name == "svc-mysql-updated")
    check("update port", p3.port == 3308)

    # Loeschen
    delete_provider(p.id)

    try:
        get_provider(p.id)
        fail("Geloeschter Provider sollte 404 sein")
    except DatabaseError as e:
        check("Geloeschter Provider -> 404", e.status_code == 404)

    # Validierungsfehler
    try:
        create_provider(name="", host="x.dev")
        fail("Leerer Name sollte Fehler werfen")
    except DatabaseError:
        ok("Leerer Name -> Fehler")

    try:
        create_provider(name="x", host="")
        fail("Leerer Host sollte Fehler werfen")
    except DatabaseError:
        ok("Leerer Host -> Fehler")

    try:
        create_provider(name="x", host="x.dev", port=0)
        fail("Port 0 sollte Fehler werfen")
    except DatabaseError:
        ok("Port 0 -> Fehler")


# ================================================================
# Test 3: Database-Service
# ================================================================
print("\n== Database-Service ==")

with app.app_context():
    from app.domain.databases.service import (
        create_database, list_databases, rotate_password,
        delete_database, DatabaseError,
    )
    from app.domain.databases.models import DatabaseProvider
    from app.domain.instances.models import Instance

    db.session.expire_all()
    inst = db.session.get(Instance, _inst_id)
    provider = db.session.get(DatabaseProvider, _provider_id)

    # Erstellen
    database = create_database(inst, provider.id)
    check("DB erstellt", database.id is not None)
    check("DB hat db_name", len(database.db_name) > 0)
    check("DB hat username", len(database.username) > 0)
    check("DB hat password", len(database.password) > 0)
    check("DB provider_id", database.provider_id == provider.id)
    check("DB instance_id", database.instance_id == inst.id)
    created_db_id = database.id

    # Auflisten
    dbs = list_databases(inst)
    check("list_databases >= 1", len(dbs) >= 1)

    # Passwort rotieren
    old_pw = database.password
    database = rotate_password(inst, database)
    check("Passwort rotiert", database.password != old_pw)
    check("Neues Passwort nicht leer", len(database.password) > 0)

    # Loeschen
    delete_database(inst, database)
    dbs = list_databases(inst)
    check("Database geloescht", all(d.id != created_db_id for d in dbs))

    # Provider-Kapazitaet testen
    provider.max_databases = 1
    db.session.commit()

    db1 = create_database(inst, provider.id, db_name="cap_test_1", username="cap_u_1")
    try:
        create_database(inst, provider.id, db_name="cap_test_2", username="cap_u_2")
        fail("Kapazitaet sollte 409 liefern")
    except DatabaseError as e:
        check("Provider-Kapazitaet -> 409", e.status_code == 409)

    # Aufraemen
    delete_database(inst, db1)
    provider.max_databases = 10
    db.session.commit()

    # Ungueltige Instance
    try:
        from app.domain.databases.service import create_database as _cd
        _cd(inst, 999999)
        fail("Ungueltiger Provider sollte 404 liefern")
    except DatabaseError as e:
        check("Ungueltiger Provider -> 404", e.status_code == 404)


# ================================================================
# Test 4: Admin-API Provider
# ================================================================
print("\n== Admin-API Provider ==")

with app.app_context():
    client = app.test_client()

    # GET providers
    resp = client.get("/api/admin/database-providers")
    check("GET providers -> 200", resp.status_code == 200)
    data = resp.get_json()
    check("Providers ist Liste", isinstance(data, list))

    # POST provider
    resp = client.post("/api/admin/database-providers", json={
        "name": "api-mysql",
        "host": "api.db.dev",
        "port": 3306,
        "admin_user": "admin",
        "admin_password": "secret",
        "max_databases": 50,
    })
    check("POST provider -> 201", resp.status_code == 201)
    data = resp.get_json()
    check("Provider hat id", "id" in data)
    check("Provider kein admin_password", "admin_password" not in data)
    api_provider_id = data["id"]

    # PATCH provider
    resp = client.patch(f"/api/admin/database-providers/{api_provider_id}", json={
        "name": "api-mysql-updated",
    })
    check("PATCH provider -> 200", resp.status_code == 200)
    check("PATCH name updated", resp.get_json()["name"] == "api-mysql-updated")

    # POST ohne name -> 400
    resp = client.post("/api/admin/database-providers", json={
        "host": "x.dev",
    })
    check("POST ohne name -> 400", resp.status_code == 400)

    # DELETE provider
    resp = client.delete(f"/api/admin/database-providers/{api_provider_id}")
    check("DELETE provider -> 200", resp.status_code == 200)

    # DELETE nochmal -> 404
    resp = client.delete(f"/api/admin/database-providers/{api_provider_id}")
    check("DELETE nochmal -> 404", resp.status_code == 404)


# ================================================================
# Test 5: Client-API Databases
# ================================================================
print("\n== Client-API Databases ==")

with app.app_context():
    client = app.test_client()
    headers = {"X-User-Id": str(_user_id)}

    # GET databases
    resp = client.get(
        f"/api/client/instances/{_inst_uuid}/databases",
        headers=headers,
    )
    check("GET databases -> 200", resp.status_code == 200)
    check("Databases ist Liste", isinstance(resp.get_json(), list))

    # POST database
    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/databases",
        json={"provider_id": _provider_id},
        headers=headers,
    )
    check("POST database -> 201", resp.status_code == 201)
    data = resp.get_json()
    check("DB hat id", "id" in data)
    check("DB hat db_name", "db_name" in data)
    check("DB hat password", "password" in data)
    check("DB hat provider_host", "provider_host" in data)
    client_db_id = data["id"]

    # Rotate password
    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/databases/{client_db_id}/rotate-password",
        headers=headers,
    )
    check("Rotate -> 200", resp.status_code == 200)
    new_data = resp.get_json()
    check("Neues Password anders", new_data.get("password") != data.get("password"))

    # DELETE database
    resp = client.delete(
        f"/api/client/instances/{_inst_uuid}/databases/{client_db_id}",
        headers=headers,
    )
    check("DELETE database -> 200", resp.status_code == 200)

    # Ohne Auth -> 401
    resp = client.get(f"/api/client/instances/{_inst_uuid}/databases")
    check("Ohne Auth -> 401", resp.status_code == 401)

    # POST ohne provider_id -> 400
    resp = client.post(
        f"/api/client/instances/{_inst_uuid}/databases",
        json={},
        headers=headers,
    )
    check("POST ohne provider_id -> 400", resp.status_code == 400)


# ================================================================
# Test 6: Permissions (Database)
# ================================================================
print("\n== Permissions ==")

with app.app_context():
    from app.domain.collaborators.permissions import (
        DATABASE_PERMISSIONS,
        ALL_PERMISSIONS,
        is_valid_permission,
    )

    check("database.read vorhanden", "database.read" in DATABASE_PERMISSIONS)
    check("database.create vorhanden", "database.create" in DATABASE_PERMISSIONS)
    check("database.update vorhanden", "database.update" in DATABASE_PERMISSIONS)
    check("database.delete vorhanden", "database.delete" in DATABASE_PERMISSIONS)

    for perm in DATABASE_PERMISSIONS:
        check(f"{perm} in ALL_PERMISSIONS", perm in ALL_PERMISSIONS)
        check(f"{perm} is_valid", is_valid_permission(perm))


# ================================================================
# Test 7: Activity-Events
# ================================================================
print("\n== Activity-Events ==")

with app.app_context():
    from app.domain.activity.events import (
        DATABASE_CREATED,
        DATABASE_DELETED,
        DATABASE_PASSWORD_ROTATED,
    )
    from app.domain.activity.models import ActivityLog

    check("DATABASE_CREATED definiert", DATABASE_CREATED == "database:created")
    check("DATABASE_DELETED definiert", DATABASE_DELETED == "database:deleted")
    check("DATABASE_PASSWORD_ROTATED definiert",
          DATABASE_PASSWORD_ROTATED == "database:password_rotated")

    # Logs aus vorherigen Tests
    created_logs = ActivityLog.query.filter_by(event="database:created").count()
    check("Mindestens 1 database:created Log", created_logs >= 1)

    deleted_logs = ActivityLog.query.filter_by(event="database:deleted").count()
    check("Mindestens 1 database:deleted Log", deleted_logs >= 1)

    rotated_logs = ActivityLog.query.filter_by(event="database:password_rotated").count()
    check("Mindestens 1 password_rotated Log", rotated_logs >= 1)


# ================================================================
# Test 8: Webhook-Event-Katalog
# ================================================================
print("\n== Webhook-Event-Katalog ==")

with app.app_context():
    from app.domain.webhooks.event_catalog import (
        is_valid_webhook_event,
        get_event_catalog,
    )

    check("database:created im Katalog", is_valid_webhook_event("database:created"))
    check("database:deleted im Katalog", is_valid_webhook_event("database:deleted"))
    check("database:password_rotated im Katalog",
          is_valid_webhook_event("database:password_rotated"))

    catalog = get_event_catalog()
    check("Katalog hat >= 23 Events", len(catalog) >= 23)


# ================================================================
# Test 9: Provisioning-Adapter
# ================================================================
print("\n== Provisioning-Adapter ==")

with app.app_context():
    from app.infrastructure.database.adapter import (
        get_db_adapter,
        StubDatabaseAdapter,
        DatabaseProvisioningAdapter,
    )

    adapter = get_db_adapter()
    check("Adapter ist StubDatabaseAdapter", isinstance(adapter, StubDatabaseAdapter))
    check("Adapter erbt Basis-Klasse", isinstance(adapter, DatabaseProvisioningAdapter))

    result = adapter.create_database(None, "test", "user", "pass", "%")
    check("Stub create: success", result["success"])

    result = adapter.change_password(None, "user", "newpass")
    check("Stub change_password: success", result["success"])

    result = adapter.drop_database(None, "test", "user")
    check("Stub drop: success", result["success"])


# ================================================================
# Test 10: Regression
# ================================================================
print("\n== Regression ==")

with app.app_context():
    from app.domain.instances.service import get_runner, VALID_CONTAINER_STATES
    from app.infrastructure.runner.protocol import RunnerProtocol

    runner = get_runner()
    check("Runner ist RunnerProtocol", isinstance(runner, RunnerProtocol))
    check("VALID_CONTAINER_STATES", len(VALID_CONTAINER_STATES) >= 5)

    client = app.test_client()
    check("Agent Health -> 200", client.get("/api/agent/health").status_code == 200)
    check("Client Health -> 200", client.get("/api/client/health").status_code == 200)
    check("Admin Health -> 200", client.get("/api/admin/health").status_code == 200)
    check("Auth Health -> 200", client.get("/api/auth/health").status_code == 200)


# ================================================================
# Zusammenfassung
# ================================================================
print(f"\n{'='*60}")
print(f"M18 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
