"""Auth-API-Routen: Login, Logout, Current-User, API Keys, MFA."""

from flask import Blueprint, jsonify, request
from app.domain.auth.service import (
    authenticate_user,
    issue_access_token,
    require_auth,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/health")
def health():
    return jsonify({"status": "ok", "scope": "auth"})


# ── Login / Logout ──────────────────────────────────────


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authentifiziert einen Benutzer und gibt ein JWT-Token zurueck.

    Wenn MFA aktiv ist, wird ein Zwischenstatus zurueckgegeben.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    login_field = data.get("login") or data.get("username") or data.get("email")
    password = data.get("password")

    if not login_field or not password:
        return jsonify({"error": "Fields 'login' and 'password' are required"}), 400

    user = authenticate_user(login_field, password)

    if not user:
        _log_auth_event("auth:login_failed", None,
                        f"Fehlgeschlagener Login-Versuch fuer '{login_field}'",
                        {"login": login_field})
        return jsonify({"error": "Ungueltige Anmeldedaten"}), 401

    # MFA-Check
    if user.mfa_enabled:
        mfa_code = data.get("mfa_code")
        if not mfa_code:
            return jsonify({
                "requires_mfa": True,
                "message": "MFA-Code erforderlich",
                "user_id": user.id,
            }), 200

        from app.domain.auth.mfa_service import verify_totp
        if not verify_totp(user, mfa_code):
            _log_auth_event("auth:login_failed", user.id,
                            f"MFA-Verifikation fehlgeschlagen fuer {user.username}")
            return jsonify({"error": "Ungueltiger MFA-Code"}), 401

    token = issue_access_token(user)
    _log_auth_event("auth:login_success", user.id,
                    f"Login erfolgreich: {user.username}")

    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout – Server-seitig nur Activity-Log, Token-Invalidierung ist clientseitig."""
    user, err = require_auth()
    if err:
        return err

    _log_auth_event("auth:logout", user.id, f"Logout: {user.username}")
    return jsonify({"message": "Erfolgreich ausgeloggt"})


@auth_bp.route("/me", methods=["GET"])
def current_user():
    """Gibt den aktuell authentifizierten Benutzer zurueck."""
    user, err = require_auth()
    if err:
        return err
    return jsonify(user.to_dict())


# ── API Keys ───────────────────────────────────────────


@auth_bp.route("/api-keys", methods=["GET"])
def list_api_keys():
    """Listet alle API Keys des aktuellen Users."""
    user, err = require_auth()
    if err:
        return err

    from app.domain.auth.apikey_service import list_user_keys
    keys = list_user_keys(user.id)
    return jsonify([k.to_dict() for k in keys])


@auth_bp.route("/api-keys", methods=["POST"])
def create_api_key_endpoint():
    """Erstellt einen neuen API Key. Gibt den Roh-Token genau EINMAL zurueck."""
    user, err = require_auth()
    if err:
        return err

    data = request.get_json() or {}

    from app.domain.auth.apikey_service import create_api_key, ApiKeyError
    try:
        api_key, raw_token = create_api_key(
            user_id=user.id,
            key_type=data.get("key_type", "account"),
            memo=data.get("memo"),
            allowed_ips=data.get("allowed_ips"),
            permissions=data.get("permissions"),
        )
        result = api_key.to_dict()
        result["raw_token"] = raw_token  # Nur EINMAL zurueckgegeben!
        return jsonify(result), 201
    except ApiKeyError as e:
        return jsonify({"error": e.message}), e.status_code


@auth_bp.route("/api-keys/<int:key_id>", methods=["DELETE"])
def delete_api_key_endpoint(key_id: int):
    """Loescht einen API Key."""
    user, err = require_auth()
    if err:
        return err

    from app.domain.auth.apikey_service import delete_api_key, ApiKeyError
    try:
        delete_api_key(key_id, user.id)
        return jsonify({"message": "API Key geloescht"})
    except ApiKeyError as e:
        return jsonify({"error": e.message}), e.status_code


# ── MFA ─────────────────────────────────────────────────


@auth_bp.route("/mfa/setup", methods=["POST"])
def mfa_setup():
    """Initialisiert MFA-Setup und gibt Secret + QR-URI zurueck."""
    user, err = require_auth()
    if err:
        return err

    from app.domain.auth.mfa_service import setup_mfa, MfaError
    try:
        result = setup_mfa(user)
        return jsonify(result)
    except MfaError as e:
        return jsonify({"error": e.message}), e.status_code


@auth_bp.route("/mfa/verify", methods=["POST"])
def mfa_verify():
    """Verifiziert MFA-Code und aktiviert MFA."""
    user, err = require_auth()
    if err:
        return err

    data = request.get_json()
    if not data or "code" not in data:
        return jsonify({"error": "Field 'code' is required"}), 400

    from app.domain.auth.mfa_service import verify_and_enable_mfa, MfaError
    try:
        result = verify_and_enable_mfa(user, data["code"])
        return jsonify(result)
    except MfaError as e:
        return jsonify({"error": e.message}), e.status_code


@auth_bp.route("/mfa/disable", methods=["POST"])
def mfa_disable():
    """Deaktiviert MFA."""
    user, err = require_auth()
    if err:
        return err

    from app.domain.auth.mfa_service import disable_mfa, MfaError
    try:
        result = disable_mfa(user)
        return jsonify(result)
    except MfaError as e:
        return jsonify({"error": e.message}), e.status_code


# ── Hilfsfunktionen ─────────────────────────────────────


def _log_auth_event(event: str, actor_id: int | None, description: str,
                    properties: dict | None = None) -> None:
    """Loggt ein Auth-Event (non-blocking)."""
    try:
        from app.domain.activity.service import log_event
        log_event(event=event, actor_id=actor_id, description=description,
                  properties=properties)
    except Exception:
        pass
