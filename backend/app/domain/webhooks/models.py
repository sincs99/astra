"""Webhook-Domain-Modell."""

import uuid as _uuid
import secrets
from app.extensions import db
from datetime import datetime, timezone


class Webhook(db.Model):
    __tablename__ = "webhooks"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4())
    )
    endpoint_url = db.Column(db.String(2048), nullable=False)
    description = db.Column(db.Text, nullable=True)
    events = db.Column(db.JSON, nullable=False, default=list)
    secret_token = db.Column(
        db.String(128), nullable=False, default=lambda: secrets.token_hex(32)
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "endpoint_url": self.endpoint_url,
            "description": self.description,
            "events": self.events or [],
            "secret_token": self.secret_token,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Webhook {self.uuid} → {self.endpoint_url}>"


class WebhookDelivery(db.Model):
    """Tracking fuer Webhook-Auslieferungen (M20)."""
    __tablename__ = "webhook_deliveries"

    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey("webhooks.id"), nullable=False)
    event = db.Column(db.String(64), nullable=False)
    endpoint_url = db.Column(db.String(2048), nullable=False)
    attempts = db.Column(db.Integer, default=1)
    success = db.Column(db.Boolean, default=False)
    status_code = db.Column(db.Integer, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    webhook = db.relationship("Webhook", backref="deliveries", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "webhook_id": self.webhook_id,
            "event": self.event,
            "endpoint_url": self.endpoint_url,
            "attempts": self.attempts,
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<WebhookDelivery {self.event} → {self.endpoint_url} ({'OK' if self.success else 'FAIL'})>"
