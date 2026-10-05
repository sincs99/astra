"""Auth-API-Routen: Login, Logout, Current-User, API Keys, MFA."""

from flask import Blueprint, current_app, jsonify, request
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

    # M71: zu viele Fehlversuche fuer dieses Konto in der letzten Stunde: gesperrt (auch mit richtigem Passwort)
    blocked, retry_after = _login_failures_blocked(login_field)
    if blocked:
        _log_auth_event("auth:login_blocked", None, f"Login gesperrt (zu viele Fehlversuche) für '{login_field}'",
                        {"login": str(login_field)[:120]})
        return _limited(retry_after)

    user = authenticate_user(login_field, password)

    if not user:
        _record_login_failure(login_field)
        _log_auth_event("auth:login_failed", None,
                        f"Fehlgeschlagener Login-Versuch für '{login_field}'",
                        {"login": login_field})
        return jsonify({"error": "Ungültige Anmeldedaten"}), 401

    # M38: unbestaetigte E-Mail-Adresse
    if current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False) and user.email_verified_at is None:
        return jsonify({
            "error": "E-Mail-Adresse noch nicht bestätigt",
            "code": "email_not_verified",
        }), 403

    # MFA-Check
    recovery_remaining = None  # gesetzt, wenn ein Recovery-Code den Login freigegeben hat
    if user.mfa_enabled:
        # Der zweite Faktor ist ein TOTP-Code oder ein einmaliger Recovery-Code (Feld `mfa_code` oder `recovery_code`)
        mfa_code = data.get("mfa_code") or data.get("recovery_code")
        if not mfa_code:
            return jsonify({
                "requires_mfa": True,
                "message": "MFA-Code erforderlich",
                "user_id": user.id,
            }), 200

        from app.domain.auth.mfa_service import recovery_codes_remaining, verify_mfa_login
        method = verify_mfa_login(user, mfa_code)
        if method is None:
            _record_login_failure(login_field)
            _log_auth_event("auth:login_failed", user.id,
                            f"MFA-Verifikation fehlgeschlagen für {user.username}")
            return jsonify({"error": "Ungültiger MFA-Code"}), 401
        if method == "recovery":
            recovery_remaining = recovery_codes_remaining(user)
            _log_auth_event("auth:mfa_recovery_used", user.id,
                            f"Recovery-Code verwendet: {user.username}", {"remaining": recovery_remaining})
            _notify_recovery_used(user, recovery_remaining)

    token = issue_access_token(user)
    _log_auth_event("auth:login_success", user.id,
                    f"Login erfolgreich: {user.username}")

    body = {
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }
    if recovery_remaining is not None:
        body["recovery_code_used"] = True
        body["recovery_codes_remaining"] = recovery_remaining
    return jsonify(body)


# ── Registrierung / Passwort-Reset ───────────────────────


@auth_bp.route("/captcha", methods=["GET"])
def captcha_config():
    """Oeffentlich: CAPTCHA-Anbieter und Site-Key fuer das Widget (`provider` = none, turnstile oder hcaptcha)."""
    from app.domain.accounts.captcha import public_config
    return jsonify(public_config())


@auth_bp.route("/register", methods=["POST"])
def register():
    """Selbstregistrierung (nur wenn REGISTRATION_ENABLED=true)."""
    from app.domain.accounts.service import AccountError, register_user

    data = request.get_json() or {}
    # M71: Honigtopf-Feld (fuer Menschen unsichtbar): gefuellt = Bot, kein Konto, bewusst nichtssagende Antwort
    if data.get("website"):
        return jsonify({"error": "Ungültige Anfrage", "code": "invalid_request"}), 400
    captcha_error = _check_captcha(data)
    if captcha_error:
        return captcha_error
    try:
        user = register_user(data.get("username"), data.get("email"), data.get("password"), data.get("locale"))
    except AccountError as e:
        return jsonify({"error": e.message}), e.status_code

    _log_auth_event("auth:register", user.id, f"Registrierung: {user.username}")
    if current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False):
        return jsonify({
            "verification_required": True,
            "message": "Bitte bestätige deine E-Mail-Adresse über den Link in der Mail",
            "user": user.to_dict(),
        }), 201
    return jsonify({
        "access_token": issue_access_token(user),
        "token_type": "Bearer",
        "user": user.to_dict(),
    }), 201


@auth_bp.route("/verify-email", methods=["POST"])
def verify_email_endpoint():
    """Bestaetigt die E-Mail-Adresse mit dem Token aus der Verifizierungs-Mail."""
    from app.domain.accounts.service import AccountError, verify_email

    data = request.get_json() or {}
    try:
        user = verify_email(data.get("token"))
    except AccountError as e:
        return jsonify({"error": e.message}), e.status_code
    _log_auth_event("auth:email_verified", user.id, f"E-Mail bestätigt: {user.username}")
    return jsonify({"message": "E-Mail-Adresse bestätigt"})


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification_endpoint():
    """Sendet die Verifizierungs-Mail erneut. Antwortet immer gleich."""
    from app.domain.accounts.service import resend_verification

    data = request.get_json() or {}
    resend_verification(data.get("email") or data.get("login"))
    return jsonify({"message": "Falls die Adresse existiert und unbestätigt ist, wurde eine E-Mail versendet"})


@auth_bp.route("/password-reset/request", methods=["POST"])
def password_reset_request():
    """Sendet einen Reset-Link. Antwortet immer gleich, damit keine Adressen preisgegeben werden."""
    from app.domain.accounts.service import request_password_reset

    data = request.get_json() or {}
    captcha_error = _check_captcha(data)
    if captcha_error:
        return captcha_error
    request_password_reset(data.get("email"))
    return jsonify({"message": "Falls die Adresse existiert, wurde eine E-Mail versendet"})


@auth_bp.route("/password-reset/confirm", methods=["POST"])
def password_reset_confirm():
    """Setzt das Passwort mit einem Reset-Token neu."""
    from app.domain.accounts.service import AccountError, confirm_password_reset

    data = request.get_json() or {}
    try:
        user = confirm_password_reset(data.get("token"), data.get("password"))
    except AccountError as e:
        return jsonify({"error": e.message}), e.status_code

    _log_auth_event("auth:password_reset", user.id, f"Passwort zurückgesetzt: {user.username}")
    return jsonify({"message": "Passwort wurde geändert"})


@auth_bp.route("/change-password", methods=["POST"])
def change_password_endpoint():
    """Aendert das Passwort des eingeloggten Nutzers. Body: {current_password, new_password}."""
    from app.domain.accounts.service import AccountError, change_password

    user, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    try:
        change_password(user, data.get("current_password"), data.get("new_password"))
    except AccountError as e:
        _log_auth_event("auth:password_change_failed", user.id,
                        f"Passwort-Änderung fehlgeschlagen: {user.username}")
        return jsonify({"error": e.message}), e.status_code

    _log_auth_event("auth:password_changed", user.id, f"Passwort geändert: {user.username}")
    # Alle bisherigen Tokens sind jetzt ungueltig; dieses Gerät bekommt ein frisches und bleibt angemeldet
    return jsonify({"message": "Passwort wurde geändert", "access_token": issue_access_token(user)})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout: das verwendete Access-Token wird bis zu seinem Ablauf gesperrt (M61).

    Andere Tokens des Kontos (andere Geraete) bleiben gueltig. API-Keys und der Dev-Header X-User-Id haben
    kein Token, das sich sperren liesse.
    """
    user, err = require_auth()
    if err:
        return err

    revoked = _revoke_current_token(user)
    _log_auth_event("auth:logout", user.id, f"Logout: {user.username}")
    return jsonify({"message": "Erfolgreich ausgeloggt", "token_revoked": revoked})


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
        return jsonify({"message": "API Key gelöscht"})
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


@auth_bp.route("/mfa/recovery-codes", methods=["POST"])
def mfa_recovery_codes():
    """Erzeugt neue Recovery-Codes (alte werden ungueltig). Body: {password}. Klartext nur in dieser Antwort."""
    user, err = require_auth()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    from app.domain.auth.mfa_service import regenerate_recovery_codes, MfaError
    try:
        result = regenerate_recovery_codes(user, data.get("password"))
    except MfaError as e:
        body = {"error": e.message}
        if e.status_code == 403:
            body["code"] = "invalid_password"
        return jsonify(body), e.status_code
    return jsonify(result)


# ── Hilfsfunktionen ─────────────────────────────────────


def _revoke_current_token(user) -> bool:
    """Sperrt das JWT des aktuellen Requests. False, wenn keins verwendet wurde (API-Key, Dev-Header) oder es fehlschlug."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or header[7:].startswith("astra_"):
        return False
    try:
        from datetime import datetime, timezone
        from flask_jwt_extended import decode_token
        from app.domain.auth.blocklist import revoke_token
        decoded = decode_token(header[7:])
        jti, exp = decoded.get("jti"), decoded.get("exp")
        if not jti or exp is None:
            return False  # Token ohne jti (aelter): bleibt bis zum Ablauf gueltig
        revoke_token(jti, datetime.fromtimestamp(exp, tz=timezone.utc), user.id)
        return True
    except Exception:  # Logout darf nie scheitern: der Client verwirft das Token trotzdem
        current_app.logger.exception("Logout: Token konnte nicht gesperrt werden")
        return False


def _limited(retry_after: int):
    from app.infrastructure.ratelimit import limited_response
    return limited_response(retry_after)


def _login_failure_key(login_field) -> str:
    return "loginfail:" + str(login_field).strip().lower()[:200]


def _login_failures_blocked(login_field) -> tuple[bool, int]:
    """Sperre je Konto: RATELIMIT_LOGIN_FAILURES_PER_HOUR Fehlversuche pro Stunde (nur bei aktivem Rate Limiting)."""
    if not current_app.config.get("RATELIMIT_ENABLED", True):
        return False, 0
    from app.infrastructure import ratelimit
    limit = int(current_app.config.get("RATELIMIT_LOGIN_FAILURES_PER_HOUR", 20))
    return ratelimit.blocked(_login_failure_key(login_field), limit, ratelimit.HOUR_SECONDS,
                             current_app.config.get("REDIS_URL"))


def _record_login_failure(login_field) -> None:
    if not current_app.config.get("RATELIMIT_ENABLED", True):
        return
    from app.infrastructure import ratelimit
    ratelimit.record(_login_failure_key(login_field), ratelimit.HOUR_SECONDS, current_app.config.get("REDIS_URL"))


def _check_captcha(data: dict):
    """None, wenn kein CAPTCHA verlangt wird oder es bestanden ist; sonst die Fehlerantwort (400/503)."""
    from app.domain.accounts import captcha
    if not captcha.required():
        return None
    try:
        ok = captcha.verify(data.get("captcha_token"), request.remote_addr)
    except captcha.CaptchaUnavailable:
        return jsonify({"error": "Die Sicherheitsprüfung ist gerade nicht erreichbar, bitte später erneut versuchen",
                        "code": "captcha_unavailable"}), 503
    if not ok:
        return jsonify({"error": "Sicherheitsprüfung fehlgeschlagen, bitte erneut versuchen",
                        "code": "captcha_failed"}), 400
    return None


def _notify_recovery_used(user, remaining: int) -> None:
    """Mail an den Kontoinhaber, wenn ein Recovery-Code den Login freigegeben hat (best effort)."""
    try:
        from app.i18n import tr
        from app.infrastructure.mail import send_mail
        if user.email:
            warn = tr(user.locale, "mail.recovery_used.warn") if remaining <= 2 else ""
            send_mail(
                current_app, user.email, tr(user.locale, "mail.recovery_used.subject"),
                tr(user.locale, "mail.recovery_used.body", username=user.username, remaining=remaining, warn=warn),
            )
    except Exception:  # pragma: no cover - Mail darf den Login nie stoeren
        pass


def _log_auth_event(event: str, actor_id: int | None, description: str,
                    properties: dict | None = None) -> None:
    """Loggt ein Auth-Event (non-blocking)."""
    try:
        from app.domain.activity.service import log_event
        log_event(event=event, actor_id=actor_id, description=description,
                  properties=properties)
    except Exception:
        pass
