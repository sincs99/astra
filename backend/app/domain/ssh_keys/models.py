"""Modell fuer User-SSH-Keys (M28)."""

from datetime import datetime, timezone

from app.extensions import db


class UserSshKey(db.Model):
    __tablename__ = "user_ssh_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(191), nullable=False)
    fingerprint = db.Column(db.String(128), nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "fingerprint", name="uq_user_ssh_key_fingerprint"),
    )

    user = db.relationship("User", backref=db.backref("ssh_keys", lazy="dynamic", cascade="all, delete-orphan"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "fingerprint": self.fingerprint,
            "public_key": self.public_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
