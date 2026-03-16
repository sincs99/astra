"""Endpoint-Domain-Modell."""

from app.extensions import db
from datetime import datetime, timezone


class Endpoint(db.Model):
    __tablename__ = "endpoints"

    id = db.Column(db.Integer, primary_key=True)

    # Gehört zu einem Agent
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=False)

    # Wird einer Instance zugewiesen (nullable = frei)
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=True)

    # Netzwerk-Daten
    ip = db.Column(db.String(45), nullable=False, default="0.0.0.0")
    port = db.Column(db.Integer, nullable=False)

    # Sperr-Flag
    is_locked = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    agent = db.relationship("Agent", backref="endpoints", lazy=True)
    instance = db.relationship(
        "Instance",
        backref="endpoints",
        foreign_keys=[instance_id],
        lazy=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "instance_id": self.instance_id,
            "ip": self.ip,
            "port": self.port,
            "is_locked": self.is_locked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Endpoint {self.ip}:{self.port}>"
