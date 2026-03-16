"""Token-Service fuer Runtime-/Websocket-Zugriff.

Erzeugt Wings-kompatible JWT-Tokens fuer Websocket-/Console-Verbindungen.
Das Token wird mit dem daemon_token des Agents signiert (HMAC SHA256),
damit Wings es direkt verifizieren kann.
"""

import uuid as _uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app

from app.domain.agents.models import Agent


def create_websocket_token(
    instance_uuid: str,
    user_id: int,
    agent: Agent | None = None,
    permissions: list[str] | None = None,
    expires_minutes: int = 10,
) -> str:
    """
    Erzeugt ein Wings-kompatibles JWT-Token fuer Websocket-/Console-Zugriff.

    Wenn ein Agent mit daemon_token angegeben wird, wird das Token
    mit dem daemon_token signiert (Wings-kompatibel).
    Andernfalls wird der Panel-JWT-Secret verwendet (Stub/Fallback).

    Wings-Claims:
    - iss: Panel-URL
    - aud: Agent Connection Address
    - jti: Hash von user_id + instance_uuid
    - server_uuid: Instance UUID
    - permissions: Liste erlaubter Aktionen
    - user_id: Benutzer-ID
    - unique_id: Zufalls-String
    - iat, nbf, exp: Zeitstempel
    """

    if permissions is None:
        permissions = [
            "control.console",
            "control.start",
            "control.stop",
            "control.restart",
            "websocket.connect",
            "send_command",
        ]

    now = datetime.now(timezone.utc)

    # JTI: Hash von user_id + instance_uuid (Wings-kompatibel)
    jti = hashlib.sha256(f"{user_id}{instance_uuid}".encode()).hexdigest()

    payload = {
        "server_uuid": instance_uuid,
        "permissions": permissions,
        "user_id": user_id,
        "unique_id": secrets.token_hex(16),
        "jti": jti,
        "iat": now,
        "nbf": now - timedelta(minutes=5),
        "exp": now + timedelta(minutes=expires_minutes),
    }

    # Issuer und Audience hinzufuegen wenn Agent vorhanden
    if agent:
        panel_url = current_app.config.get("PANEL_URL", "http://localhost:5000")
        payload["iss"] = panel_url
        payload["aud"] = agent.get_connection_url()

    # Signatur: daemon_token des Agents oder Panel-JWT-Secret
    if agent and agent.daemon_token:
        secret = agent.daemon_token
    else:
        secret = current_app.config.get("JWT_SECRET_KEY", "dev-jwt-secret-key")

    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def build_socket_url(agent: Agent | str, instance_uuid: str) -> str:
    """
    Baut die Websocket-URL fuer eine Instance.

    Wings-Format: wss://{fqdn}:{port}/api/servers/{uuid}/ws

    Akzeptiert entweder ein Agent-Objekt oder einen FQDN-String (Fallback).
    """
    if isinstance(agent, Agent):
        scheme = agent.scheme or "https"
        ws_scheme = "wss" if scheme == "https" else "ws"
        port = agent.daemon_connect or 8080
        fqdn = agent.fqdn
        return f"{ws_scheme}://{fqdn}:{port}/api/servers/{instance_uuid}/ws"
    else:
        # Fallback: FQDN-String (Legacy-Kompatibilitaet)
        return f"wss://{agent}/api/servers/{instance_uuid}/ws"
