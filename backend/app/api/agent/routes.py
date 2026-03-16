"""Agent-API-Routen – Callbacks von Agents."""

from flask import Blueprint, jsonify, request
from app.extensions import db
from app.domain.instances.models import Instance
from app.domain.agents.models import Agent
from app.domain.instances.service import handle_install_callback, update_container_status

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
