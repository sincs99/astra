"""Agent-API-Routen – Callbacks von Agents."""

from flask import Blueprint, jsonify, request
from app.extensions import db
from app.domain.instances.models import Instance
from app.domain.agents.models import Agent
from app.domain.instances.service import handle_install_callback, update_container_status
from app.domain.ssh_keys.auth_service import (
    authorize_ssh_key_access,
    REASON_OK,
    REASON_MALFORMED,
)

agent_bp = Blueprint("agent", __name__)


def _touch_agent_for_instance(instance: Instance) -> None:
    """Aktualisiert last_seen_at des Agents einer Instance (best-effort)."""
    try:
        agent = db.session.get(Agent, instance.agent_id)
        if agent:
            agent.touch()
            db.session.commit()
    except Exception:
        pass


@agent_bp.route("/health")
def health():
    return jsonify({"status": "ok", "scope": "agent"})


@agent_bp.route("/instances/<uuid>/install", methods=["POST"])
def install_callback(uuid: str):
    """Agent meldet das Ergebnis der Installation.
    Body: { "successful": true/false }
    """
    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": f"Instance mit UUID '{uuid}' nicht gefunden"}), 404

    data = request.get_json()
    if not data or "successful" not in data:
        return jsonify({"error": "Field 'successful' is required"}), 400

    _touch_agent_for_instance(instance)
    instance = handle_install_callback(instance, data["successful"])

    return jsonify({
        "uuid": instance.uuid,
        "status": instance.status,
        "message": "Install-Callback verarbeitet",
    })


@agent_bp.route("/instances/<uuid>/container/status", methods=["POST"])
def container_status(uuid: str):
    """Agent meldet den Container-Status.
    Body: { "state": "running" | "stopped" | "starting" | "stopping" | "offline" }
    """
    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return jsonify({"error": f"Instance mit UUID '{uuid}' nicht gefunden"}), 404

    data = request.get_json()
    if not data or "state" not in data:
        return jsonify({"error": "Field 'state' is required"}), 400

    state = data["state"]
    if not isinstance(state, str) or not state.strip():
        return jsonify({"error": "Field 'state' must be a non-empty string"}), 400

    _touch_agent_for_instance(instance)
    instance = update_container_status(instance, state)

    return jsonify({
        "uuid": instance.uuid,
        "container_state": instance.container_state,
        "status": instance.status,
        "message": "Container-Status verarbeitet",
    })


@agent_bp.route("/sftp-auth", methods=["POST"])
def sftp_auth():
    """Agent fragt an, ob ein SSH-Key-Zugriff auf eine Instance erlaubt ist.

    Request-Body (JSON):
        username      (str, required)  – Astra-Benutzername
        instance_uuid (str, required)  – UUID der Ziel-Instance
        public_key    (str, optional)  – SSH Public Key (bevorzugt)
        fingerprint   (str, optional)  – SHA256-Fingerprint (Fallback wenn kein public_key)

    Mindestens public_key oder fingerprint muss angegeben werden.

    Response 200:
        { "allowed": true,  "username": "...", "instance_uuid": "...", "permissions": [...] }
        { "allowed": false, "reason": "..." }
    Response 400: Malformed request
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip() if data.get("username") else ""
    instance_uuid = data.get("instance_uuid", "").strip() if data.get("instance_uuid") else ""
    public_key = data.get("public_key") or None
    fingerprint = data.get("fingerprint") or None

    if not username or not instance_uuid:
        return jsonify({"error": "Fields 'username' and 'instance_uuid' are required"}), 400

    if not public_key and not fingerprint:
        return jsonify({"error": "Either 'public_key' or 'fingerprint' is required"}), 400

    result = authorize_ssh_key_access(
        instance_uuid=instance_uuid,
        username=username,
        public_key=public_key,
        fingerprint=fingerprint,
    )

    if result.reason == REASON_MALFORMED:
        return jsonify({"error": "Malformed auth request"}), 400

    if result.allowed:
        return jsonify({
            "allowed": True,
            "username": result.username,
            "instance_uuid": result.instance_uuid,
            "permissions": result.permissions,
        })

    return jsonify({
        "allowed": False,
        "reason": result.reason,
    })
