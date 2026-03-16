"""ActivityLog-Domain-Modell."""

from app.extensions import db
from datetime import datetime, timezone


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(120), nullable=False, index=True)

    # Actor (User oder System)
    actor_id = db.Column(db.Integer, nullable=True, index=True)
    actor_type = db.Column(db.String(32), default="user")  # user, system, agent

    # Subject (worauf sich die Aktion bezieht)
    subject_id = db.Column(db.Integer, nullable=True)
    subject_type = db.Column(db.String(64), nullable=True)  # instance, backup, routine etc.

    description = db.Column(db.Text, nullable=True)
    properties = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event": self.event,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "description": self.description,
            "properties": self.properties,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<ActivityLog {self.event}>"
