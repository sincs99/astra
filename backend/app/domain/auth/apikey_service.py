"""API-Key-Service: Erstellen, Validieren, Loeschen."""

import logging
from datetime import datetime, timezone

from app.extensions import db
from app.domain.auth.models import ApiKey
from app.domain.users.models import User

logger = logging.getLogger(__name__)


class ApiKeyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def list_user_keys(user_id: int) -> list[ApiKey]:
    """Listet alle API Keys eines Users."""
    return (
        ApiKey.query.filter_by(user_id=user_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def create_api_key(
    user_id: int,
    key_type: str = "account",
    memo: str | None = None,
    allowed_ips: str | None = None,
    permissions: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Erstellt einen neuen API Key.

    Returns:
        (ApiKey, raw_token) - raw_token wird nur EINMAL zurueckgegeben!
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ApiKeyError("User nicht gefunden", 404)

    if key_type not in ("account", "application"):
        raise ApiKeyError("key_type muss 'account' oder 'application' sein")

    raw_token, identifier, token_hash = ApiKey.generate_token()

    api_key = ApiKey(
        user_id=user_id,
        key_type=key_type,
        identifier=identifier,
        token_hash=token_hash,
        memo=memo,
        allowed_ips=allowed_ips,
        permissions=permissions,
        expires_at=expires_at,
    )
    db.session.add(api_key)
    db.session.commit()

    logger.info("API Key '%s' fuer User %d erstellt", identifier, user_id)

    try:
        from app.domain.activity.service import log_event
        log_event(
            event="auth:api_key_created",
            actor_id=user_id,
            description=f"API Key '{identifier}' erstellt",
            properties={"identifier": identifier, "key_type": key_type},
        )
    except Exception:
        pass

    return api_key, raw_token


def validate_api_key(raw_token: str) -> ApiKey | None:
    """Validiert einen API Key und gibt ihn zurueck wenn gueltig."""
    if not raw_token or "." not in raw_token:
        return None

    token_hash = ApiKey.hash_token(raw_token)
    api_key = ApiKey.query.filter_by(token_hash=token_hash).first()

    if not api_key:
        return None

    if api_key.is_expired():
        return None

    # last_used_at aktualisieren
    api_key.last_used_at = datetime.now(timezone.utc)
    db.session.commit()

    return api_key


def delete_api_key(key_id: int, user_id: int) -> None:
    """Loescht einen API Key."""
    api_key = ApiKey.query.filter_by(id=key_id, user_id=user_id).first()
    if not api_key:
        raise ApiKeyError("API Key nicht gefunden", 404)

    identifier = api_key.identifier
    db.session.delete(api_key)
    db.session.commit()

    logger.info("API Key '%s' geloescht", identifier)

    try:
        from app.domain.activity.service import log_event
        log_event(
            event="auth:api_key_deleted",
            actor_id=user_id,
            description=f"API Key '{identifier}' geloescht",
            properties={"identifier": identifier},
        )
    except Exception:
        pass
