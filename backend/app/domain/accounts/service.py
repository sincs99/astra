"""Selbstregistrierung und Passwort-Reset.

Reset-Tokens sind signiert (SECRET_KEY) und zeitlich begrenzt. Sie enthalten
einen Fingerabdruck des aktuellen Passwort-Hashes und werden dadurch nach der
ersten erfolgreichen Verwendung ungueltig. Es ist keine Tabelle noetig.
"""

import hashlib
import re
from datetime import datetime, timezone

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.domain.users.models import User
from app.infrastructure.mail import send_mail

MIN_PASSWORD_LENGTH = 8
RESET_SALT = "astra-password-reset"
VERIFY_SALT = "astra-email-verification"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def _fingerprint(user: User) -> str:
    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:16]


def _check_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein")


def register_user(username: str, email: str, password: str, locale: str | None = None) -> User:
    if not current_app.config.get("REGISTRATION_ENABLED", False):
        raise AccountError("Registrierung ist deaktiviert", 403)
    if not username or not email:
        raise AccountError("Felder 'username' und 'email' sind erforderlich")
    username = username.strip()
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise AccountError("Ungültige E-Mail-Adresse")
    _check_password(password)
    if locale is not None:
        from app.i18n import validate_locale
        if validate_locale(locale) is None:
            raise AccountError("Ungültige Sprache (erlaubt: de, en)")
    if User.query.filter_by(username=username).first():
        raise AccountError("Benutzername bereits vergeben", 409)
    if User.query.filter(db.func.lower(User.email) == email).first():
        raise AccountError("E-Mail bereits registriert", 409)

    user = User(username=username, email=email, is_admin=False, locale=locale)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    if current_app.config.get("EMAIL_VERIFICATION_REQUIRED", False):
        send_verification_email(user)
    return user


def _verify_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=VERIFY_SALT)


def send_verification_email(user: User) -> bool:
    token = _verify_serializer().dumps({"uid": user.id, "email": user.email})
    base = current_app.config.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    hours = current_app.config.get("EMAIL_VERIFICATION_TTL_HOURS", 48)
    return send_mail(
        current_app,
        user.email,
        "Astra: E-Mail-Adresse bestätigen",
        f"Hallo {user.username},\n\n"
        f"bitte bestätige deine E-Mail-Adresse (gültig {hours} Stunden):\n"
        f"{base}/verify-email?token={token}\n\n"
        f"Falls du dich nicht registriert hast, ignoriere diese Mail.\n",
    )


def verify_email(token: str) -> User:
    max_age = current_app.config.get("EMAIL_VERIFICATION_TTL_HOURS", 48) * 3600
    try:
        data = _verify_serializer().loads(token or "", max_age=max_age)
    except SignatureExpired:
        raise AccountError("Bestätigungs-Link ist abgelaufen", 400)
    except BadSignature:
        raise AccountError("Ungültiger Bestätigungs-Link", 400)
    user = db.session.get(User, data.get("uid"))
    if not user or user.email != data.get("email"):
        raise AccountError("Ungültiger Bestätigungs-Link", 400)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        db.session.commit()
    return user


def resend_verification(email: str) -> None:
    """Sendet den Link erneut (Adresse oder Benutzername), falls Konto existiert und unbestaetigt ist. Verraet nichts nach aussen."""
    if not email:
        return
    login = email.strip().lower()
    user = User.query.filter(
        db.or_(db.func.lower(User.email) == login, db.func.lower(User.username) == login)
    ).first()
    if user and user.email_verified_at is None:
        send_verification_email(user)


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Passwort fuer einen eingeloggten Nutzer aendern (aktuelles Passwort erforderlich)."""
    if not current_password or not user.check_password(current_password):
        raise AccountError("Aktuelles Passwort ist falsch", 401)
    _check_password(new_password)
    if new_password == current_password:
        raise AccountError("Das neue Passwort muss sich vom aktuellen unterscheiden")
    user.set_password(new_password)
    db.session.commit()


def request_password_reset(email: str) -> None:
    """Sendet einen Reset-Link, falls die Adresse existiert. Verraet nichts nach aussen."""
    if not email:
        return
    user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
    if not user:
        return
    token = _serializer().dumps({"uid": user.id, "fp": _fingerprint(user)})
    base = current_app.config.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    link = f"{base}/password-reset/confirm?token={token}"
    minutes = current_app.config.get("PASSWORD_RESET_TTL_MINUTES", 60)
    send_mail(
        current_app,
        user.email,
        "Astra: Passwort zurücksetzen",
        f"Hallo {user.username},\n\n"
        f"über diesen Link kannst du dein Passwort zurücksetzen "
        f"(gültig {minutes} Minuten):\n{link}\n\n"
        f"Falls du das nicht angefordert hast, ignoriere diese Mail.\n",
    )


def confirm_password_reset(token: str, new_password: str) -> User:
    _check_password(new_password)
    max_age = current_app.config.get("PASSWORD_RESET_TTL_MINUTES", 60) * 60
    try:
        data = _serializer().loads(token or "", max_age=max_age)
    except SignatureExpired:
        raise AccountError("Reset-Link ist abgelaufen", 400)
    except BadSignature:
        raise AccountError("Ungültiger Reset-Link", 400)

    user = db.session.get(User, data.get("uid"))
    if not user or data.get("fp") != _fingerprint(user):
        raise AccountError("Ungültiger oder bereits verwendeter Reset-Link", 400)

    user.set_password(new_password)
    if user.email_verified_at is None:
        # Wer den Reset-Link aus dem Postfach nutzt, hat die Adresse damit bestaetigt
        user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return user
