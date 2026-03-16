"""Backup-Domain-Modell."""

import uuid as _uuid
from app.extensions import db
from datetime import datetime, timezone


class Backup(db.Model):
    __tablename__ = "backups"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(_uuid.uuid4()))
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=False)
    name = db.Column(db.String(191), nullable=False)
    ignored_files = db.Column(db.Text, nullable=True)
    disk = db.Column(db.String(32), default="runner")  # "runner" oder "s3"
    checksum = db.Column(db.String(64), nullable=True)
    bytes = db.Column(db.BigInteger, default=0)
    is_successful = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    instance = db.relationship("Instance", backref="backups", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "instance_id": self.instance_id,
            "name": self.name,
            "ignored_files": self.ignored_files,
            "disk": self.disk,
            "checksum": self.checksum,
            "bytes": self.bytes,
            "is_successful": self.is_successful,
            "is_locked": self.is_locked,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Backup {self.name} ({self.uuid})>"
