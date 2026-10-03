"""Kleiner Schluessel-Wert-Speicher fuer Betriebszustand (M53), z.B. der letzte Lauf des Billing-Ticks."""

from datetime import datetime, timezone

from app.extensions import db
from app.utils.timeutil import iso_utc


class SystemState(db.Model):
    __tablename__ = "system_state"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "updated_at": iso_utc(self.updated_at)}
