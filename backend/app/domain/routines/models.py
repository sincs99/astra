"""Routine- und Action-Domain-Modelle."""

from app.extensions import db
from datetime import datetime, timezone


class Routine(db.Model):
    __tablename__ = "routines"

    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=False)
    name = db.Column(db.String(191), nullable=False)

    # Cron-Felder
    cron_minute = db.Column(db.String(20), default="*")
    cron_hour = db.Column(db.String(20), default="*")
    cron_day_month = db.Column(db.String(20), default="*")
    cron_month = db.Column(db.String(20), default="*")
    cron_day_week = db.Column(db.String(20), default="*")

    is_active = db.Column(db.Boolean, default=True)
    is_processing = db.Column(db.Boolean, default=False)
    only_when_online = db.Column(db.Boolean, default=True)

    last_run_at = db.Column(db.DateTime, nullable=True)
    next_run_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    instance = db.relationship("Instance", backref="routines", lazy=True)
    actions = db.relationship("Action", backref="routine", lazy=True, order_by="Action.sequence", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instance_id": self.instance_id,
            "name": self.name,
            "cron_minute": self.cron_minute,
            "cron_hour": self.cron_hour,
            "cron_day_month": self.cron_day_month,
            "cron_month": self.cron_month,
            "cron_day_week": self.cron_day_week,
            "is_active": self.is_active,
            "is_processing": self.is_processing,
            "only_when_online": self.only_when_online,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Routine {self.name}>"


class Action(db.Model):
    __tablename__ = "actions"
    __table_args__ = (
        db.UniqueConstraint("routine_id", "sequence", name="uq_routine_sequence"),
    )

    id = db.Column(db.Integer, primary_key=True)
    routine_id = db.Column(db.Integer, db.ForeignKey("routines.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    delay_seconds = db.Column(db.Integer, default=0)
    continue_on_failure = db.Column(db.Boolean, default=False)
    is_queued = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "routine_id": self.routine_id,
            "sequence": self.sequence,
            "action_type": self.action_type,
            "payload": self.payload,
            "delay_seconds": self.delay_seconds,
            "continue_on_failure": self.continue_on_failure,
            "is_queued": self.is_queued,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Action {self.action_type} seq={self.sequence}>"
