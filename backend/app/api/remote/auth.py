"""Node-Token-Authentifizierung fuer die Wings Remote-API (M33).

Wings sendet bei jedem Request an das Panel:
    Authorization: Bearer {daemon_token_id}.{daemon_token}

Entspricht der DaemonAuthenticate-Middleware im Referenz-Panel.
"""

from __future__ import annotations

import hmac
import logging

from flask import g, jsonify, request

from app.extensions import db
from app.domain.agents.models import Agent

logger = logging.getLogger(__name__)


def authenticate_agent_request():
    """before_request-Hook: Prueft den Bearer-Token und setzt g.agent.

    Rueckgabe None = weiter, sonst eine Flask-Response (Fehler).
    """
    header = request.headers.get("Authorization", "")
    if not header:
        return _error(401, "Access to this endpoint must include an Authorization header.",
                      {"WWW-Authenticate": "Bearer"})

    scheme, _, bearer = header.partition(" ")
    if scheme.lower() != "bearer" or not bearer.strip():
        return _error(401, "Access to this endpoint must include an Authorization header.",
                      {"WWW-Authenticate": "Bearer"})

    parts = bearer.strip().split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return _error(400, "The Authorization header provided was not in a valid format.")

    token_id, token = parts
    agent = Agent.query.filter_by(daemon_token_id=token_id).first()
    if not agent or not agent.daemon_token:
        logger.warning("Remote-API: unbekannte token_id '%s' von %s", token_id, request.remote_addr)
        return _error(403, "You are not authorized to access this resource.")

    if not hmac.compare_digest(str(agent.daemon_token), token):
        logger.warning("Remote-API: ungueltiger Token fuer Agent '%s' von %s", agent.name, request.remote_addr)
        return _error(403, "You are not authorized to access this resource.")

    if not agent.is_active:
        return _error(403, "This node is deactivated.")

    g.agent = agent

    # Jeder authentifizierte Request zaehlt als Lebenszeichen des Agents
    try:
        agent.touch()
        db.session.commit()
    except Exception:  # pragma: no cover - best-effort
        db.session.rollback()

    return None


def current_agent() -> Agent:
    return g.agent


def _error(status: int, message: str, headers: dict | None = None):
    resp = jsonify({"error": message})
    resp.status_code = status
    if headers:
        for key, value in headers.items():
            resp.headers[key] = value
    return resp
