"""Client-API-Routen – Zugriff fuer Benutzer auf eigene/shared Instances."""

from flask import Blueprint, jsonify, request
from app.extensions import db
from app.domain.instances.models import Instance
from app.domain.agents.models import Agent
from app.domain.instances.service import (
    send_power_action,
    get_runner,
    reinstall_instance,
    sync_instance,
    update_instance_config,
    InstanceActionError,
)
from app.domain.collaborators.checker import (
    can_access_instance,
    get_user_instance,
    get_instance_role,
)
from app.domain.collaborators.permissions import POWER_SIGNAL_PERMISSIONS, ALL_PERMISSIONS
from app.infrastructure.tokens.service import create_websocket_token, build_socket_url
from app.domain.auth.service import get_current_user

client_bp = Blueprint("client", __name__)


def _require_auth():
    """Gibt user_id oder (error_response, status_code).

    Nutzt den zentralen Auth-Service (JWT + X-User-Id Fallback in Dev/Test).
    Dev/Test-Fallback: X-User-Id wird als raw user_id akzeptiert (auch ohne DB-Lookup),
    damit bestehende Tests mit fiktiven User-IDs weiter funktionieren.
    """
    user = get_current_user()
    if user:
        return user.id, None

    # Dev/Test-Fallback: X-User-Id als raw Integer (Legacy-Kompatibilitaet)
    from flask import current_app
    if current_app.config.get("TESTING") or current_app.config.get("DEBUG"):
        user_id_header = request.headers.get("X-User-Id")
        if user_id_header and user_id_header.isdigit():
            return int(user_id_header), None

    return None, (jsonify({"error": "Authentifizierung erforderlich"}), 401)


def _require_instance(uuid: str, user_id: int, permission: str | None = None):
    """Holt Instance mit Zugriffsprüfung. Gibt (instance, error_response) zurück."""
    instance = get_user_instance(uuid, user_id)
    if not instance:
        return None, (jsonify({"error": "Instance nicht gefunden"}), 404)

    if permission and not can_access_instance(user_id, instance, permission):
        return None, (jsonify({"error": f"Fehlende Berechtigung: {permission}"}), 403)

    return instance, None


def _require_owner(uuid: str, user_id: int):
    """Holt Instance und prüft Owner-Status."""
    instance = Instance.query.filter_by(uuid=uuid, owner_id=user_id).first()
    if not instance:
        return None, (jsonify({"error": "Instance nicht gefunden"}), 404)
    return instance, None


def _require_not_suspended(instance: Instance):
    """Gibt (None, None) zurueck wenn ok, oder (None, error_response) wenn suspendiert.

    Zentrale Sperrpruefung fuer alle operativen Client-Aktionen (M29).
    Admin-Lesezugriffe sind nicht betroffen.
    """
    from app.domain.instances.service import is_instance_suspended
    if is_instance_suspended(instance):
        msg = "Instance ist suspendiert"
        if instance.suspended_reason:
            msg += f": {instance.suspended_reason}"
        return None, (jsonify({"error": msg}), 409)
    return None, None


def _get_agent(instance: Instance) -> Agent | None:
    return db.session.get(Agent, instance.agent_id)


# ── Health ──────────────────────────────────────────────

@client_bp.route("/health")
def health():
    return jsonify({"status": "ok", "scope": "client"})


# ── Instances ───────────────────────────────────────────

@client_bp.route("/instances", methods=["GET"])
def list_my_instances():
    user_id, err = _require_auth()
    if err:
        return err

    # Owner-Instances
    owned = Instance.query.filter_by(owner_id=user_id).all()

    # Collaborator-Instances
    from app.domain.collaborators.models import Collaborator
    collabs = Collaborator.query.filter_by(user_id=user_id).all()
    collab_ids = [c.instance_id for c in collabs]
    shared = Instance.query.filter(Instance.id.in_(collab_ids)).all() if collab_ids else []

    all_instances = owned + shared
    all_instances.sort(key=lambda i: i.created_at or "", reverse=True)

    result = []
    for inst in all_instances:
        d = inst.to_dict()
        d["role"] = get_instance_role(user_id, inst)
        result.append(d)

    return jsonify(result)


@client_bp.route("/instances/<uuid>", methods=["GET"])
def get_my_instance(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err

    instance, err = _require_instance(uuid, user_id)
    if err:
        return err

    d = instance.to_dict()
    d["role"] = get_instance_role(user_id, instance)
    return jsonify(d)


# ── Power ───────────────────────────────────────────────

@client_bp.route("/instances/<uuid>/power", methods=["POST"])
def power_action(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json()
    if not data or "signal" not in data:
        return jsonify({"error": "Field 'signal' is required"}), 400

    signal = data["signal"]
    valid_signals = ("start", "stop", "restart", "kill")
    if signal not in valid_signals:
        return jsonify({"error": f"Invalid signal. Erlaubt: {', '.join(valid_signals)}"}), 400

    perm = POWER_SIGNAL_PERMISSIONS.get(signal)
    instance, err = _require_instance(uuid, user_id, perm)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    try:
        result = send_power_action(instance, signal)
        return jsonify(result)
    except InstanceActionError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Reinstall (M16) ────────────────────────────────────

@client_bp.route("/instances/<uuid>/reinstall", methods=["POST"])
def reinstall_endpoint(uuid: str):
    """Loest eine Reinstallation der Instance aus."""
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    try:
        result = reinstall_instance(instance)
        return jsonify({
            "uuid": result.uuid,
            "status": result.status,
            "message": "Reinstallation gestartet",
        })
    except InstanceActionError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Config-Update (M16) ────────────────────────────────

@client_bp.route("/instances/<uuid>/build", methods=["PATCH"])
def update_build_config(uuid: str):
    """Aktualisiert Build-/Startup-Konfiguration und loest ggf. Sync aus.

    Akzeptierte Felder: memory, swap, disk, io, cpu, image, startup_command
    """
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # Nur erlaubte Felder durchlassen
    allowed = {"memory", "swap", "disk", "io", "cpu", "image", "startup_command", "name", "description"}
    changes = {k: v for k, v in data.items() if k in allowed}

    if not changes:
        return jsonify({"error": "Keine gueltigen Felder angegeben"}), 400

    result = update_instance_config(instance, **changes)

    return jsonify({
        "instance": result["instance"].to_dict(),
        "synced": result["synced"],
        "sync_message": result["sync_message"],
        "changed_fields": result["changed_fields"],
    })



@client_bp.route("/instances/<uuid>/variables", methods=["PATCH"])
def update_variable_values(uuid: str):
    """Aktualisiert die Blueprint-Variablen-Werte einer Instance.

    Body: {"SERVER_PORT": "25565", "MAX_PLAYERS": "20", ...}
    Nur Variablen, die im Blueprint als user_editable=true markiert sind, dürfen
    von Nicht-Ownern gesetzt werden.
    """
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    # Blueprint-Variablen laden um user_editable zu prüfen
    from app.domain.blueprints.models import Blueprint
    blueprint = db.session.get(Blueprint, instance.blueprint_id)
    bp_vars = {v["env_var"]: v for v in (blueprint.variables or []) if "env_var" in v} if blueprint else {}

    role = get_instance_role(user_id, instance)
    is_owner = role == "owner"

    # Nur gültige (im Blueprint definierte) Variablen erlauben
    updated = dict(instance.variable_values or {})
    rejected = []

    for key, value in data.items():
        if key not in bp_vars:
            rejected.append(key)
            continue
        var_def = bp_vars[key]
        if not is_owner and not var_def.get("user_editable", True):
            rejected.append(key)
            continue
        updated[key] = str(value) if value is not None else ""

    instance.variable_values = updated
    db.session.commit()

    return jsonify({
        "variable_values": instance.variable_values,
        "rejected": rejected,
    })


# ── Sync (M16) ─────────────────────────────────────────

@client_bp.route("/instances/<uuid>/sync", methods=["POST"])
def sync_endpoint(uuid: str):
    """Loest manuelle Konfigurationssynchronisierung aus."""
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    try:
        result = sync_instance(instance)
        status_code = 200 if result.get("success") else 502
        return jsonify(result), status_code
    except InstanceActionError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Websocket ───────────────────────────────────────────

@client_bp.route("/instances/<uuid>/websocket", methods=["GET"])
def websocket_credentials(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err

    instance, err = _require_instance(uuid, user_id, "control.console")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    token = create_websocket_token(
        instance_uuid=instance.uuid,
        user_id=user_id,
        agent=agent,
    )
    socket_url = build_socket_url(agent, instance.uuid)
    return jsonify({"token": token, "socket": socket_url})


# ── Resources ──────────────────────────────────────────

@client_bp.route("/instances/<uuid>/resources", methods=["GET"])
def instance_resources(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err

    instance, err = _require_instance(uuid, user_id)
    if err:
        return err

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        stats = runner.get_instance_resources(agent, instance)
        return jsonify(stats.to_dict())
    except Exception as e:
        return jsonify({"error": f"Resources nicht abrufbar: {str(e)}"}), 502


# ── Files ───────────────────────────────────────────────

@client_bp.route("/instances/<uuid>/files", methods=["GET"])
def list_files(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.read")
    if err:
        return err

    directory = request.args.get("directory", "/")
    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        return jsonify(runner.list_files(agent, instance, directory).to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/content", methods=["GET"])
def read_file_content(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.read")
    if err:
        return err

    path = request.args.get("path")
    if not path:
        return jsonify({"error": "Query parameter 'path' is required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        return jsonify(runner.read_file(agent, instance, path).to_dict())
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/write", methods=["POST"])
def write_file_content(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "path" not in data or "content" not in data:
        return jsonify({"error": "Fields 'path' and 'content' are required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.write_file(agent, instance, data["path"], data["content"])
        return jsonify({"success": result.success, "message": result.message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/delete", methods=["POST"])
def delete_file_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.delete")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"error": "Field 'path' is required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.delete_file(agent, instance, data["path"])
        return jsonify({"success": result.success, "message": result.message}), 200 if result.success else 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/create-directory", methods=["POST"])
def create_directory_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "path" not in data:
        return jsonify({"error": "Field 'path' is required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.create_directory(agent, instance, data["path"])
        return jsonify({"success": result.success, "message": result.message}), 201 if result.success else 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/rename", methods=["POST"])
def rename_file_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "source" not in data or "target" not in data:
        return jsonify({"error": "Fields 'source' and 'target' are required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.rename_file(agent, instance, data["source"], data["target"])
        return jsonify({"success": result.success, "message": result.message}), 200 if result.success else 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/compress", methods=["POST"])
def compress_files_endpoint(uuid: str):
    """Komprimiert mehrere Dateien/Verzeichnisse zu einem Archiv.

    Body: {"files": ["/path/to/file1", "/path/to/dir"], "destination": "/archive.tar.gz"}
    """
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "files" not in data or "destination" not in data:
        return jsonify({"error": "Fields 'files' and 'destination' are required"}), 400

    files = data["files"]
    if not isinstance(files, list) or len(files) == 0:
        return jsonify({"error": "Field 'files' must be a non-empty list"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.compress_files(agent, instance, files, data["destination"])
        return jsonify({"success": result.success, "message": result.message, "data": result.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@client_bp.route("/instances/<uuid>/files/decompress", methods=["POST"])
def decompress_file_endpoint(uuid: str):
    """Entpackt ein Archiv in ein Zielverzeichnis.

    Body: {"file": "/archive.tar.gz", "destination": "/target-dir"}
    """
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "file.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "file" not in data or "destination" not in data:
        return jsonify({"error": "Fields 'file' and 'destination' are required"}), 400

    agent = _get_agent(instance)
    if not agent:
        return jsonify({"error": "Agent nicht gefunden"}), 500

    try:
        runner = get_runner()
        result = runner.decompress_file(agent, instance, data["file"], data["destination"])
        return jsonify({"success": result.success, "message": result.message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Backups ─────────────────────────────────────────────

@client_bp.route("/instances/<uuid>/backups", methods=["GET"])
def list_backups_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "backup.read")
    if err:
        return err

    from app.domain.backups.service import list_backups
    return jsonify([b.to_dict() for b in list_backups(instance)])


@client_bp.route("/instances/<uuid>/backups", methods=["POST"])
def create_backup_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "backup.create")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Field 'name' is required"}), 400

    from app.domain.backups.service import create_backup, BackupError
    try:
        backup = create_backup(instance=instance, name=data["name"], ignored_files=data.get("ignored_files"))
        return jsonify(backup.to_dict()), 201
    except BackupError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/backups/<backup_uuid>/restore", methods=["POST"])
def restore_backup_endpoint(uuid: str, backup_uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "backup.restore")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    from app.domain.backups.models import Backup
    backup = Backup.query.filter_by(uuid=backup_uuid, instance_id=instance.id).first()
    if not backup:
        return jsonify({"error": "Backup nicht gefunden"}), 404

    from app.domain.backups.service import restore_backup, BackupError
    try:
        instance = restore_backup(instance, backup)
        return jsonify({"message": f"Backup '{backup.name}' wiederhergestellt", "instance_status": instance.status})
    except BackupError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/backups/<backup_uuid>", methods=["DELETE"])
def delete_backup_endpoint(uuid: str, backup_uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "backup.delete")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    from app.domain.backups.models import Backup
    backup = Backup.query.filter_by(uuid=backup_uuid, instance_id=instance.id).first()
    if not backup:
        return jsonify({"error": "Backup nicht gefunden"}), 404

    from app.domain.backups.service import delete_backup, BackupError
    try:
        delete_backup(instance, backup)
        return jsonify({"message": f"Backup '{backup.name}' gelöscht"})
    except BackupError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Databases (M18) ────────────────────────────────────

@client_bp.route("/instances/<uuid>/databases", methods=["GET"])
def list_databases_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "database.read")
    if err:
        return err

    from app.domain.databases.service import list_databases
    dbs = list_databases(instance)
    return jsonify([d.to_dict(include_password=True) for d in dbs])


@client_bp.route("/instances/<uuid>/databases", methods=["POST"])
def create_database_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "database.create")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    data = request.get_json()
    if not data or "provider_id" not in data:
        return jsonify({"error": "Field 'provider_id' is required"}), 400

    from app.domain.databases.service import create_database, DatabaseError
    try:
        database = create_database(
            instance=instance,
            provider_id=data["provider_id"],
            db_name=data.get("db_name"),
            username=data.get("username"),
            password=data.get("password"),
            remote_host=data.get("remote_host", "%"),
            max_connections=data.get("max_connections"),
        )
        return jsonify(database.to_dict(include_password=True)), 201
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/databases/<int:db_id>/rotate-password", methods=["POST"])
def rotate_database_password(uuid: str, db_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "database.update")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    from app.domain.databases.models import Database
    database = Database.query.filter_by(id=db_id, instance_id=instance.id).first()
    if not database:
        return jsonify({"error": "Datenbank nicht gefunden"}), 404

    from app.domain.databases.service import rotate_password, DatabaseError
    try:
        database = rotate_password(instance, database)
        return jsonify(database.to_dict(include_password=True))
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/databases/<int:db_id>", methods=["DELETE"])
def delete_database_endpoint(uuid: str, db_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id, "database.delete")
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    from app.domain.databases.models import Database
    database = Database.query.filter_by(id=db_id, instance_id=instance.id).first()
    if not database:
        return jsonify({"error": "Datenbank nicht gefunden"}), 404

    from app.domain.databases.service import delete_database, DatabaseError
    try:
        delete_database(instance, database)
        return jsonify({"message": "Datenbank geloescht"})
    except DatabaseError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Collaborators ───────────────────────────────────────

@client_bp.route("/instances/<uuid>/collaborators", methods=["GET"])
def list_collaborators(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.collaborators.service import list_collaborators as _list
    return jsonify([c.to_dict() for c in _list(instance)])


@client_bp.route("/instances/<uuid>/collaborators", methods=["POST"])
def add_collaborator(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    data = request.get_json()
    if not data or "user_id" not in data or "permissions" not in data:
        return jsonify({"error": "Fields 'user_id' and 'permissions' are required"}), 400

    from app.domain.collaborators.service import add_collaborator as _add, CollaboratorError
    try:
        collab = _add(instance, data["user_id"], data["permissions"])
        return jsonify(collab.to_dict()), 201
    except CollaboratorError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/collaborators/<int:collab_id>", methods=["PATCH"])
def update_collaborator(uuid: str, collab_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.collaborators.models import Collaborator
    collab = Collaborator.query.filter_by(id=collab_id, instance_id=instance.id).first()
    if not collab:
        return jsonify({"error": "Collaborator nicht gefunden"}), 404

    data = request.get_json()
    if not data or "permissions" not in data:
        return jsonify({"error": "Field 'permissions' is required"}), 400

    from app.domain.collaborators.service import update_collaborator as _update, CollaboratorError
    try:
        collab = _update(collab, data["permissions"])
        return jsonify(collab.to_dict())
    except CollaboratorError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/collaborators/<int:collab_id>", methods=["DELETE"])
def remove_collaborator(uuid: str, collab_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.collaborators.models import Collaborator
    collab = Collaborator.query.filter_by(id=collab_id, instance_id=instance.id).first()
    if not collab:
        return jsonify({"error": "Collaborator nicht gefunden"}), 404

    from app.domain.collaborators.service import remove_collaborator as _remove
    _remove(collab)
    return jsonify({"message": "Collaborator entfernt"})


# ── Routines ────────────────────────────────────────────


@client_bp.route("/instances/<uuid>/routines", methods=["GET"])
def list_routines_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.service import list_routines
    return jsonify([r.to_dict() for r in list_routines(instance)])


@client_bp.route("/instances/<uuid>/routines", methods=["POST"])
def create_routine_endpoint(uuid: str):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Field 'name' is required"}), 400

    from app.domain.routines.service import create_routine
    routine = create_routine(instance, **data)
    return jsonify(routine.to_dict()), 201


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>", methods=["PATCH"])
def update_routine_endpoint(uuid: str, routine_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.models import Routine
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    data = request.get_json() or {}
    from app.domain.routines.service import update_routine
    routine = update_routine(routine, **data)
    return jsonify(routine.to_dict())


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>", methods=["DELETE"])
def delete_routine_endpoint(uuid: str, routine_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.models import Routine
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    from app.domain.routines.service import delete_routine
    delete_routine(routine)
    return jsonify({"message": "Routine gelöscht"})


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>/execute", methods=["POST"])
def execute_routine_endpoint(uuid: str, routine_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err
    _, err = _require_not_suspended(instance)
    if err:
        return err

    from app.domain.routines.models import Routine
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    from app.domain.routines.service import execute_routine, RoutineError
    try:
        result = execute_routine(routine)
        return jsonify(result)
    except RoutineError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Actions ─────────────────────────────────────────────


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>/actions", methods=["POST"])
def add_action_endpoint(uuid: str, routine_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.models import Routine
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    data = request.get_json()
    if not data or "sequence" not in data or "action_type" not in data:
        return jsonify({"error": "Fields 'sequence' and 'action_type' are required"}), 400

    from app.domain.routines.service import add_action, RoutineError
    try:
        action = add_action(
            routine,
            sequence=data["sequence"],
            action_type=data["action_type"],
            payload=data.get("payload"),
            delay_seconds=data.get("delay_seconds", 0),
            continue_on_failure=data.get("continue_on_failure", False),
        )
        return jsonify(action.to_dict()), 201
    except RoutineError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>/actions/<int:action_id>", methods=["PATCH"])
def update_action_endpoint(uuid: str, routine_id: int, action_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.models import Routine, Action
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    action = Action.query.filter_by(id=action_id, routine_id=routine.id).first()
    if not action:
        return jsonify({"error": "Action nicht gefunden"}), 404

    data = request.get_json() or {}
    from app.domain.routines.service import update_action, RoutineError
    try:
        action = update_action(action, **data)
        return jsonify(action.to_dict())
    except RoutineError as e:
        return jsonify({"error": e.message}), e.status_code


@client_bp.route("/instances/<uuid>/routines/<int:routine_id>/actions/<int:action_id>", methods=["DELETE"])
def delete_action_endpoint(uuid: str, routine_id: int, action_id: int):
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_owner(uuid, user_id)
    if err:
        return err

    from app.domain.routines.models import Routine, Action
    routine = Routine.query.filter_by(id=routine_id, instance_id=instance.id).first()
    if not routine:
        return jsonify({"error": "Routine nicht gefunden"}), 404

    action = Action.query.filter_by(id=action_id, routine_id=routine.id).first()
    if not action:
        return jsonify({"error": "Action nicht gefunden"}), 404

    from app.domain.routines.service import delete_action
    delete_action(action)
    return jsonify({"message": "Action gelöscht"})


# ── Activity ────────────────────────────────────────────


@client_bp.route("/instances/<uuid>/activity", methods=["GET"])
def instance_activity(uuid: str):
    """Listet Activity-Logs für eine Instance."""
    user_id, err = _require_auth()
    if err:
        return err
    instance, err = _require_instance(uuid, user_id)
    if err:
        return err

    from app.domain.activity.service import list_for_instance
    limit = request.args.get("limit", 50, type=int)
    logs = list_for_instance(instance.id, limit=limit)
    return jsonify([l.to_dict() for l in logs])


# ── SSH Keys (M28) ──────────────────────────────────────


@client_bp.route("/account/ssh-keys", methods=["GET"])
def list_ssh_keys():
    """Listet alle SSH-Keys des authentifizierten Users."""
    user_id, err = _require_auth()
    if err:
        return err

    from app.domain.ssh_keys.service import list_user_ssh_keys
    keys = list_user_ssh_keys(user_id)
    return jsonify([k.to_dict() for k in keys])


@client_bp.route("/account/ssh-keys", methods=["POST"])
def create_ssh_key():
    """Fuegt einen neuen SSH-Key zum Account hinzu."""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "")
    public_key = data.get("public_key", "")

    from app.domain.ssh_keys.service import create_user_ssh_key, SshKeyError
    try:
        key = create_user_ssh_key(user_id, name, public_key)
    except SshKeyError as e:
        return jsonify({"error": e.message}), e.status_code

    return jsonify(key.to_dict()), 201


@client_bp.route("/account/ssh-keys/<int:key_id>", methods=["PATCH"])
def update_ssh_key(key_id: int):
    """Benennt einen SSH-Key um."""
    user_id, err = _require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    name = data.get("name", "")

    from app.domain.ssh_keys.service import update_user_ssh_key_name, SshKeyError
    try:
        key = update_user_ssh_key_name(user_id, key_id, name)
    except SshKeyError as e:
        return jsonify({"error": e.message}), e.status_code

    return jsonify(key.to_dict())


@client_bp.route("/account/ssh-keys/<int:key_id>", methods=["DELETE"])
def delete_ssh_key(key_id: int):
    """Loescht einen SSH-Key."""
    user_id, err = _require_auth()
    if err:
        return err

    from app.domain.ssh_keys.service import delete_user_ssh_key, SshKeyError
    try:
        delete_user_ssh_key(user_id, key_id)
    except SshKeyError as e:
        return jsonify({"error": e.message}), e.status_code

    return jsonify({"message": "SSH-Key geloescht"})
