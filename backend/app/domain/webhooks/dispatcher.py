"""Webhook-Dispatcher mit Job-Queue (M23).

- Non-blocking Dispatch ueber Job-Queue
- Max 3 Versuche mit exponentiellem Backoff (in Job-Handler)
- Delivery-Tracking ueber WebhookDelivery-Modell
- Rueckwaertskompatibilitaet: dispatch_webhook_event() API bleibt gleich
"""

import logging
from datetime import datetime, timezone

import requests as http_requests

from app.domain.webhooks.event_catalog import is_valid_webhook_event

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = (5, 10)
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]


def dispatch_webhook_event(
    event: str,
    actor_id: int | None = None,
    actor_type: str = "user",
    subject_id: int | None = None,
    subject_type: str | None = None,
    description: str | None = None,
    properties: dict | None = None,
) -> None:
    """Prueft ob aktive Webhooks das Event abonniert haben und versendet sie.

    Ab M23: Webhook-Dispatch laeuft ueber die Job-Queue statt ad-hoc Threading.
    """
    if not is_valid_webhook_event(event):
        return

    try:
        from flask import current_app
        _ = current_app._get_current_object()
    except RuntimeError:
        logger.debug("Kein Flask-App-Kontext - Webhook-Dispatch uebersprungen")
        return

    webhook_payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {"id": actor_id, "type": actor_type},
        "subject": {"id": subject_id, "type": subject_type},
        "description": description,
        "properties": properties or {},
    }

    # Passende Webhooks finden und als Jobs enqueuen
    try:
        from app.domain.webhooks.service import find_webhooks_for_event
        from app.infrastructure.jobs.queue import enqueue_job
        from app.infrastructure.jobs.registry import JOB_TYPE_WEBHOOK_DISPATCH

        webhooks = find_webhooks_for_event(event)
        if not webhooks:
            return

        logger.info("Dispatching Event '%s' an %d Webhook(s) via Job-Queue",
                     event, len(webhooks))

        for wh in webhooks:
            enqueue_job(
                job_type=JOB_TYPE_WEBHOOK_DISPATCH,
                payload={
                    "webhook_id": wh.id,
                    "event": event,
                    "webhook_payload": webhook_payload,
                    "max_retries": MAX_RETRIES,
                    "retry_delays": RETRY_DELAYS,
                },
                max_attempts=1,  # Retry-Logik ist im Handler
                payload_summary={
                    "event": event,
                    "webhook_id": wh.id,
                    "endpoint_url": wh.endpoint_url,
                },
            )
    except Exception as e:
        logger.error("Webhook-Dispatch Fehler: %s", str(e))


def dispatch_test(webhook) -> dict:
    """Sendet einen Test-Payload an einen einzelnen Webhook (synchron)."""
    payload = {
        "event": "webhook:test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": {"id": None, "type": "system"},
        "subject": {"id": webhook.id, "type": "webhook"},
        "description": "Test-Webhook von Astra",
        "properties": {"webhook_uuid": webhook.uuid},
    }

    headers = {
        "Content-Type": "application/json",
        "X-Astra-Event": "webhook:test",
        "X-Astra-Token": webhook.secret_token or "",
        "User-Agent": "Astra-Webhook/1.0",
    }

    try:
        response = http_requests.post(
            webhook.endpoint_url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "message": f"HTTP {response.status_code}",
        }
    except http_requests.Timeout:
        return {"success": False, "status_code": None, "message": "Timeout"}
    except http_requests.ConnectionError:
        return {"success": False, "status_code": None, "message": "Verbindungsfehler"}
    except Exception as e:
        return {"success": False, "status_code": None, "message": str(e)}


# ── Rueckwaertskompatibilitaet (fuer bestehende Tests) ──


def _send_to_webhook(webhook, event: str, payload: dict) -> tuple[bool, int | None, str | None]:
    """Sendet den Payload an einen Webhook. Gibt (success, status_code, error) zurueck.

    Legacy-Kompatibilitaetsfunktion – ab M23 laeuft Dispatch ueber Job-Handler.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Astra-Event": event,
        "X-Astra-Token": webhook.secret_token or "",
        "User-Agent": "Astra-Webhook/1.0",
    }

    try:
        response = http_requests.post(
            webhook.endpoint_url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        is_success = 200 <= response.status_code < 300
        return is_success, response.status_code, None if is_success else f"HTTP {response.status_code}"
    except http_requests.Timeout:
        return False, None, "Timeout"
    except http_requests.ConnectionError:
        return False, None, "Verbindungsfehler"
    except Exception as e:
        return False, None, str(e)


def _track_delivery(webhook, event: str, attempts: int, success: bool,
                    status_code: int | None, error: str | None = None) -> None:
    """Speichert Delivery-Ergebnis (best-effort).

    Legacy-Kompatibilitaetsfunktion – ab M23 laeuft Tracking im Job-Handler.
    """
    try:
        from app.extensions import db
        from app.domain.webhooks.models import WebhookDelivery

        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event,
            endpoint_url=webhook.endpoint_url,
            attempts=attempts,
            success=success,
            status_code=status_code,
            error=error,
        )
        db.session.add(delivery)
        db.session.commit()
    except Exception as e:
        logger.debug("Delivery-Tracking fehlgeschlagen: %s", str(e))
