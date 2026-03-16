"""Service-Logik für Webhooks."""

import logging
import secrets
from urllib.parse import urlparse

from app.extensions import db
from app.domain.webhooks.models import Webhook
from app.domain.webhooks.event_catalog import validate_webhook_events

logger = logging.getLogger(__name__)


class WebhookError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Validierung ─────────────────────────────────────────


def _validate_url(url: str) -> None:
    """Prüft, ob die URL ein gültiges HTTP(S)-Ziel ist."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise WebhookError("endpoint_url muss http:// oder https:// verwenden")
        if not parsed.netloc:
            raise WebhookError("endpoint_url hat keinen gültigen Host")
    except ValueError:
        raise WebhookError("endpoint_url ist keine gültige URL")


def _validate_events(events: list[str]) -> None:
    """Prüft, ob alle Events im Katalog sind."""
    if not events:
        raise WebhookError("Mindestens ein Event muss angegeben werden")
    ok, invalid = validate_webhook_events(events)
    if not ok:
        raise WebhookError(f"Ungültige Webhook-Events: {', '.join(invalid)}")


# ── CRUD ────────────────────────────────────────────────


def list_webhooks() -> list[Webhook]:
    """Gibt alle Webhooks zurück, sortiert nach Erstelldatum."""
    return Webhook.query.order_by(Webhook.created_at.desc()).all()


def get_webhook(webhook_id: int) -> Webhook:
    """Einzelnen Webhook laden."""
    wh = db.session.get(Webhook, webhook_id)
    if not wh:
        raise WebhookError(f"Webhook mit ID {webhook_id} nicht gefunden", 404)
    return wh


def create_webhook(
    endpoint_url: str,
    events: list[str],
    description: str | None = None,
    secret_token: str | None = None,
    is_active: bool = True,
) -> Webhook:
    """Erstellt einen neuen Webhook."""

    _validate_url(endpoint_url)
    _validate_events(events)

    wh = Webhook(
        endpoint_url=endpoint_url,
        events=events,
        description=description,
        secret_token=secret_token or secrets.token_hex(32),
        is_active=is_active,
    )
    db.session.add(wh)
    db.session.commit()

    logger.info("Webhook erstellt: %s → %s", wh.uuid, endpoint_url)
    return wh


def update_webhook(webhook_id: int, **kwargs) -> Webhook:
    """Aktualisiert einen bestehenden Webhook."""
    wh = get_webhook(webhook_id)

    if "endpoint_url" in kwargs:
        _validate_url(kwargs["endpoint_url"])
        wh.endpoint_url = kwargs["endpoint_url"]

    if "events" in kwargs:
        _validate_events(kwargs["events"])
        wh.events = kwargs["events"]

    if "description" in kwargs:
        wh.description = kwargs["description"]

    if "secret_token" in kwargs:
        wh.secret_token = kwargs["secret_token"]

    if "is_active" in kwargs:
        wh.is_active = kwargs["is_active"]

    db.session.commit()
    logger.info("Webhook aktualisiert: %s", wh.uuid)
    return wh


def delete_webhook(webhook_id: int) -> None:
    """Löscht einen Webhook."""
    wh = get_webhook(webhook_id)
    db.session.delete(wh)
    db.session.commit()
    logger.info("Webhook gelöscht: %s", wh.uuid)


# ── Event-Matching ──────────────────────────────────────


def find_webhooks_for_event(event: str) -> list[Webhook]:
    """Findet alle aktiven Webhooks, die ein bestimmtes Event abonniert haben."""
    active_hooks = Webhook.query.filter_by(is_active=True).all()
    return [wh for wh in active_hooks if event in (wh.events or [])]
