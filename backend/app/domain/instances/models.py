"""Instance-Domain-Modell."""

import uuid as _uuid
from app.extensions import db
from datetime import datetime, timezone


class Instance(db.Model):
    __tablename__ = "instances"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4())
    )
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Beziehungen
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=False)
    blueprint_id = db.Column(db.Integer, db.ForeignKey("blueprints.id"), nullable=False)
    primary_endpoint_id = db.Column(
        db.Integer, db.ForeignKey("endpoints.id"), nullable=True
    )

    # Fachlicher Lifecycle-Status (provisioning, provision_failed, reinstalling, reinstall_failed, restoring, suspended, None=ready)
    status = db.Column(db.String(32), default="stopped")

    # Runtime Container-Status von Wings (running, starting, stopping, stopped, offline, unknown)
    container_state = db.Column(db.String(32), nullable=True)

    # Zeitpunkt der ersten erfolgreichen Installation
    installed_at = db.Column(db.DateTime, nullable=True)

    # M29: Administrativer Suspension-Status
    suspended_reason = db.Column(db.String(500), nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    suspended_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Ressourcen
    memory = db.Column(db.Integer, default=512)       # MB
    swap = db.Column(db.Integer, default=0)            # MB
    disk = db.Column(db.Integer, default=1024)         # MB
    io = db.Column(db.Integer, default=500)            # IO-Weight
    cpu = db.Column(db.Integer, default=100)           # CPU-Limit in %

    # Container-Konfiguration
    image = db.Column(db.String(255), nullable=True)
    startup_command = db.Column(db.Text, nullable=True)

    # Blueprint-Variablen-Werte: {env_var: value} – überschreibt Blueprint-Defaults
    variable_values = db.Column(db.JSON, nullable=True, default=dict)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = db.relationship("User", foreign_keys=[owner_id], backref="instances", lazy=True)
    suspended_by = db.relationship("User", foreign_keys=[suspended_by_user_id], lazy=True)
    agent = db.relationship("Agent", backref="instances", lazy=True)
    blueprint = db.relationship("Blueprint", backref="instances", lazy=True)
    primary_endpoint = db.relationship(
        "Endpoint", foreign_keys=[primary_endpoint_id], lazy=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "agent_id": self.agent_id,
            "blueprint_id": self.blueprint_id,
            "primary_endpoint_id": self.primary_endpoint_id,
            "status": self.status,
            "container_state": self.container_state,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "memory": self.memory,
            "swap": self.swap,
            "disk": self.disk,
            "io": self.io,
            "cpu": self.cpu,
            "image": self.image,
            "startup_command": self.startup_command,
            "variable_values": self.variable_values or {},
            "suspended_reason": self.suspended_reason,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "suspended_by_user_id": self.suspended_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Instance {self.name} ({self.uuid})>"
