"""Schnelltests fuer Meilenstein 13 - Wings-Backup-Integration."""

import sys
import os
from unittest.mock import patch, MagicMock

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
# Test 1: WingsRunnerAdapter - create_backup (Mocked)
# ================================================================
print("\n== WingsRunnerAdapter - create_backup ==")

with app.app_context():
    db.create_all()

    from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter
    from app.infrastructure.runner.wings_http import WingsResponse
    from app.domain.agents.models import Agent
    from app.domain.backups.models import Backup

    adapter = WingsRunnerAdapter(timeout=(5, 10))

    mock_agent = Agent(name="bk-agent", fqdn="bk.test.dev",
                       scheme="https", daemon_connect=8080, daemon_token="tok")

    mock_instance = MagicMock()
    mock_instance.uuid = "inst-uuid"
    mock_instance.name = "TestServer"
    mock_instance.agent_id = 1

    mock_backup = MagicMock(spec=Backup)
    mock_backup.uuid = "bk-uuid-001"
    mock_backup.name = "Daily Backup"
    mock_backup.disk = "wings"
    mock_backup.ignored_files = "*.tmp\ncache/"

    # Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=200,
        data={"checksum": "abc123", "size": 50000000},
    )) as mock_post:
        result = adapter.create_backup(mock_agent, mock_instance, mock_backup)
        check("create_backup - success", result.success is True)
        check("create_backup - message", "erstellt" in result.message)
        check("create_backup - checksum", result.data.get("checksum") == "abc123")
        check("create_backup - bytes", result.data.get("bytes") == 50000000)

        # Pruefen: korrekter Endpoint und Payload
        call_args = mock_post.call_args
        check("create_backup - endpoint", f"/api/servers/inst-uuid/backup" in call_args[0][1])
        payload = call_args[0][2]
        check("create_backup - adapter=wings", payload["adapter"] == "wings")
        check("create_backup - uuid", payload["uuid"] == "bk-uuid-001")
        check("create_backup - ignore", "*.tmp" in payload["ignore"])

    # Fehler
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=False, status_code=500, data=None, error="Internal"
    )):
        result = adapter.create_backup(mock_agent, mock_instance, mock_backup)
        check("create_backup fehler - not success", result.success is False)
        check("create_backup fehler - message", "fehlgeschlagen" in result.message)

    # Timeout
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=False, status_code=None, data=None, error="Timeout"
    )):
        result = adapter.create_backup(mock_agent, mock_instance, mock_backup)
        check("create_backup timeout - not success", result.success is False)

# ================================================================
# Test 2: WingsRunnerAdapter - restore_backup (Mocked)
# ================================================================
print("\n== WingsRunnerAdapter - restore_backup ==")

with app.app_context():
    # Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=204, data=None,
    )) as mock_post:
        result = adapter.restore_backup(mock_agent, mock_instance, mock_backup)
        check("restore_backup - success", result.success is True)
        check("restore_backup - message", "wiederhergestellt" in result.message)

        call_args = mock_post.call_args
        endpoint = call_args[0][1]
        check("restore_backup - endpoint", f"/api/servers/inst-uuid/backup/bk-uuid-001/restore" in endpoint,
              f"Endpoint: {endpoint}")
        payload = call_args[0][2]
        check("restore_backup - adapter", payload["adapter"] == "wings")
        check("restore_backup - truncate", payload["truncate_directory"] is False)
        check("restore_backup - download_url", payload["download_url"] == "")

    # Fehler
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=False, status_code=404, data=None, error="Not Found"
    )):
        result = adapter.restore_backup(mock_agent, mock_instance, mock_backup)
        check("restore_backup fehler - not success", result.success is False)
        check("restore_backup fehler - message", "fehlgeschlagen" in result.message)

# ================================================================
# Test 3: WingsRunnerAdapter - delete_backup (Mocked)
# ================================================================
print("\n== WingsRunnerAdapter - delete_backup ==")

with app.app_context():
    # Erfolg
    with patch.object(adapter._http, "delete", return_value=WingsResponse(
        success=True, status_code=204, data=None,
    )) as mock_del:
        result = adapter.delete_backup(mock_agent, mock_instance, mock_backup)
        check("delete_backup - success", result.success is True)
        check("delete_backup - message", "geloescht" in result.message)

        endpoint = mock_del.call_args[0][1]
        check("delete_backup - endpoint", f"/api/servers/inst-uuid/backup/bk-uuid-001" in endpoint,
              f"Endpoint: {endpoint}")

    # Fehler
    with patch.object(adapter._http, "delete", return_value=WingsResponse(
        success=False, status_code=500, data=None, error="Internal"
    )):
        result = adapter.delete_backup(mock_agent, mock_instance, mock_backup)
        check("delete_backup fehler - not success", result.success is False)

# ================================================================
# Test 4: Stub-Adapter Backup-Ops weiterhin funktional
# ================================================================
print("\n== Stub-Adapter Backup-Kompatibilitaet ==")

with app.app_context():
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    stub = StubRunnerAdapter()
    stub_agent = Agent(name="stub-agent", fqdn="stub.test.dev")

    result = stub.create_backup(stub_agent, mock_instance, mock_backup)
    check("Stub create_backup - success", result.success is True)
    check("Stub create_backup - data hat checksum", "checksum" in (result.data or {}))
    check("Stub create_backup - data hat bytes", "bytes" in (result.data or {}))

    result = stub.restore_backup(stub_agent, mock_instance, mock_backup)
    check("Stub restore_backup - success", result.success is True)

    result = stub.delete_backup(stub_agent, mock_instance, mock_backup)
    check("Stub delete_backup - success", result.success is True)


# ================================================================
# Test 5: Backup-Service Integration (mit gemocktem Runner)
# ================================================================
print("\n== Backup-Service Integration ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.blueprints.models import Blueprint as BPModel
    from app.domain.instances.models import Instance
    from app.domain.endpoints.models import Endpoint
    from app.domain.backups.service import create_backup, restore_backup, delete_backup, list_backups
    from app.domain.instances.service import set_runner

    # Testdaten aufbauen
    user = User(username="bkuser", email="bk@test.dev", password_hash="x")
    db.session.add(user)
    db.session.flush()

    bp = BPModel(name="BK-Blueprint", docker_image="test:latest")
    db.session.add(bp)
    db.session.flush()

    agent = Agent(name="svc-agent", fqdn="svc.test.dev",
                  scheme="https", daemon_connect=8080, daemon_token="t")
    db.session.add(agent)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="10.0.0.1", port=25565)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="BackupTestServer", owner_id=user.id,
        agent_id=agent.id, blueprint_id=bp.id,
        memory=512, disk=1024, cpu=100,
    )
    db.session.add(inst)
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    # Wings-Adapter mit Mocks verwenden
    wings_adapter = WingsRunnerAdapter(timeout=(5, 10))
    set_runner(wings_adapter)

    # create_backup via Service - Erfolg
    with patch.object(wings_adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=200,
        data={"checksum": "svc-check", "size": 12345},
    )):
        backup = create_backup(inst, "Service-Test-Backup", ignored_files="*.log")
        check("Service create_backup - is_successful", backup.is_successful is True)
        check("Service create_backup - checksum", backup.checksum == "svc-check")
        check("Service create_backup - bytes", backup.bytes == 12345)
        check("Service create_backup - name", backup.name == "Service-Test-Backup")

    # list_backups
    backups = list_backups(inst)
    check("Service list_backups - hat Eintraege", len(backups) >= 1)

    # restore_backup via Service - Erfolg
    with patch.object(wings_adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=204, data=None,
    )):
        restored_inst = restore_backup(inst, backup)
        check("Service restore_backup - status None (ready)", restored_inst.status is None)

    # restore_backup via Service - Fehler
    with patch.object(wings_adapter._http, "post", return_value=WingsResponse(
        success=False, status_code=502, data=None, error="Bad Gateway",
    )):
        failed_inst = restore_backup(inst, backup)
        check("Service restore_backup fehler - provision_failed", failed_inst.status == "provision_failed")

    # Zuruecksetzen
    inst.status = None
    db.session.commit()

    # delete_backup via Service
    backup_id = backup.id
    with patch.object(wings_adapter._http, "delete", return_value=WingsResponse(
        success=True, status_code=204, data=None,
    )):
        delete_backup(inst, backup)
        remaining = Backup.query.get(backup_id)
        check("Service delete_backup - Backup geloescht", remaining is None)

    # create_backup via Service - Runner-Fehler (Backup bleibt is_successful=False)
    with patch.object(wings_adapter._http, "post", return_value=WingsResponse(
        success=False, status_code=500, data=None, error="Internal",
    )):
        failed_backup = create_backup(inst, "Failed-Backup")
        check("Service create_backup fehler - not successful", failed_backup.is_successful is False)

    # UUID/User-ID fuer spaetere Tests merken
    _inst_uuid = inst.uuid
    _user_id = user.id

    # Aufraeumen: StubRunner zuruecksetzen
    set_runner(StubRunnerAdapter())


# ================================================================
# Test 6: Client-API Backup-Endpunkte (Smoke Test)
# ================================================================
print("\n== Client-API Backup-Endpunkte ==")

with app.app_context():
    client = app.test_client()

    # Backups auflisten - braucht X-User-Id
    r = client.get(f"/api/client/instances/{_inst_uuid}/backups",
                   headers={"X-User-Id": str(_user_id)})
    check("GET /backups - 200", r.status_code == 200)
    data = r.get_json()
    check("GET /backups - ist Liste", isinstance(data, list))


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*50}")
print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*50}\n")

sys.exit(1 if failed else 0)
