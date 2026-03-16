"""MFA-Service: TOTP-basierte Zwei-Faktor-Authentifizierung."""

import secrets
import logging

import pyotp

from app.extensions import db
from app.domain.users.models import User

logger = logging.getLogger(__name__)


class MfaError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


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
        issuer_name="Astra Panel",
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
        raise MfaError("Ungueltiger Verifikationscode", 401)

    # Recovery-Codes generieren
    recovery_codes = [secrets.token_hex(4) for _ in range(8)]

    user.mfa_enabled = True
    user.mfa_recovery_codes = recovery_codes
    db.session.commit()

    logger.info("MFA aktiviert fuer User %s", user.username)

    try:
        from app.domain.activity.service import log_event
        log_event(
            event="auth:mfa_enabled",
            actor_id=user.id,
            description=f"MFA aktiviert fuer {user.username}",
        )
    except Exception:
        pass

    return {
        "mfa_enabled": True,
        "recovery_codes": recovery_codes,
        "message": "MFA erfolgreich aktiviert. Recovery-Codes sicher aufbewahren!",
    }


def verify_totp(user: User, code: str) -> bool:
    """Verifiziert einen TOTP-Code fuer Login.

    Prueft auch Recovery-Codes.
    """
    if not user.mfa_enabled or not user.mfa_secret:
        return True  # MFA nicht aktiv = immer OK

    # TOTP pruefen
    totp = pyotp.TOTP(user.mfa_secret)
    if totp.verify(code, valid_window=1):
        return True

    # Recovery-Code pruefen
    if user.mfa_recovery_codes and code in user.mfa_recovery_codes:
        # Recovery-Code einmalig verwenden
        codes = list(user.mfa_recovery_codes)
        codes.remove(code)
        user.mfa_recovery_codes = codes
        db.session.commit()
        logger.info("Recovery-Code verwendet fuer User %s", user.username)
        return True

    return False


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
            description=f"MFA deaktiviert fuer {user.username}",
        )
    except Exception:
        pass

    return {"mfa_enabled": False, "message": "MFA deaktiviert"}
