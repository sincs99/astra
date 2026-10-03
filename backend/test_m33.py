"""Tests fuer Meilenstein 33 – Wings Remote-API.

Deckt ab:
a) Node-Token-Auth (401/400/403, deaktivierter Agent, last_seen-Update)
b) Server-Endpunkte (Liste paginiert, Details, Install GET/POST, Container-Status, Reset, Transfer)
c) Config-Builder (settings, process_configuration, Platzhalter in config_files)
d) SFTP-Auth im Wings-Format (Passwort, Public Key, Collaborator-Mapping, Suspension, Fremd-Agent)
e) Activity-Ingestion
f) Backup-/Restore-Callbacks (asynchroner Abschluss)
g) Admin: Credentials beim Anlegen, config.yml-Export, Rotation, PATCH, Blueprint-Felder, Admin-Schutz
h) Regression: /api/agent-Endpunkte und Stub-Backups funktionieren weiter
"""

import sys
import os
import json
import struct
import base64

sys.path.insert(0, os.path.dirname(__file__))
os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db

passed = 0
failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  OK  {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  FAIL {label}" + (f" – {detail}" if detail else ""))


def check(label, condition, detail=""):
    if condition:
        ok(label)
    else:
        fail(label, detail)


def _make_ed25519_public_key(seed: bytes) -> str:
    key_type = b"ssh-ed25519"
    body = struct.pack(">I", len(key_type)) + key_type
    body += struct.pack(">I", len(seed)) + seed
    return f"ssh-ed25519 {base64.b64encode(body).decode('ascii')} m33-key"


KEY_OWNER = _make_ed25519_public_key(b"\x41" * 32)
KEY_STRANGER = _make_ed25519_public_key(b"\x42" * 32)

app = create_app("testing")
app.config["TESTING"] = True
app.config["BASE_URL"] = "https://panel.m33.test"
client = app.test_client()

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
    from app.domain.instances.service import set_runner, STATUS_READY, STATUS_PROVISIONING
    from app.domain.collaborators.models import Collaborator
    from app.domain.ssh_keys.models import UserSshKey
    from app.domain.ssh_keys.validator import compute_fingerprint
    from app.infrastructure.runner.stub_adapter import StubRunnerAdapter

    set_runner(StubRunnerAdapter())

    owner = User(username="m33-owner", email="m33owner@test.dev")
    owner.set_password("ownerpass")
    collab = User(username="m33-collab", email="m33collab@test.dev")
    collab.set_password("collabpass")
    nobody = User(username="m33-nobody", email="m33nobody@test.dev")
    nobody.set_password("nobodypass")
    admin = User(username="m33-admin", email="m33admin@test.dev", is_admin=True)
    admin.set_password("adminpass")
    db.session.add_all([owner, collab, nobody, admin])
    db.session.flush()

    agent = Agent(name="m33-node", fqdn="node.m33.test", scheme="https", daemon_listen=8080, daemon_sftp=2022)
    agent.generate_daemon_credentials()
    other_agent = Agent(name="m33-other", fqdn="other.m33.test")
    other_agent.generate_daemon_credentials()
    inactive_agent = Agent(name="m33-inactive", fqdn="inactive.m33.test", is_active=False)
    inactive_agent.generate_daemon_credentials()
    db.session.add_all([agent, other_agent, inactive_agent])
    db.session.flush()

    bp = Blueprint(
        name="m33-minecraft",
        docker_image="ghcr.io/pterodactyl/yolks:java_21",
        startup_command="java -Xmx{{SERVER_MEMORY}}M -jar server.jar",
        install_script="#!/bin/bash\necho install",
        install_container="ghcr.io/pterodactyl/installers:debian",
        install_entrypoint="bash",
        variables=[
            {"name": "Version", "env_var": "MC_VERSION", "default_value": "latest",
             "user_viewable": True, "user_editable": True},
        ],
        config_startup={"done": [")! For help, type "], "strip_ansi": False},
        config_stop="stop",
        config_files={
            "server.properties": {
                "parser": "properties",
                "find": {
                    "server-ip": "0.0.0.0",
                    "server-port": "{{server.build.default.port}}",
                    "motd": "{{env.MC_VERSION}} on {{server.meta.name}}",
                    "query.port": "{{server.build.default.port}}",
                },
            },
            "broken": "not-an-object",
        },
        file_denylist=["*.jar"],
    )
    db.session.add(bp)
    db.session.flush()

    ep = Endpoint(agent_id=agent.id, ip="10.0.0.5", port=25565)
    ep2 = Endpoint(agent_id=agent.id, ip="10.0.0.5", port=25566)
    ep_other = Endpoint(agent_id=other_agent.id, ip="10.0.1.5", port=25565)
    db.session.add_all([ep, ep2, ep_other])
    db.session.flush()

    inst = Instance(
        name="m33-server", owner_id=owner.id, agent_id=agent.id, blueprint_id=bp.id,
        status=STATUS_READY, memory=2048, swap=0, disk=10240, io=500, cpu=200,
        image=bp.docker_image, startup_command=bp.startup_command,
        variable_values={"MC_VERSION": "1.21"},
    )
    inst2 = Instance(
        name="m33-second", owner_id=owner.id, agent_id=agent.id, blueprint_id=bp.id,
        status=STATUS_PROVISIONING, memory=1024, disk=4096,
    )
    inst_other = Instance(
        name="m33-foreign", owner_id=owner.id, agent_id=other_agent.id, blueprint_id=bp.id,
        status=STATUS_READY, memory=1024, disk=4096,
    )
    db.session.add_all([inst, inst2, inst_other])
    db.session.flush()
    ep.instance_id = inst.id
    inst.primary_endpoint_id = ep.id
    ep2.instance_id = inst.id
    ep_other.instance_id = inst_other.id
    inst_other.primary_endpoint_id = ep_other.id

    db.session.add(Collaborator(user_id=collab.id, instance_id=inst.id,
                                permissions=["file.read", "file.update", "file.sftp"]))
    db.session.add(UserSshKey(user_id=owner.id, name="owner-key", public_key=KEY_OWNER,
                              fingerprint=compute_fingerprint(KEY_OWNER)))
    db.session.commit()

    _owner_id = owner.id
    _collab_id = collab.id
    _admin_id = admin.id
    _nobody_id = nobody.id
    _agent_id = agent.id
    _other_agent_id = other_agent.id
    _inactive_agent_id = inactive_agent.id
    _bp_id = bp.id
    _inst_id = inst.id
    _inst_uuid = inst.uuid
    _inst2_id = inst2.id
    _inst2_uuid = inst2.uuid
    _inst_other_uuid = inst_other.uuid
    NODE_AUTH = {"Authorization": f"Bearer {agent.daemon_token_id}.{agent.daemon_token}"}
    OTHER_AUTH = {"Authorization": f"Bearer {other_agent.daemon_token_id}.{other_agent.daemon_token}"}
    INACTIVE_AUTH = {"Authorization": f"Bearer {inactive_agent.daemon_token_id}.{inactive_agent.daemon_token}"}
    _token_id = agent.daemon_token_id
    _token = agent.daemon_token


def admin_headers():
    return {"X-User-Id": str(_admin_id)}


# ================================================================
# a) Node-Token-Auth
# ================================================================

print("\n=== a) Node-Token-Auth ===")

resp = client.get("/api/remote/servers")
check("Ohne Authorization -> 401", resp.status_code == 401, str(resp.status_code))
check("401 traegt WWW-Authenticate: Bearer", resp.headers.get("WWW-Authenticate") == "Bearer")

resp = client.get("/api/remote/servers", headers={"Authorization": "Bearer nurEinTeil"})
check("Token ohne Punkt -> 400", resp.status_code == 400, str(resp.status_code))

resp = client.get("/api/remote/servers", headers={"Authorization": "Bearer unknownid.sometoken"})
check("Unbekannte token_id -> 403", resp.status_code == 403, str(resp.status_code))

resp = client.get("/api/remote/servers", headers={"Authorization": f"Bearer {_token_id}.falsch"})
check("Falscher Token -> 403", resp.status_code == 403, str(resp.status_code))

resp = client.get("/api/remote/servers", headers={"Authorization": f"Basic {_token_id}.{_token}"})
check("Kein Bearer-Schema -> 401", resp.status_code == 401, str(resp.status_code))

resp = client.get("/api/remote/servers", headers=INACTIVE_AUTH)
check("Deaktivierter Agent -> 403", resp.status_code == 403, str(resp.status_code))

resp = client.get("/api/remote/servers", headers=NODE_AUTH)
check("Gueltiger Token -> 200", resp.status_code == 200, str(resp.status_code))

with app.app_context():
    a = db.session.get(Agent, _agent_id)
    check("Authentifizierter Request setzt last_seen_at", a.last_seen_at is not None)
    check("Agent-Health nach Request = healthy", a.get_health_status() == "healthy", a.get_health_status())

with app.app_context():
    from app.domain.agents.models import DAEMON_TOKEN_ID_LENGTH, DAEMON_TOKEN_LENGTH
    check("token_id hat 16 Zeichen", len(_token_id) == DAEMON_TOKEN_ID_LENGTH == 16)
    check("token hat 64 Zeichen", len(_token) == DAEMON_TOKEN_LENGTH == 64)
    check("token ist alphanumerisch (kein Punkt)", _token.isalnum() and _token_id.isalnum())


# ================================================================
# b) Server-Endpunkte
# ================================================================

print("\n=== b) Server-Endpunkte ===")

resp = client.get("/api/remote/servers?per_page=1", headers=NODE_AUTH)
body = resp.get_json()
check("Liste: data hat 1 Element bei per_page=1", len(body["data"]) == 1)
check("Liste: meta.total = 2 (nur eigene Server)", body["meta"]["total"] == 2, str(body["meta"]))
check("Liste: meta.last_page = 2", body["meta"]["last_page"] == 2)
check("Liste: meta.current_page = 1", body["meta"]["current_page"] == 1)
check("Liste: Element hat uuid/settings/process_configuration",
      set(body["data"][0].keys()) == {"uuid", "settings", "process_configuration"})

resp = client.get("/api/remote/servers?per_page=1&page=2", headers=NODE_AUTH)
body2 = resp.get_json()
check("Liste Seite 2: anderes Element", body2["data"][0]["uuid"] != body["data"][0]["uuid"])
uuids = {body["data"][0]["uuid"], body2["data"][0]["uuid"]}
check("Liste enthaelt keine fremden Server", _inst_other_uuid not in uuids and uuids == {_inst_uuid, _inst2_uuid})

resp = client.get("/api/remote/servers?per_page=abc&page=-3", headers=NODE_AUTH)
check("Liste: ungueltige Paging-Parameter -> Defaults, 200", resp.status_code == 200)

resp = client.get(f"/api/remote/servers/{_inst_uuid}", headers=NODE_AUTH)
check("Details -> 200", resp.status_code == 200, str(resp.status_code))
details = resp.get_json()
settings = details["settings"]
check("Details: settings.uuid", settings["uuid"] == _inst_uuid)
check("Details: settings.build.memory_limit = 2048", settings["build"]["memory_limit"] == 2048)
check("Details: settings.build.cpu_limit = 200", settings["build"]["cpu_limit"] == 200)
check("Details: allocations.default = 10.0.0.5:25565",
      settings["allocations"]["default"] == {"ip": "10.0.0.5", "port": 25565})
check("Details: allocations.mappings enthaelt beide Ports",
      sorted(settings["allocations"]["mappings"]["10.0.0.5"]) == [25565, 25566])
check("Details: environment.SERVER_PORT = 25565", settings["environment"]["SERVER_PORT"] == "25565")
check("Details: environment.MC_VERSION aus variable_values", settings["environment"]["MC_VERSION"] == "1.21")
check("Details: environment.P_SERVER_UUID", settings["environment"]["P_SERVER_UUID"] == _inst_uuid)
check("Details: egg.file_denylist", settings["egg"]["file_denylist"] == ["*.jar"])
check("Details: egg.id = Blueprint-ID als String", settings["egg"]["id"] == str(_bp_id))
check("Details: suspended = false", settings["suspended"] is False)
check("Details: container.image", settings["container"]["image"] == "ghcr.io/pterodactyl/yolks:java_21")

resp = client.get(f"/api/remote/servers/{_inst_uuid[:8]}", headers=NODE_AUTH)
check("Details per Kurz-UUID -> 200", resp.status_code == 200 and resp.get_json()["settings"]["uuid"] == _inst_uuid)

resp = client.get(f"/api/remote/servers/{_inst_other_uuid}", headers=NODE_AUTH)
check("Details fremder Server -> 404", resp.status_code == 404, str(resp.status_code))

resp = client.get(f"/api/remote/servers/{_inst_other_uuid}", headers=OTHER_AUTH)
check("Details fremder Server mit richtigem Agent -> 200", resp.status_code == 200)

# Install GET
resp = client.get(f"/api/remote/servers/{_inst_uuid}/install", headers=NODE_AUTH)
inst_body = resp.get_json()
check("Install GET -> 200", resp.status_code == 200)
check("Install: container_image", inst_body["container_image"] == "ghcr.io/pterodactyl/installers:debian")
check("Install: entrypoint", inst_body["entrypoint"] == "bash")
check("Install: script", inst_body["script"].startswith("#!/bin/bash"))

# Install POST (inst2 ist provisioning)
resp = client.post(f"/api/remote/servers/{_inst2_uuid}/install", headers=NODE_AUTH, json={})
check("Install POST ohne successful -> 422", resp.status_code == 422, str(resp.status_code))

resp = client.post(f"/api/remote/servers/{_inst2_uuid}/install", headers=NODE_AUTH,
                   json={"successful": True, "reinstall": False})
check("Install POST successful -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    i2 = db.session.get(Instance, _inst2_id)
    check("Install POST: Status provisioning -> ready", i2.status is None, str(i2.status))
    check("Install POST: installed_at gesetzt", i2.installed_at is not None)

with app.app_context():
    i2 = db.session.get(Instance, _inst2_id)
    i2.status = "reinstalling"
    db.session.commit()
resp = client.post(f"/api/remote/servers/{_inst2_uuid}/install", headers=NODE_AUTH,
                   json={"successful": False, "reinstall": True})
check("Install POST failed (reinstall) -> 204", resp.status_code == 204)
with app.app_context():
    i2 = db.session.get(Instance, _inst2_id)
    check("Install POST failed: Status reinstall_failed", i2.status == "reinstall_failed", str(i2.status))
    i2.status = None
    db.session.commit()

# Container-Status
resp = client.post(f"/api/remote/servers/{_inst_uuid}/container/status", headers=NODE_AUTH,
                   json={"data": {"new_state": "running"}})
check("Container-Status running -> 200 {}", resp.status_code == 200 and resp.get_json() == {})
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Container-Status: container_state = running", i.container_state == "running", str(i.container_state))

resp = client.post(f"/api/remote/servers/{_inst_uuid}/container/status", headers=NODE_AUTH,
                   json={"data": {"new_state": "offline"}})
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Container-Status offline uebernommen", i.container_state == "offline", str(i.container_state))

resp = client.post(f"/api/remote/servers/{_inst_uuid}/container/status", headers=NODE_AUTH,
                   json={"data": {"new_state": "exploding"}})
check("Container-Status unbekannt -> 200, ignoriert", resp.status_code == 200)
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Container-Status unbekannt aendert nichts", i.container_state == "offline")

# Reset
with app.app_context():
    i2 = db.session.get(Instance, _inst2_id)
    i2.status = "restoring"
    i_other = Instance.query.filter_by(uuid=_inst_other_uuid).first()
    i_other.status = "provisioning"
    db.session.commit()
resp = client.post("/api/remote/servers/reset", headers=NODE_AUTH)
check("Reset -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    i2 = db.session.get(Instance, _inst2_id)
    i_other = Instance.query.filter_by(uuid=_inst_other_uuid).first()
    check("Reset: restoring -> ready auf eigenem Agent", i2.status is None, str(i2.status))
    check("Reset: fremder Agent unberuehrt", i_other.status == "provisioning", str(i_other.status))
    i_other.status = None
    db.session.commit()

# Transfer
resp = client.post(f"/api/remote/servers/{_inst_uuid}/transfer/success", headers=NODE_AUTH)
check("Transfer success ohne laufenden Transfer -> 409", resp.status_code == 409, str(resp.status_code))
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    i.status = "transferring"
    db.session.commit()
resp = client.get(f"/api/remote/servers/{_inst_uuid}/transfer/failure", headers=NODE_AUTH)
check("Transfer failure (GET) -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Transfer failure: Status transfer_failed", i.status == "transfer_failed", str(i.status))
    i.status = "transferring"
    db.session.commit()
resp = client.post(f"/api/remote/servers/{_inst_uuid}/transfer/success", headers=NODE_AUTH)
check("Transfer success (POST) -> 204", resp.status_code == 204)
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Transfer success: Status ready", i.status is None, str(i.status))


# ================================================================
# c) Config-Builder / process_configuration
# ================================================================

print("\n=== c) Config-Builder ===")

proc = details["process_configuration"]
check("process_configuration.startup.done", proc["startup"]["done"] == [")! For help, type "])
check("process_configuration.startup.strip_ansi = false", proc["startup"]["strip_ansi"] is False)
check("process_configuration.startup.user_interaction = []", proc["startup"]["user_interaction"] == [])
check("process_configuration.stop = command/stop", proc["stop"] == {"type": "command", "value": "stop"})
check("configs: kaputter Eintrag wird uebersprungen", len(proc["configs"]) == 1, str(len(proc["configs"])))
cfg = proc["configs"][0]
check("configs[0].file = server.properties", cfg["file"] == "server.properties")
check("configs[0].parser = properties", cfg["parser"] == "properties")
check("configs[0] hat kein find mehr", "find" not in cfg)
replace_map = {r["match"]: r["replace_with"] for r in cfg["replace"]}
check("Platzhalter server.build.default.port -> 25565", replace_map.get("server-port") == "25565", str(replace_map))
check("Platzhalter env.X + server.meta.name", replace_map.get("motd") == "1.21 on m33-server", str(replace_map.get("motd")))
check("Statischer Wert bleibt", replace_map.get("server-ip") == "0.0.0.0")

with app.app_context():
    from app.infrastructure.runner.config_builder import (
        build_process_configuration, build_install_payload, _replace_placeholders,
    )
    b = db.session.get(Blueprint, _bp_id)
    b.config_stop = "^sigterm"
    db.session.commit()
    i = db.session.get(Instance, _inst_id)
    p = build_process_configuration(i)
    check("config_stop ^sigterm -> signal/SIGTERM", p["stop"] == {"type": "signal", "value": "SIGTERM"}, str(p["stop"]))
    b.config_stop = "stop"
    b.config_startup = {"done": "Done ("}
    db.session.commit()
    p = build_process_configuration(i)
    check("config_startup.done als String -> Liste", p["startup"]["done"] == ["Done ("], str(p["startup"]))
    b.config_startup = {"done": [")! For help, type "], "strip_ansi": False}
    db.session.commit()

    check("{{config.docker.interface}} bleibt stehen",
          _replace_placeholders("{{config.docker.interface}}", {}) == "{{config.docker.interface}}")
    check("Unbekannter server.-Pfad -> leer",
          _replace_placeholders("x{{server.nicht.da}}y", {"build": {}}) == "xy")

    # Blueprint ohne Install-Felder -> Defaults
    b.install_container = None
    b.install_entrypoint = None
    db.session.commit()
    payload = build_install_payload(i)
    check("Install-Defaults: container", payload["container_image"] == "ghcr.io/pterodactyl/installers:debian")
    check("Install-Defaults: entrypoint", payload["entrypoint"] == "bash")
    b.install_container = "ghcr.io/pterodactyl/installers:debian"
    b.install_entrypoint = "bash"
    db.session.commit()


# ================================================================
# d) SFTP-Auth
# ================================================================

print("\n=== d) SFTP-Auth (Wings-Format) ===")

short = _inst_uuid[:8]


def sftp(payload, headers=NODE_AUTH):
    return client.post("/api/remote/sftp/auth", headers=headers, json=payload)


resp = sftp({"type": "password", "username": f"m33-owner.{short}", "password": "ownerpass"})
check("Owner Passwort -> 200", resp.status_code == 200, f"{resp.status_code} {resp.get_data(as_text=True)}")
body = resp.get_json()
check("Owner: server = volle UUID", body["server"] == _inst_uuid)
check("Owner: user = User-ID", body["user"] == str(_owner_id))
check("Owner: alle SFTP-Permissions",
      set(body["permissions"]) == {"file.read", "file.read-content", "file.create", "file.update", "file.delete"},
      str(body["permissions"]))

resp = sftp({"type": "password", "username": f"M33-Owner.{_inst_uuid}", "password": "ownerpass"})
check("Username case-insensitive + volle UUID -> 200", resp.status_code == 200, str(resp.status_code))

resp = sftp({"type": "password", "username": f"m33-owner.{short}", "password": "falsch"})
check("Owner falsches Passwort -> 403", resp.status_code == 403, str(resp.status_code))

resp = sftp({"type": "password", "username": "m33-owner", "password": "ownerpass"})
check("Username ohne Server-Teil -> 400", resp.status_code == 400, str(resp.status_code))

resp = sftp({"type": "password", "username": f"m33-owner.{short}"})
check("Ohne password -> 400", resp.status_code == 400, str(resp.status_code))

resp = sftp({"type": "password", "username": f"gibtsnicht.{short}", "password": "x"})
check("Unbekannter User -> 403", resp.status_code == 403, str(resp.status_code))

resp = sftp({"type": "password", "username": f"m33-owner.{_inst_other_uuid[:8]}", "password": "ownerpass"})
check("Server auf anderem Agent -> 403", resp.status_code == 403, str(resp.status_code))

resp = sftp({"type": "password", "username": f"m33-nobody.{short}", "password": "nobodypass"})
check("User ohne Bezug zur Instance -> 403", resp.status_code == 403, str(resp.status_code))

resp = sftp({"type": "password", "username": f"m33-collab.{short}", "password": "collabpass"})
check("Collaborator mit file.sftp -> 200", resp.status_code == 200, str(resp.status_code))
perms = set(resp.get_json()["permissions"])
check("Collaborator-Mapping: read -> read + read-content, update -> update + create, kein delete",
      perms == {"file.read", "file.read-content", "file.update", "file.create"}, str(perms))

resp = sftp({"type": "password", "username": f"m33-admin.{short}", "password": "adminpass"})
check("Admin -> 200 mit allen Rechten", resp.status_code == 200 and len(resp.get_json()["permissions"]) == 5)

with app.app_context():
    c = Collaborator.query.filter_by(user_id=_collab_id, instance_id=_inst_id).first()
    c.permissions = ["file.read", "file.update"]
    db.session.commit()
resp = sftp({"type": "password", "username": f"m33-collab.{short}", "password": "collabpass"})
check("Collaborator ohne file.sftp -> 403", resp.status_code == 403, str(resp.status_code))
with app.app_context():
    c = Collaborator.query.filter_by(user_id=_collab_id, instance_id=_inst_id).first()
    c.permissions = ["file.read", "file.update", "file.sftp"]
    db.session.commit()

# Public Key
resp = sftp({"type": "public_key", "username": f"m33-owner.{short}", "password": KEY_OWNER})
check("Owner Public Key -> 200", resp.status_code == 200, f"{resp.status_code} {resp.get_data(as_text=True)}")
resp = sftp({"type": "public_key", "username": f"m33-owner.{short}", "password": KEY_STRANGER})
check("Unbekannter Public Key -> 403", resp.status_code == 403, str(resp.status_code))
resp = sftp({"type": "public_key", "username": f"m33-owner.{short}", "password": "kein-key"})
check("Kaputter Public Key -> 403", resp.status_code == 403, str(resp.status_code))

# Suspension
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    i.status = "suspended"
    db.session.commit()
resp = sftp({"type": "password", "username": f"m33-owner.{short}", "password": "ownerpass"})
check("Suspendierte Instance -> 403 (Passwort)", resp.status_code == 403, str(resp.status_code))
resp = sftp({"type": "public_key", "username": f"m33-owner.{short}", "password": KEY_OWNER})
check("Suspendierte Instance -> 403 (Key)", resp.status_code == 403, str(resp.status_code))
resp = client.get(f"/api/remote/servers/{_inst_uuid}", headers=NODE_AUTH)
check("Details: suspended = true waehrend Suspension", resp.get_json()["settings"]["suspended"] is True)
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    i.status = None
    db.session.commit()

resp = sftp({"type": "password", "username": f"m33-owner.{short}", "password": "ownerpass"}, headers={})
check("SFTP ohne Node-Auth -> 401", resp.status_code == 401)


# ================================================================
# e) Activity
# ================================================================

print("\n=== e) Activity-Ingestion ===")

with app.app_context():
    from app.domain.activity.models import ActivityLog
    before = ActivityLog.query.filter_by(subject_type="instance", subject_id=_inst_id).count()

resp = client.post("/api/remote/activity", headers=NODE_AUTH, json={"data": [
    {"user": str(_owner_id), "server": _inst_uuid, "event": "server:power.start",
     "metadata": {"action": "start"}, "ip": "203.0.113.7", "timestamp": "2026-10-03T10:00:00.123456Z"},
    {"user": "", "server": _inst_uuid, "event": "server:console.command",
     "metadata": {"command": "say hi"}, "ip": "", "timestamp": "kaputt"},
    {"user": str(_owner_id), "server": _inst_other_uuid, "event": "server:power.start",
     "metadata": {}, "ip": "", "timestamp": "2026-10-03T10:00:00Z"},
    {"user": str(_owner_id), "server": _inst_uuid, "event": "nicht:server",
     "metadata": {}, "ip": "", "timestamp": "2026-10-03T10:00:00Z"},
    "garbage",
]})
check("Activity -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    logs = ActivityLog.query.filter_by(subject_type="instance", subject_id=_inst_id) \
        .filter(ActivityLog.event.like("server:%")).order_by(ActivityLog.id.asc()).all()
    check("Activity: genau 2 Events gespeichert (fremder Server + Nicht-server-Event ignoriert)",
          len(logs) == 2, str([l.event for l in logs]))
    start = next((l for l in logs if l.event == "server:power.start"), None)
    cmd = next((l for l in logs if l.event == "server:console.command"), None)
    check("Activity: actor_id aus user_uuid aufgeloest", start is not None and start.actor_id == _owner_id)
    check("Activity: ip uebernommen", start is not None and start.ip_address == "203.0.113.7")
    check("Activity: properties = metadata", start is not None and start.properties == {"action": "start"})
    check("Activity: Timestamp mit Nanosekunden geparst", start is not None and start.created_at.year == 2026
          and start.created_at.hour == 10)
    check("Activity: ohne User -> actor_type agent", cmd is not None and cmd.actor_type == "agent" and cmd.actor_id is None)
    check("Activity: kaputter Timestamp -> original_timestamp in properties",
          cmd is not None and cmd.properties.get("original_timestamp") == "kaputt")
    after_total = ActivityLog.query.filter_by(subject_type="instance", subject_id=_inst_id).count()
    check("Activity: Zaehler +2", after_total == before + 2, f"{before} -> {after_total}")

resp = client.post("/api/remote/activity", headers=NODE_AUTH, json={"data": "nope"})
check("Activity ohne Liste -> 422", resp.status_code == 422)


# ================================================================
# f) Backups
# ================================================================

print("\n=== f) Backup-/Restore-Callbacks ===")

with app.app_context():
    from app.domain.backups.models import Backup
    pending = Backup(instance_id=_inst_id, name="pending", is_successful=False, is_locked=True)
    done = Backup(instance_id=_inst_id, name="done", is_successful=True)
    foreign = Backup(instance_id=Instance.query.filter_by(uuid=_inst_other_uuid).first().id,
                     name="foreign", is_successful=False)
    db.session.add_all([pending, done, foreign])
    db.session.commit()
    _pending_uuid, _done_uuid, _foreign_uuid = pending.uuid, done.uuid, foreign.uuid

resp = client.get(f"/api/remote/backups/{_pending_uuid}?size=100", headers=NODE_AUTH)
check("Backup GET (S3) -> 400 kein S3-Adapter", resp.status_code == 400, str(resp.status_code))
resp = client.get("/api/remote/backups/unbekannt?size=100", headers=NODE_AUTH)
check("Backup GET unbekannt -> 404", resp.status_code == 404)

resp = client.post(f"/api/remote/backups/{_foreign_uuid}", headers=NODE_AUTH, json={"successful": True})
check("Backup-Status fremder Agent -> 404", resp.status_code == 404, str(resp.status_code))

resp = client.post(f"/api/remote/backups/{_done_uuid}", headers=NODE_AUTH, json={"successful": True})
check("Backup-Status bereits erfolgreich -> 400", resp.status_code == 400, str(resp.status_code))

resp = client.post(f"/api/remote/backups/{_pending_uuid}", headers=NODE_AUTH,
                   json={"successful": True, "checksum": "abc123", "checksum_type": "sha1", "size": 4096})
check("Backup-Status successful -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    b = Backup.query.filter_by(uuid=_pending_uuid).first()
    check("Backup: is_successful = true", b.is_successful is True)
    check("Backup: checksum = sha1:abc123", b.checksum == "sha1:abc123", str(b.checksum))
    check("Backup: bytes = 4096", b.bytes == 4096)
    check("Backup: completed_at gesetzt", b.completed_at is not None)
    check("Backup: Lock bleibt bei Erfolg", b.is_locked is True)

with app.app_context():
    failing = Backup(instance_id=_inst_id, name="failing", is_successful=False, is_locked=True)
    db.session.add(failing)
    db.session.commit()
    _failing_uuid = failing.uuid
resp = client.post(f"/api/remote/backups/{_failing_uuid}", headers=NODE_AUTH, json={"successful": False})
check("Backup-Status failed -> 204", resp.status_code == 204)
with app.app_context():
    b = Backup.query.filter_by(uuid=_failing_uuid).first()
    check("Backup failed: is_successful false, Lock entfernt, bytes 0",
          b.is_successful is False and b.is_locked is False and b.bytes == 0)

# Restore
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    i.status = "restoring"
    db.session.commit()
resp = client.post(f"/api/remote/backups/{_pending_uuid}/restore", headers=NODE_AUTH, json={"successful": True})
check("Restore-Callback -> 204", resp.status_code == 204, str(resp.status_code))
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Restore-Callback: Status restoring -> ready", i.status is None, str(i.status))
    i.status = "restoring"
    db.session.commit()
resp = client.post(f"/api/remote/backups/{_pending_uuid}/restore", headers=NODE_AUTH, json={"successful": False})
with app.app_context():
    i = db.session.get(Instance, _inst_id)
    check("Restore-Callback failed: Status trotzdem ready", i.status is None, str(i.status))

# Backup-Service: asynchrones Verhalten (Runner ohne completed)
with app.app_context():
    from app.domain.backups import service as backup_service
    from app.domain.instances.service import get_runner, set_runner
    from app.infrastructure.runner.protocol import RunnerResponse

    class AsyncRunner(StubRunnerAdapter):
        def create_backup(self, agent, instance, backup):
            return RunnerResponse(success=True, message="202", data={"completed": False})

        def restore_backup(self, agent, instance, backup):
            return RunnerResponse(success=True, message="202")

    previous = get_runner()
    set_runner(AsyncRunner())
    i = db.session.get(Instance, _inst_id)
    b = backup_service.create_backup(i, "async-backup")
    check("Service: Backup bleibt pending bis Remote-Callback", b.is_successful is False and b.completed_at is None)
    b.is_successful = True
    db.session.commit()
    backup_service.restore_backup(i, b)
    check("Service: Restore haelt Instance auf 'restoring'", i.status == "restoring", str(i.status))
    i.status = None
    db.session.commit()
    set_runner(previous)

    # Stub bleibt synchron
    b2 = backup_service.create_backup(i, "stub-backup")
    check("Service: Stub-Backup sofort erfolgreich", b2.is_successful is True and b2.completed_at is not None)
    backup_service.restore_backup(i, b2)
    check("Service: Stub-Restore sofort ready", i.status is None)


# ================================================================
# g) Admin-API
# ================================================================

print("\n=== g) Admin-API ===")

resp = client.post("/api/admin/agents", json={"name": "m33-new", "fqdn": "new.m33.test",
                                              "scheme": "http", "behind_proxy": True,
                                              "daemon_sftp": 2222, "daemon_base": "/srv/wings"})
check("Agent anlegen -> 201", resp.status_code == 201, str(resp.get_json()))
new_agent = resp.get_json()
check("Agent anlegen: daemon_token_id gesetzt", bool(new_agent.get("daemon_token_id")))
check("Agent anlegen: has_daemon_credentials", new_agent.get("has_daemon_credentials") is True)
check("Agent anlegen: daemon_token NICHT in Antwort", "daemon_token" not in new_agent)
check("Agent anlegen: uuid gesetzt", bool(new_agent.get("uuid")))
check("Agent anlegen: Verbindungsfelder uebernommen",
      new_agent["scheme"] == "http" and new_agent["behind_proxy"] is True
      and new_agent["daemon_sftp"] == 2222 and new_agent["daemon_base"] == "/srv/wings")
_new_agent_id = new_agent["id"]

resp = client.post("/api/admin/agents", json={"name": "bad", "fqdn": "bad.m33.test", "scheme": "ftp"})
check("Agent anlegen: ungueltiges scheme -> 400", resp.status_code == 400)
resp = client.post("/api/admin/agents", json={"name": "bad", "fqdn": "bad2.m33.test", "daemon_sftp": 70000})
check("Agent anlegen: Port > 65535 -> 400", resp.status_code == 400)
resp = client.post("/api/admin/agents", json={"name": "bad", "fqdn": "bad3.m33.test", "daemon_base": "relativ"})
check("Agent anlegen: relativer daemon_base -> 400", resp.status_code == 400)

# config.yml: Schutz
resp = client.get(f"/api/admin/agents/{_new_agent_id}/configuration")
check("config.yml ohne Auth -> 401", resp.status_code == 401, str(resp.status_code))
resp = client.get(f"/api/admin/agents/{_new_agent_id}/configuration", headers={"X-User-Id": str(_owner_id)})
check("config.yml als Nicht-Admin -> 403", resp.status_code == 403, str(resp.status_code))
resp = client.get("/api/admin/agents/999999/configuration", headers=admin_headers())
check("config.yml unbekannter Agent -> 404", resp.status_code == 404)

resp = client.get(f"/api/admin/agents/{_new_agent_id}/configuration", headers=admin_headers())
check("config.yml als Admin -> 200", resp.status_code == 200, str(resp.status_code))
cfg_body = resp.get_json()
cfg = cfg_body["config"]
check("config: token_id passt", cfg["token_id"] == new_agent["daemon_token_id"])
check("config: token 64 Zeichen", len(cfg["token"]) == 64)
check("config: uuid passt", cfg["uuid"] == new_agent["uuid"])
check("config: remote = BASE_URL", cfg["remote"] == "https://panel.m33.test", str(cfg["remote"]))
check("config: api.port = daemon_listen", cfg["api"]["port"] == 8080)
check("config: ssl.enabled false (http + behind_proxy)", cfg["api"]["ssl"]["enabled"] is False)
check("config: ssl.cert enthaelt fqdn", "new.m33.test" in cfg["api"]["ssl"]["cert"])
check("config: system.sftp.bind_port = 2222", cfg["system"]["sftp"]["bind_port"] == 2222)
check("config: system.data = /srv/wings", cfg["system"]["data"] == "/srv/wings")
check("config: allowed_mounts leer", cfg["allowed_mounts"] == [])

import yaml as _yaml
parsed = _yaml.safe_load(cfg_body["yaml"])
check("yaml: parsebar und identisch mit config", parsed == cfg)
check("yaml: beginnt mit debug: false", cfg_body["yaml"].startswith("debug: false"))

# ssl.enabled true bei https ohne Proxy
resp = client.get(f"/api/admin/agents/{_agent_id}/configuration", headers=admin_headers())
check("config: ssl.enabled true (https, kein Proxy)", resp.get_json()["config"]["api"]["ssl"]["enabled"] is True)

# Mit dem Token aus der config.yml an der Remote-API anmelden
resp = client.get("/api/remote/servers", headers={"Authorization": f"Bearer {cfg['token_id']}.{cfg['token']}"})
check("Token aus config.yml authentifiziert an /api/remote", resp.status_code == 200 and resp.get_json()["meta"]["total"] == 0)

# Rotation
resp = client.post(f"/api/admin/agents/{_new_agent_id}/rotate-credentials")
check("Rotation ohne Auth -> 401", resp.status_code == 401)
resp = client.post(f"/api/admin/agents/{_new_agent_id}/rotate-credentials", headers=admin_headers())
check("Rotation als Admin -> 200", resp.status_code == 200, str(resp.status_code))
rotated = resp.get_json()["agent"]
check("Rotation: neue token_id", rotated["daemon_token_id"] != cfg["token_id"])
resp = client.get("/api/remote/servers", headers={"Authorization": f"Bearer {cfg['token_id']}.{cfg['token']}"})
check("Alter Token nach Rotation -> 403", resp.status_code == 403, str(resp.status_code))
resp = client.get(f"/api/admin/agents/{_new_agent_id}/configuration", headers=admin_headers())
new_cfg = resp.get_json()["config"]
resp = client.get("/api/remote/servers", headers={"Authorization": f"Bearer {new_cfg['token_id']}.{new_cfg['token']}"})
check("Neuer Token nach Rotation -> 200", resp.status_code == 200)
with app.app_context():
    from app.domain.activity.models import ActivityLog
    check("Rotation loggt agent:credentials_rotated",
          ActivityLog.query.filter_by(event="agent:credentials_rotated", subject_id=_new_agent_id).count() == 1)

# Agent ohne Credentials (Alt-Daten) bekommt beim config-Abruf welche
with app.app_context():
    legacy = Agent(name="m33-legacy", fqdn="legacy.m33.test")
    legacy.uuid = None
    db.session.add(legacy)
    db.session.commit()
    _legacy_id = legacy.id
resp = client.get(f"/api/admin/agents/{_legacy_id}/configuration", headers=admin_headers())
lc = resp.get_json()["config"]
check("Legacy-Agent: Credentials + uuid beim config-Abruf erzeugt",
      resp.status_code == 200 and lc["token_id"] and lc["token"] and lc["uuid"])

# PATCH
resp = client.patch(f"/api/admin/agents/{_new_agent_id}", json={"daemon_sftp": 2023, "behind_proxy": False,
                                                                "scheme": "https", "upload_size": 512, "name": "m33-renamed"})
check("PATCH Agent -> 200", resp.status_code == 200, str(resp.get_json()))
pa = resp.get_json()
check("PATCH Agent: Felder uebernommen",
      pa["daemon_sftp"] == 2023 and pa["behind_proxy"] is False and pa["scheme"] == "https"
      and pa["upload_size"] == 512 and pa["name"] == "m33-renamed")
resp = client.patch(f"/api/admin/agents/{_new_agent_id}", json={"fqdn": "node.m33.test"})
check("PATCH Agent: fqdn-Kollision -> 409", resp.status_code == 409)
resp = client.patch(f"/api/admin/agents/{_new_agent_id}", json={"upload_size": 0})
check("PATCH Agent: upload_size 0 -> 400", resp.status_code == 400)
resp = client.patch("/api/admin/agents/999999", json={"name": "x"})
check("PATCH Agent unbekannt -> 404", resp.status_code == 404)
resp = client.patch(f"/api/admin/agents/{_new_agent_id}", json={"is_active": False})
check("PATCH Agent: deaktivieren", resp.get_json()["is_active"] is False)
resp = client.get("/api/remote/servers", headers={"Authorization": f"Bearer {new_cfg['token_id']}.{new_cfg['token']}"})
check("Deaktivierter Agent per PATCH -> Remote 403", resp.status_code == 403)

# Blueprints
resp = client.post("/api/admin/blueprints", json={
    "name": "m33-bp-api", "docker_image": "img", "config_stop": "^SIGINT",
    "config_startup": {"done": ["Ready"], "strip_ansi": True},
    "config_files": {"cfg.yml": {"parser": "yaml", "find": {"port": "{{server.build.default.port}}"}}},
    "file_denylist": ["*.jar", "secret.txt"],
    "install_container": "ghcr.io/pterodactyl/installers:alpine", "install_entrypoint": "ash",
})
check("Blueprint anlegen mit Wings-Feldern -> 201", resp.status_code == 201, str(resp.get_json()))
bp_body = resp.get_json()
check("Blueprint: Wings-Felder in to_dict",
      bp_body["config_stop"] == "^SIGINT" and bp_body["config_startup"]["done"] == ["Ready"]
      and bp_body["file_denylist"] == ["*.jar", "secret.txt"]
      and bp_body["install_container"] == "ghcr.io/pterodactyl/installers:alpine"
      and bp_body["install_entrypoint"] == "ash" and "cfg.yml" in bp_body["config_files"])
_bp_api_id = bp_body["id"]

resp = client.patch(f"/api/admin/blueprints/{_bp_api_id}", json={"config_stop": "end", "file_denylist": []})
check("Blueprint PATCH Wings-Felder -> 200", resp.status_code == 200
      and resp.get_json()["config_stop"] == "end" and resp.get_json()["file_denylist"] == [])

for bad in (
    {"config_startup": "Ready"},
    {"config_startup": {"done": [1, 2]}},
    {"config_stop": "x" * 65},
    {"config_files": ["liste"]},
    {"file_denylist": "string"},
    {"install_container": 5},
):
    resp = client.patch(f"/api/admin/blueprints/{_bp_api_id}", json=bad)
    check(f"Blueprint PATCH ungueltig {list(bad.keys())[0]} -> 400", resp.status_code == 400, str(resp.status_code))

resp = client.get("/api/admin/blueprints")
check("Blueprint-Liste enthaelt Wings-Felder", all("config_stop" in b for b in resp.get_json()))


# ================================================================
# h) Regression
# ================================================================

print("\n=== h) Regression ===")

resp = client.get("/api/agent/health")
check("Alter Agent-Endpunkt /api/agent/health weiterhin ok", resp.status_code == 200)

resp = client.post(f"/api/agent/instances/{_inst_uuid}/container/status", json={"state": "running"})
check("Alter Container-Status-Endpunkt weiterhin ok", resp.status_code == 200)

resp = client.post("/api/agent/sftp-auth", json={"username": "m33-owner", "instance_uuid": _inst_uuid, "public_key": KEY_OWNER})
check("Alter /api/agent/sftp-auth weiterhin ok", resp.status_code == 200 and resp.get_json()["allowed"] is True)

resp = client.get("/api/admin/agents")
check("GET /api/admin/agents ohne daemon_token", all("daemon_token" not in a for a in resp.get_json()))

resp = client.get("/health")
check("/health ok", resp.status_code == 200)

with app.app_context():
    from app.infrastructure.tokens.service import create_websocket_token
    import jwt as _jwt
    a = db.session.get(Agent, _agent_id)
    token = create_websocket_token(_inst_uuid, _owner_id, agent=a)
    decoded = _jwt.decode(token, a.daemon_token, algorithms=["HS256"], audience=a.get_connection_url())
    check("Websocket-Token mit daemon_token signiert", decoded["server_uuid"] == _inst_uuid)
    check("Websocket-Token enthaelt user_uuid", decoded.get("user_uuid") == str(_owner_id))
    check("Websocket-Token iss = BASE_URL", decoded.get("iss") == "https://panel.m33.test", str(decoded.get("iss")))


# ================================================================
# Ergebnis
# ================================================================

print(f"\n{'=' * 60}")
print(f"M33 Tests: {passed} bestanden, {failed} fehlgeschlagen")
print(f"{'=' * 60}")
sys.exit(1 if failed else 0)
