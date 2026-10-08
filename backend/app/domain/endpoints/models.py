"""Endpoint-Domain-Modell."""

from app.extensions import db
from datetime import datetime, timezone
from app.utils.timeutil import iso_utc


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

    # M82: false nimmt den Endpoint aus der automatischen Vergabe (z.B. Query-Port eines Spiels), ohne ihn zu sperren.
    # Die explizite Zuweisung (endpoint_id) bleibt moeglich.
    auto_assign = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

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
            "auto_assign": bool(self.auto_assign) if self.auto_assign is not None else True,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self):
        return f"<Endpoint {self.ip}:{self.port}>"
