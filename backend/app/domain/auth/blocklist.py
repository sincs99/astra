"""Logout-Blocklist fuer Access-Tokens (M61).

Quelle der Wahrheit ist die Tabelle `revoked_tokens` (dauerhaft, von allen Workern geteilt, ueberlebt
Neustarts). Pro authentifiziertem Request kommt ein Primaerschluessel-Lookup dazu. Ein Redis-Cache wurde
bewusst nicht vorgeschaltet: ein Neustart oder Flush von Redis wuerde sonst abgemeldete Tokens wieder
gueltig machen.
"""

import logging
from datetime import datetime, timezone

from app.extensions import db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def revoke_token(jti: str, expires_at: datetime, user_id: int | None = None) -> bool:
    """Sperrt ein Token bis zu seinem Ablauf. Idempotent. True = neu eingetragen.

    Raeumt dabei beilaeufig abgelaufene Eintraege auf (das haelt die Tabelle ohne Cron klein).
    """
    from sqlalchemy.exc import IntegrityError
    from app.domain.auth.models import RevokedToken
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    now = _now()
    try:
        RevokedToken.query.filter(RevokedToken.expires_at < now).delete(synchronize_session=False)
    except Exception:  # pragma: no cover - Aufraeumen darf das Sperren nie verhindern
        db.session.rollback()
        logger.exception("Blocklist: Aufraeumen fehlgeschlagen")
    if db.session.get(RevokedToken, jti) is not None:
        db.session.commit()
        return False
    db.session.add(RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at, revoked_at=now))
    try:
        db.session.commit()
    except IntegrityError:  # paralleler Logout mit demselben Token
        db.session.rollback()
        return False
    return True


def is_revoked(jti: str | None) -> bool:
    """True, wenn das Token per Logout gesperrt wurde. Tokens ohne jti sind nie gesperrt (wie vor M61)."""
    if not jti:
        return False
    from app.domain.auth.models import RevokedToken
    return db.session.get(RevokedToken, str(jti)) is not None


def cleanup_revoked_tokens(dry_run: bool = False, now: datetime | None = None) -> dict:
    """Loescht abgelaufene Eintraege (das Token waere ohnehin ungueltig)."""
    from app.domain.auth.models import RevokedToken
    query = RevokedToken.query.filter(RevokedToken.expires_at < (now or _now()))
    count = query.count()
    if count and not dry_run:
        query.delete(synchronize_session=False)
        db.session.commit()
    return {"matched": count, "deleted": 0 if dry_run else count}
