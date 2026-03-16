"""Auth-Service: Authentifizierung, Token-Verwaltung, Benutzerkontext.

Unterstuetzt:
- JWT-basierte Authentifizierung (Login)
- API-Key-basierte Authentifizierung (Bearer astra_xxx.yyy)
- X-User-Id Header als Dev/Test-Fallback
"""

import logging
from datetime import timedelta

from flask import request, current_app, jsonify
from flask_jwt_extended import (
    create_access_token,
    decode_token,
)

from app.extensions import db
from app.domain.users.models import User

logger = logging.getLogger(__name__)


def authenticate_user(login: str, password: str) -> User | None:
    """Authentifiziert einen Benutzer ueber Username/Email + Passwort."""
    user = User.query.filter(
        (User.username == login) | (User.email == login)
    ).first()

    if not user:
        return None

    if not user.check_password(password):
        return None

    return user


def issue_access_token(user: User, expires_hours: int = 24) -> str:
    """Erstellt ein JWT Access-Token fuer den Benutzer."""
    additional_claims = {
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
    }

    token = create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=expires_hours),
    )
    return token


def get_current_user() -> User | None:
    """Ermittelt den aktuellen Benutzer aus dem Request-Kontext.

    Strategie:
    1. Bearer-Token pruefen:
       a) JWT-Token decodieren
       b) API-Key validieren (astra_xxx.yyy Format)
    2. Falls Dev/Test: X-User-Id Header als Fallback
    3. Sonst: None
    """
    # 1. Bearer-Token aus Authorization-Header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        token = auth_header[7:]

        # 1a. API-Key erkennen (beginnt mit "astra_")
        if token.startswith("astra_") and "." in token:
            return _resolve_api_key_user(token)

        # 1b. JWT-Token decodieren
        try:
            decoded = decode_token(token)
            identity = decoded.get("sub")
            if identity:
                user = db.session.get(User, int(identity))
                if user:
                    return user
        except Exception as e:
            logger.debug("JWT-Decode fehlgeschlagen: %s", str(e))
            return None

    # 2. Fallback: X-User-Id Header (nur in Testing/Dev)
    if _is_dev_or_testing():
        user_id_header = request.headers.get("X-User-Id")
        if user_id_header and user_id_header.isdigit():
            user = db.session.get(User, int(user_id_header))
            if user:
                return user

    return None


def _resolve_api_key_user(raw_token: str) -> User | None:
    """Validiert einen API Key und gibt den zugehoerigen User zurueck."""
    try:
        from app.domain.auth.apikey_service import validate_api_key
        api_key = validate_api_key(raw_token)
        if api_key:
            return db.session.get(User, api_key.user_id)
    except Exception as e:
        logger.debug("API-Key-Validierung fehlgeschlagen: %s", str(e))
    return None


def require_auth():
    """Erzwingt Authentifizierung. Gibt (user, error_response) zurueck."""
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Authentifizierung erforderlich"}), 401)
    return user, None


def require_admin():
    """Erzwingt Admin-Authentifizierung."""
    user, err = require_auth()
    if err:
        return None, err
    if not user.is_admin:
        return None, (jsonify({"error": "Admin-Berechtigung erforderlich"}), 403)
    return user, None


def _is_dev_or_testing() -> bool:
    """Prueft ob die App im Testing- oder Development-Modus laeuft."""
    return (
        current_app.config.get("TESTING", False)
        or current_app.config.get("DEBUG", False)
    )
