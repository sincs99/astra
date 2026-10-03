"""Selbstregistrierung und Passwort-Reset.

Reset-Tokens sind signiert (SECRET_KEY) und zeitlich begrenzt. Sie enthalten
einen Fingerabdruck des aktuellen Passwort-Hashes und werden dadurch nach der
ersten erfolgreichen Verwendung ungueltig. Es ist keine Tabelle noetig.
"""

import hashlib
import re

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.domain.users.models import User
from app.infrastructure.mail import send_mail

MIN_PASSWORD_LENGTH = 8
RESET_SALT = "astra-password-reset"
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


def register_user(username: str, email: str, password: str) -> User:
    if not current_app.config.get("REGISTRATION_ENABLED", False):
        raise AccountError("Registrierung ist deaktiviert", 403)
    if not username or not email:
        raise AccountError("Felder 'username' und 'email' sind erforderlich")
    username = username.strip()
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise AccountError("Ungueltige E-Mail-Adresse")
    _check_password(password)
    if User.query.filter_by(username=username).first():
        raise AccountError("Benutzername bereits vergeben", 409)
    if User.query.filter(db.func.lower(User.email) == email).first():
        raise AccountError("E-Mail bereits registriert", 409)

    user = User(username=username, email=email, is_admin=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def request_password_reset(email: str) -> None:
    """Sendet einen Reset-Link, falls die Adresse existiert. Verraet nichts nach aussen."""
    if not email:
        return
    user = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
    if not user:
        return
    token = _serializer().dumps({"uid": user.id, "fp": _fingerprint(user)})
    base = current_app.config.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    link = f"{base}/reset-password?token={token}"
    minutes = current_app.config.get("PASSWORD_RESET_TTL_MINUTES", 60)
    send_mail(
        current_app,
        user.email,
        "Astra: Passwort zuruecksetzen",
        f"Hallo {user.username},\n\n"
        f"ueber diesen Link kannst du dein Passwort zuruecksetzen "
        f"(gueltig {minutes} Minuten):\n{link}\n\n"
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
        raise AccountError("Ungueltiger Reset-Link", 400)

    user = db.session.get(User, data.get("uid"))
    if not user or data.get("fp") != _fingerprint(user):
        raise AccountError("Ungueltiger oder bereits verwendeter Reset-Link", 400)

    user.set_password(new_password)
    db.session.commit()
    return user
