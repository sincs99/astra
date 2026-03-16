"""Schnelltests fuer Meilenstein 11 - Wings-Integration."""

import sys
import os
import json
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


# ================================================================
# Test 1: Stub-Adapter (Default)
# ================================================================
print("\n== Adapter-Umschaltung: Stub (default) ==")

app_stub = create_app("testing")
with app_stub.app_context():
    check("Default Adapter = stub", app_stub.config["_RUNNER_ADAPTER_NAME"] == "stub")
    client_stub = app_stub.test_client()

    r = client_stub.get("/api/admin/runner/info")
    check("GET /runner/info -> 200", r.status_code == 200)
    info = r.get_json()
    check("Adapter ist 'stub'", info["adapter"] == "stub")
    check("Timeout vorhanden", "timeout" in info)

# ================================================================
# Test 2: Wings-Adapter per Config
# ================================================================
print("\n== Adapter-Umschaltung: Wings ==")

# Env-Var MUSS vor dem Import der Config gesetzt sein.
# Da Config schon geladen ist, setzen wir app.config direkt:
app_wings = create_app("testing")
app_wings.config["RUNNER_ADAPTER"] = "wings"
# Runner manuell neu initialisieren
from app.infrastructure.runner import WingsRunnerAdapter
from app.domain.instances.service import set_runner
with app_wings.app_context():
    set_runner(WingsRunnerAdapter(timeout=(5, 30)))
    app_wings.config["_RUNNER_ADAPTER_NAME"] = "wings"

with app_wings.app_context():
    check("Wings Adapter konfiguriert", app_wings.config["_RUNNER_ADAPTER_NAME"] == "wings")
    client_wings = app_wings.test_client()

    r = client_wings.get("/api/admin/runner/info")
    info = r.get_json()
    check("Runner-Info zeigt 'wings'", info["adapter"] == "wings")

# ================================================================
# Test 3: Agent-Modell Wings-Felder
# ================================================================
print("\n== Agent-Modell Wings-Felder ==")

app = create_app("testing")
with app.app_context():
    db.create_all()
    from app.domain.agents.models import Agent

    agent = Agent(
        name="test-wings-agent",
        fqdn="node01.test.dev",
        scheme="https",
        daemon_connect=8080,
        daemon_listen=8080,
        daemon_token_id="abc123",
        daemon_token="secret-token-value",
    )
    db.session.add(agent)
    db.session.commit()

    check("Agent scheme", agent.scheme == "https")
    check("Agent daemon_connect", agent.daemon_connect == 8080)
    check("Agent daemon_token_id", agent.daemon_token_id == "abc123")
    check("Agent daemon_token gesetzt", agent.daemon_token == "secret-token-value")
    check("Agent connection_url", agent.get_connection_url() == "https://node01.test.dev:8080")

    # to_dict soll daemon_token NICHT enthalten
    d = agent.to_dict()
    check("to_dict enthaelt NICHT daemon_token", "daemon_token" not in d)
    check("to_dict enthaelt daemon_token_id", "daemon_token_id" in d)
    check("to_dict enthaelt scheme", d["scheme"] == "https")

# ================================================================
# Test 4: ConfigBuilder
# ================================================================
print("\n== ConfigBuilder ==")

with app.app_context():
    from app.domain.users.models import User
    from app.domain.blueprints.models import Blueprint as BPModel
    from app.domain.instances.models import Instance
    from app.domain.endpoints.models import Endpoint

    # Testdaten aufbauen
    user = User(username="testuser", email="test@test.dev", password_hash="x")
    db.session.add(user)
    db.session.flush()

    bp = BPModel(name="Test-Blueprint", docker_image="ghcr.io/test/image:latest")
    db.session.add(bp)
    db.session.flush()

    agent2 = Agent(name="config-agent", fqdn="cfg.test.dev")
    db.session.add(agent2)
    db.session.flush()

    ep = Endpoint(agent_id=agent2.id, ip="192.168.1.10", port=25565)
    db.session.add(ep)
    db.session.flush()

    inst = Instance(
        name="TestServer",
        description="Ein Testserver",
        owner_id=user.id,
        agent_id=agent2.id,
        blueprint_id=bp.id,
        memory=1024,
        swap=256,
        disk=4096,
        io=500,
        cpu=200,
        image="ghcr.io/test/image:latest",
        startup_command="java -jar server.jar",
    )
    db.session.add(inst)
    db.session.flush()

    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    db.session.commit()

    from app.infrastructure.runner.config_builder import build_server_config

    config = build_server_config(inst)

    check("Config hat uuid", config["uuid"] == inst.uuid)
    check("Config hat meta.name", config["meta"]["name"] == "TestServer")
    check("Config hat meta.description", config["meta"]["description"] == "Ein Testserver")
    check("Config suspended = False", config["suspended"] is False)
    check("Config invocation", config["invocation"] == "java -jar server.jar")
    check("Config build.memory_limit", config["build"]["memory_limit"] == 1024)
    check("Config build.swap", config["build"]["swap"] == 256)
    check("Config build.disk_space", config["build"]["disk_space"] == 4096)
    check("Config build.io_weight", config["build"]["io_weight"] == 500)
    check("Config build.cpu_limit", config["build"]["cpu_limit"] == 200)
    check("Config build.oom_killer", config["build"]["oom_killer"] is True)
    check("Config container.image", config["container"]["image"] == "ghcr.io/test/image:latest")
    check("Config allocations.default.ip", config["allocations"]["default"]["ip"] == "192.168.1.10")
    check("Config allocations.default.port", config["allocations"]["default"]["port"] == 25565)
    check("Config allocations.mappings hat IPs", "192.168.1.10" in config["allocations"]["mappings"])
    check("Config environment.SERVER_PORT", config["environment"]["SERVER_PORT"] == "25565")

# ================================================================
# Test 5: WingsHttpClient (mit Mocks)
# ================================================================
print("\n== WingsHttpClient (Mocked) ==")

with app.app_context():
    from app.infrastructure.runner.wings_http import WingsHttpClient, WingsResponse

    http_client = WingsHttpClient(timeout=(5, 10))

    # Mock-Agent
    mock_agent = Agent(
        name="mock-agent", fqdn="mock.test.dev",
        scheme="https", daemon_connect=8080,
        daemon_token="test-token-123",
    )

    # Test: Erfolgreicher Request
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.content = b""
    mock_response.json.side_effect = ValueError()

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_response):
        result = http_client.post(mock_agent, "/api/servers/test-uuid/sync")
        check("Mock POST 204 = success", result.success is True)
        check("Mock POST status_code=204", result.status_code == 204)

    # Test: Fehler-Request
    mock_err_response = MagicMock()
    mock_err_response.status_code = 500
    mock_err_response.content = b'{"error":"internal"}'
    mock_err_response.json.return_value = {"error": "internal"}

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_err_response):
        result = http_client.post(mock_agent, "/api/servers/test-uuid/power", {"action": "start"})
        check("Mock POST 500 = nicht success", result.success is False)
        check("Mock POST error vorhanden", result.error is not None)

    # Test: Timeout
    import requests as req_lib
    with patch("app.infrastructure.runner.wings_http.http_lib.request", side_effect=req_lib.Timeout()):
        result = http_client.get(mock_agent, "/api/servers/test-uuid")
        check("Timeout -> success=False", result.success is False)
        check("Timeout -> error enthaelt 'Timeout'", "Timeout" in (result.error or ""))

    # Test: ConnectionError
    with patch("app.infrastructure.runner.wings_http.http_lib.request", side_effect=req_lib.ConnectionError()):
        result = http_client.get(mock_agent, "/api/servers/test-uuid")
        check("ConnectionError -> success=False", result.success is False)
        check("ConnectionError -> error enthaelt 'nicht erreichbar'", "nicht erreichbar" in (result.error or ""))

# ================================================================
# Test 6: WingsRunnerAdapter (mit Mocks)
# ================================================================
print("\n== WingsRunnerAdapter (Mocked) ==")

with app.app_context():
    from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter
    from app.infrastructure.runner.wings_http import WingsResponse

    adapter = WingsRunnerAdapter(timeout=(5, 10))

    mock_agent = Agent(
        name="wings-agent", fqdn="wings.test.dev",
        scheme="https", daemon_connect=8080,
        daemon_token="token",
    )

    # create_instance - Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(success=True, status_code=200, data=None)):
        result = adapter.create_instance(mock_agent, inst)
        check("create_instance success", result.success is True)
        check("create_instance message", "erstellt" in result.message)

    # create_instance - Fehler
    with patch.object(adapter._http, "post", return_value=WingsResponse(success=False, status_code=502, data=None, error="Bad Gateway")):
        result = adapter.create_instance(mock_agent, inst)
        check("create_instance fehlschlag", result.success is False)

    # sync_instance - Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(success=True, status_code=204, data=None)):
        result = adapter.sync_instance(mock_agent, inst)
        check("sync_instance success", result.success is True)

    # send_power_action - Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(success=True, status_code=204, data=None)):
        result = adapter.send_power_action(mock_agent, inst, "start")
        check("send_power_action success", result.success is True)

    # send_power_action - Fehler
    with patch.object(adapter._http, "post", return_value=WingsResponse(success=False, status_code=None, data=None, error="Timeout")):
        result = adapter.send_power_action(mock_agent, inst, "stop")
        check("send_power_action fehler", result.success is False)

    # delete_instance - Erfolg
    with patch.object(adapter._http, "delete", return_value=WingsResponse(success=True, status_code=204, data=None)):
        result = adapter.delete_instance(mock_agent, inst)
        check("delete_instance success", result.success is True)

# ================================================================
# Test 7: Stub-Adapter funktioniert weiterhin
# ================================================================
print("\n== Stub-Adapter Kompatibilitaet ==")

with app_stub.app_context():
    db.create_all()

    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    stub = StubRunnerAdapter()

    stub_agent = Agent(name="stub-agent", fqdn="stub.test.dev")

    result = stub.create_instance(stub_agent, inst)
    check("Stub create_instance", result.success is True)

    result = stub.sync_instance(stub_agent, inst)
    check("Stub sync_instance", result.success is True)

    result = stub.send_power_action(stub_agent, inst, "start")
    check("Stub send_power_action", result.success is True)

    result = stub.delete_instance(stub_agent, inst)
    check("Stub delete_instance", result.success is True)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*50}")
print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*50}\n")

sys.exit(1 if failed else 0)
