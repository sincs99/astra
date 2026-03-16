"""Zentraler Activity-Logging-Service."""

import logging

from app.extensions import db
from app.domain.activity.models import ActivityLog

logger = logging.getLogger(__name__)


def log_event(
    event: str,
    actor_id: int | None = None,
    actor_type: str = "user",
    subject_id: int | None = None,
    subject_type: str | None = None,
    description: str | None = None,
    properties: dict | None = None,
    ip_address: str | None = None,
) -> ActivityLog:
    """Erstellt einen Activity-Log-Eintrag und löst Webhook-Dispatch aus."""
    entry = ActivityLog(
        event=event,
        actor_id=actor_id,
        actor_type=actor_type,
        subject_id=subject_id,
        subject_type=subject_type,
        description=description,
        properties=properties,
        ip_address=ip_address,
    )
    db.session.add(entry)
    db.session.commit()

    # Webhook-Dispatch auslösen (non-blocking, Fehler werden geloggt)
    try:
        from app.domain.webhooks.dispatcher import dispatch_webhook_event
        dispatch_webhook_event(
            event=event,
            actor_id=actor_id,
            actor_type=actor_type,
            subject_id=subject_id,
            subject_type=subject_type,
            description=description,
            properties=properties,
        )
    except Exception as e:
        logger.warning("Webhook-Dispatch für Event '%s' fehlgeschlagen: %s", event, str(e))

    return entry


def list_for_instance(instance_id: int, limit: int = 50) -> list[ActivityLog]:
    """Listet Activity-Logs für eine Instance."""
    return (
        ActivityLog.query.filter_by(subject_id=instance_id, subject_type="instance")
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )


def list_for_user(user_id: int, limit: int = 50) -> list[ActivityLog]:
    """Listet Activity-Logs eines Users."""
    return (
        ActivityLog.query.filter_by(actor_id=user_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )


def list_global(
    event: str | None = None,
    actor_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Listet alle Activity-Logs mit optionalen Filtern (paginiert)."""
    query = ActivityLog.query

    if event:
        query = query.filter_by(event=event)
    if actor_id:
        query = query.filter_by(actor_id=actor_id)

    query = query.order_by(ActivityLog.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [i.to_dict() for i in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
