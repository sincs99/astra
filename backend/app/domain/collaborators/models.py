"""Collaborator-Domain-Modell."""

from app.extensions import db
from datetime import datetime, timezone


class Collaborator(db.Model):
    __tablename__ = "collaborators"
    __table_args__ = (
        db.UniqueConstraint("user_id", "instance_id", name="uq_user_instance"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=False)
    permissions = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", backref="collaborations", lazy=True)
    instance = db.relationship("Instance", backref="collaborators", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "instance_id": self.instance_id,
            "permissions": self.permissions,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Collaborator user={self.user_id} instance={self.instance_id}>"
