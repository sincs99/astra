"""MFA-Service: TOTP-basierte Zwei-Faktor-Authentifizierung."""

import hmac
import logging
import re
import secrets

import pyotp
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.domain.users.models import User

logger = logging.getLogger(__name__)


RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # ohne leicht verwechselbare Zeichen (i, l, o, 0, 1)
_HASH_PREFIXES = ("scrypt:", "pbkdf2:")
_TOTP_RE = re.compile(r"^\d{6}$")


class MfaError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def _normalize_code(code) -> str:
    return re.sub(r"[\s-]", "", str(code or "")).lower()


def _new_recovery_codes() -> tuple[list[str], list[str]]:
    """Erzeugt Recovery-Codes. Rueckgabe: (Klartext fuer die einmalige Anzeige, Hashes zum Speichern)."""
    plain = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        plain.append(f"{raw[:5]}-{raw[5:]}")
    return plain, [generate_password_hash(_normalize_code(c)) for c in plain]


def recovery_codes_remaining(user: User) -> int:
    return len(user.mfa_recovery_codes or []) if user.mfa_enabled else 0


def regenerate_recovery_codes(user: User, password: str) -> dict:
    """Erzeugt neue Recovery-Codes (die alten werden ungueltig). Das Passwort muss erneut angegeben werden."""
    if not user.mfa_enabled:
        raise MfaError("MFA ist nicht aktiviert", 409)
    if not password or not user.check_password(password):
        raise MfaError("Passwort ist falsch", 403)
    plain, hashes = _new_recovery_codes()
    user.mfa_recovery_codes = hashes
    db.session.commit()
    try:
        from app.domain.activity.service import log_event
        log_event(event="auth:mfa_recovery_codes_regenerated", actor_id=user.id,
                  description=f"MFA-Recovery-Codes neu erzeugt für {user.username}")
    except Exception:
        pass
    return {
        "recovery_codes": plain,
        "recovery_codes_remaining": len(plain),
        "message": "Neue Recovery-Codes erzeugt. Die alten sind ungültig. Jeder Code gilt nur einmal.",
    }


def consume_recovery_code(user: User, code: str) -> bool:
    """Prueft einen Recovery-Code und verbraucht ihn (einmalig, parallelisierungssicher)."""
    normalized = _normalize_code(code)
    if not normalized or _TOTP_RE.match(normalized):
        return False
    # Zeilensperre: derselbe Code darf bei parallelen Logins nicht zweimal gelten (PostgreSQL)
    locked = db.session.query(User).filter_by(id=user.id).with_for_update().one()
    stored = list(locked.mfa_recovery_codes or [])
    for entry in stored:
        if entry.startswith(_HASH_PREFIXES):
            ok = check_password_hash(entry, normalized)
        else:  # Altbestand (vor M60 im Klartext gespeichert), solange die Migration nicht lief
            ok = hmac.compare_digest(_normalize_code(entry), normalized)
        if ok:
            stored.remove(entry)
            locked.mfa_recovery_codes = stored
            db.session.commit()
            logger.info("Recovery-Code verwendet fuer User %s", locked.username)
            return True
    db.session.rollback()
    return False


def setup_mfa(user: User) -> dict:
    """Initialisiert MFA fuer einen User. Gibt Secret und Provisioning-URI zurueck.

    MFA wird erst nach Verifikation aktiviert.
    """
    if user.mfa_enabled:
        raise MfaError("MFA ist bereits aktiviert")

    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.session.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=user.email,
        issuer_name=current_app.config.get("MFA_ISSUER_NAME") or "Astra Panel",
    )

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "MFA-Setup initialisiert. Bitte mit Authenticator-App scannen und Code verifizieren.",
    }


def verify_and_enable_mfa(user: User, code: str) -> dict:
    """Verifiziert den TOTP-Code und aktiviert MFA.

    Wird beim erstmaligen Setup aufgerufen.
    """
    if not user.mfa_secret:
        raise MfaError("MFA-Setup wurde nicht gestartet")

    if user.mfa_enabled:
        raise MfaError("MFA ist bereits aktiviert")

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise MfaError("Ungültiger Verifikationscode", 401)

    # Recovery-Codes generieren: Klartext nur in dieser Antwort, gespeichert werden nur Hashes
    recovery_codes, hashes = _new_recovery_codes()

    user.mfa_enabled = True
    user.mfa_recovery_codes = hashes
    db.session.commit()

    logger.info("MFA aktiviert fuer User %s", user.username)

    try:
        from app.domain.activity.service import log_event
        log_event(
            event="auth:mfa_enabled",
            actor_id=user.id,
            description=f"MFA aktiviert für {user.username}",
        )
    except Exception:
        pass

    return {
        "mfa_enabled": True,
        "recovery_codes": recovery_codes,
        "recovery_codes_remaining": len(recovery_codes),
        "message": "MFA erfolgreich aktiviert. Recovery-Codes sicher aufbewahren: sie werden nur jetzt angezeigt!",
    }


def verify_mfa_login(user: User, code: str) -> str | None:
    """Prueft den zweiten Faktor beim Login. Rueckgabe: "totp", "recovery" oder None (ungueltig)."""
    if not user.mfa_enabled or not user.mfa_secret:
        return "totp"  # MFA nicht aktiv = immer OK
    code = str(code or "").strip()
    if _TOTP_RE.match(code) and pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
        return "totp"
    if consume_recovery_code(user, code):
        return "recovery"
    return None


def verify_totp(user: User, code: str) -> bool:
    """Verifiziert einen TOTP-Code (oder einen einmaligen Recovery-Code) fuer den Login."""
    return verify_mfa_login(user, code) is not None


def disable_mfa(user: User) -> dict:
    """Deaktiviert MFA fuer einen User."""
    if not user.mfa_enabled:
        raise MfaError("MFA ist nicht aktiviert")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    db.session.commit()

    logger.info("MFA deaktiviert fuer User %s", user.username)

    try:
        from app.domain.activity.service import log_event
        log_event(
            event="auth:mfa_disabled",
            actor_id=user.id,
            description=f"MFA deaktiviert für {user.username}",
        )
    except Exception:
        pass

    return {"mfa_enabled": False, "message": "MFA deaktiviert"}
