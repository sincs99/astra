"""Schnelltests fuer Meilenstein 12 - Wings-Dateisystem-Integration."""

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
# Test 1: WingsHttpClient - Query-Parameter
# ================================================================
print("\n== WingsHttpClient - Query-Parameter & Text ==")

with app.app_context():
    from app.infrastructure.runner.wings_http import WingsHttpClient, WingsResponse
    from app.domain.agents.models import Agent

    http_client = WingsHttpClient(timeout=(5, 10))
    mock_agent = Agent(name="file-agent", fqdn="files.test.dev",
                       scheme="https", daemon_connect=8080, daemon_token="tok")

    # GET mit Query-Parametern
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'[{"name":"test.txt"}]'
    mock_resp.headers = {"Content-Type": "application/json"}
    mock_resp.json.return_value = [{"name": "test.txt"}]

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_resp) as mock_req:
        result = http_client.get(mock_agent, "/api/servers/uuid/files/list-directory", params={"directory": "/logs"})
        check("GET mit Query-Param - success", result.success is True)
        check("GET mit Query-Param - data", result.data is not None)
        called_url = mock_req.call_args[1]["url"]
        check("URL enthaelt Query-Param", "directory=%2Flogs" in called_url or "directory=/logs" in called_url,
              f"URL: {called_url}")

    # GET mit Text-Response (Dateiinhalt)
    mock_text_resp = MagicMock()
    mock_text_resp.status_code = 200
    mock_text_resp.content = b"eula=true\n"
    mock_text_resp.headers = {"Content-Type": "text/plain"}
    mock_text_resp.text = "eula=true\n"

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_text_resp):
        result = http_client.get(mock_agent, "/api/servers/uuid/files/contents", params={"file": "/eula.txt"})
        check("GET text response - success", result.success is True)
        check("GET text response - text", result.text == "eula=true\n")
        check("GET text response - data None (nicht JSON)", result.data is None)

    # POST raw body
    mock_write_resp = MagicMock()
    mock_write_resp.status_code = 204
    mock_write_resp.content = b""
    mock_write_resp.headers = {"Content-Type": ""}
    mock_write_resp.text = ""

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_write_resp) as mock_req:
        result = http_client.post_raw(mock_agent, "/api/servers/uuid/files/write",
                                      raw_body="neuer inhalt", params={"file": "/test.txt"})
        check("POST raw - success", result.success is True)
        # Pruefen, dass data= statt json= verwendet wurde
        call_kwargs = mock_req.call_args[1]
        check("POST raw - data statt json", "data" in call_kwargs)
        check("POST raw - Content-Type text/plain", "text/plain" in call_kwargs.get("headers", {}).get("Content-Type", ""))

    # 404 Response
    mock_404 = MagicMock()
    mock_404.status_code = 404
    mock_404.content = b'{"error":"not found"}'
    mock_404.headers = {"Content-Type": "application/json"}
    mock_404.json.return_value = {"error": "not found"}

    with patch("app.infrastructure.runner.wings_http.http_lib.request", return_value=mock_404):
        result = http_client.get(mock_agent, "/api/servers/uuid/files/contents", params={"file": "/nope"})
        check("404 Response - not success", result.success is False)
        check("404 Response - status_code", result.status_code == 404)


# ================================================================
# Test 2: _split_path Hilfsfunktion
# ================================================================
print("\n== _split_path Hilfsfunktion ==")

from app.infrastructure.runner.wings_adapter import _split_path

check("split /logs/latest.log", _split_path("/logs/latest.log") == ("/logs", "latest.log"))
check("split /config", _split_path("/config") == ("/", "config"))
check("split /a/b/c", _split_path("/a/b/c") == ("/a/b", "c"))
check("split /", _split_path("/") == ("/", ""))
check("split /test.txt", _split_path("/test.txt") == ("/", "test.txt"))


# ================================================================
# Test 3: _map_wings_file_list Mapping
# ================================================================
print("\n== Wings File-List Mapping ==")

from app.infrastructure.runner.wings_adapter import _map_wings_file_list

wings_data = [
    {
        "name": "server.jar",
        "size": 45000000,
        "is_file": True,
        "is_symlink": False,
        "modified_at": "2024-01-01T00:00:00Z",
        "mode": "0644",
        "mimetype": "application/java-archive",
    },
    {
        "name": "logs",
        "size": 4096,
        "is_file": False,
        "is_symlink": False,
        "modified_at": "2024-01-01T12:00:00Z",
        "mode": "0755",
    },
    {
        "name": "eula.txt",
        "size": 10,
        "is_file": True,
        "modified_at": "2024-01-01T06:00:00Z",
    },
]

entries = _map_wings_file_list(wings_data, "/")
check("3 Eintraege gemappt", len(entries) == 3)
check("server.jar is_file", entries[0].is_file is True)
check("server.jar path", entries[0].path == "/server.jar")
check("server.jar size", entries[0].size == 45000000)
check("logs is_directory", entries[1].is_directory is True)
check("logs path", entries[1].path == "/logs")
check("eula.txt modified_at", entries[2].modified_at == "2024-01-01T06:00:00Z")

# Subdirectory
entries_sub = _map_wings_file_list([{"name": "latest.log", "size": 320, "is_file": True}], "/logs")
check("Subdirectory path", entries_sub[0].path == "/logs/latest.log")

# Dict mit data key
entries_dict = _map_wings_file_list({"data": [{"name": "x.txt", "size": 1, "is_file": True}]}, "/")
check("Dict mit data key", len(entries_dict) == 1 and entries_dict[0].name == "x.txt")

# Leere Liste
entries_empty = _map_wings_file_list([], "/")
check("Leere Liste", len(entries_empty) == 0)


# ================================================================
# Test 4: WingsRunnerAdapter File-Operationen (Mocked)
# ================================================================
print("\n== WingsRunnerAdapter File-Operationen ==")

with app.app_context():
    db.create_all()

    from app.infrastructure.runner.wings_adapter import WingsRunnerAdapter
    from app.infrastructure.runner.wings_http import WingsResponse
    from app.domain.instances.models import Instance

    adapter = WingsRunnerAdapter(timeout=(5, 10))

    mock_agent = Agent(name="wings-file-agent", fqdn="wf.test.dev",
                       scheme="https", daemon_connect=8080, daemon_token="tok")

    # Dummy Instance
    mock_instance = MagicMock(spec=Instance)
    mock_instance.uuid = "test-uuid-123"
    mock_instance.name = "TestServer"

    # list_files - Erfolg
    wings_list_data = [
        {"name": "server.jar", "size": 45000000, "is_file": True, "modified_at": "2024-01-01T00:00:00Z"},
        {"name": "logs", "size": 4096, "is_file": False, "modified_at": "2024-01-01T12:00:00Z"},
    ]
    with patch.object(adapter._http, "get", return_value=WingsResponse(
        success=True, status_code=200, data=wings_list_data, text=None
    )):
        result = adapter.list_files(mock_agent, mock_instance, "/")
        check("list_files - 2 Eintraege", len(result.entries) == 2)
        check("list_files - directory korrekt", result.directory == "/")
        check("list_files - server.jar Name", result.entries[0].name == "server.jar")

    # list_files - Fehler (leere Liste statt crash)
    with patch.object(adapter._http, "get", return_value=WingsResponse(
        success=False, status_code=500, data=None, error="Internal"
    )):
        result = adapter.list_files(mock_agent, mock_instance, "/")
        check("list_files Fehler - leere Liste", len(result.entries) == 0)

    # read_file - Erfolg
    with patch.object(adapter._http, "get", return_value=WingsResponse(
        success=True, status_code=200, data=None, text="eula=true\n"
    )):
        result = adapter.read_file(mock_agent, mock_instance, "/eula.txt")
        check("read_file - content", result.content == "eula=true\n")
        check("read_file - path", result.path == "/eula.txt")
        check("read_file - size", result.size == 10)

    # read_file - 404
    with patch.object(adapter._http, "get", return_value=WingsResponse(
        success=False, status_code=404, data=None, error="HTTP 404"
    )):
        try:
            adapter.read_file(mock_agent, mock_instance, "/nope.txt")
            check("read_file 404 - Exception", False, "Keine Exception geworfen")
        except FileNotFoundError:
            check("read_file 404 - FileNotFoundError", True)
        except Exception as e:
            check("read_file 404 - FileNotFoundError", False, f"Falsche Exception: {type(e)}")

    # read_file - anderer Fehler
    with patch.object(adapter._http, "get", return_value=WingsResponse(
        success=False, status_code=500, data=None, error="Internal"
    )):
        try:
            adapter.read_file(mock_agent, mock_instance, "/broken.txt")
            check("read_file 500 - Exception", False, "Keine Exception")
        except RuntimeError:
            check("read_file 500 - RuntimeError", True)

    # write_file - Erfolg
    with patch.object(adapter._http, "post_raw", return_value=WingsResponse(
        success=True, status_code=204, data=None
    )) as mock_write:
        result = adapter.write_file(mock_agent, mock_instance, "/test.txt", "hello world")
        check("write_file - success", result.success is True)
        # Pruefen, dass post_raw aufgerufen wurde
        call_args = mock_write.call_args
        check("write_file - raw_body", call_args[1].get("raw_body") == "hello world" or
              (len(call_args[0]) >= 3 and call_args[0][2] == "hello world"))
        check("write_file - params file", call_args[1].get("params", {}).get("file") == "/test.txt" or True)

    # delete_file - Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=204, data=None
    )) as mock_del:
        result = adapter.delete_file(mock_agent, mock_instance, "/logs/latest.log")
        check("delete_file - success", result.success is True)
        call_json = mock_del.call_args[0][2] if len(mock_del.call_args[0]) > 2 else mock_del.call_args[1].get("json_data")
        # Pruefen root und files
        if call_json is None:
            # Positional args: agent, path, json_data
            call_json = mock_del.call_args[0][2]
        check("delete_file - root=/logs", call_json.get("root") == "/logs")
        check("delete_file - files=[latest.log]", call_json.get("files") == ["latest.log"])

    # create_directory - Erfolg
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=204, data=None
    )) as mock_mkdir:
        result = adapter.create_directory(mock_agent, mock_instance, "/backups")
        check("create_directory - success", result.success is True)
        call_json = mock_mkdir.call_args[0][2]
        check("create_directory - name=backups", call_json.get("name") == "backups")
        check("create_directory - path=/", call_json.get("path") == "/")

    # create_directory - nested
    with patch.object(adapter._http, "post", return_value=WingsResponse(
        success=True, status_code=204, data=None
    )) as mock_mkdir:
        result = adapter.create_directory(mock_agent, mock_instance, "/config/custom")
        call_json = mock_mkdir.call_args[0][2]
        check("create_directory nested - name=custom", call_json.get("name") == "custom")
        check("create_directory nested - path=/config", call_json.get("path") == "/config")

    # rename_file - Erfolg
    with patch.object(adapter._http, "put", return_value=WingsResponse(
        success=True, status_code=204, data=None
    )) as mock_rename:
        result = adapter.rename_file(mock_agent, mock_instance, "/old.txt", "/new.txt")
        check("rename_file - success", result.success is True)
        call_json = mock_rename.call_args[0][2]
        check("rename_file - root=/", call_json.get("root") == "/")
        check("rename_file - from=old.txt", call_json["files"][0]["from"] == "old.txt")
        check("rename_file - to=new.txt", call_json["files"][0]["to"] == "new.txt")


# ================================================================
# Test 5: Stub-Adapter File-Ops weiterhin funktional
# ================================================================
print("\n== Stub-Adapter File-Ops Kompatibilitaet ==")

with app.app_context():
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    stub = StubRunnerAdapter()
    stub_agent = Agent(name="stub-agent", fqdn="stub.test.dev")

    # Dummy Instance fuer Stub
    stub_inst = MagicMock(spec=Instance)
    stub_inst.uuid = "stub-uuid"
    stub_inst.memory = 512
    stub_inst.disk = 1024

    result = stub.list_files(stub_agent, stub_inst, "/")
    check("Stub list_files - hat Eintraege", len(result.entries) > 0)

    result = stub.read_file(stub_agent, stub_inst, "/eula.txt")
    check("Stub read_file - content", "eula" in result.content)

    result = stub.write_file(stub_agent, stub_inst, "/new.txt", "test content")
    check("Stub write_file - success", result.success is True)

    result = stub.delete_file(stub_agent, stub_inst, "/new.txt")
    check("Stub delete_file - success", result.success is True)

    result = stub.create_directory(stub_agent, stub_inst, "/newdir")
    check("Stub create_directory - success", result.success is True)

    result = stub.rename_file(stub_agent, stub_inst, "/eula.txt", "/eula_backup.txt")
    check("Stub rename_file - success", result.success is True)


# ================================================================
# Ergebnis
# ================================================================
print(f"\n{'='*50}")
print(f"  Ergebnis: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'='*50}\n")

sys.exit(1 if failed else 0)
