"""ApiKey-Domain-Modell."""

import secrets
import hashlib
from app.extensions import db
from datetime import datetime, timezone


class ApiKey(db.Model):
    """API-Key fuer programmatischen Zugriff."""
    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key_type = db.Column(db.String(32), nullable=False, default="account")  # account, application
    identifier = db.Column(db.String(16), unique=True, nullable=False)  # Prefix fuer Identifikation
    token_hash = db.Column(db.String(128), nullable=False)
    memo = db.Column(db.String(255), nullable=True)
    allowed_ips = db.Column(db.Text, nullable=True)  # Kommagetrennte IPs oder null
    permissions = db.Column(db.JSON, nullable=True)  # Liste erlaubter Permissions
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", backref="api_keys", lazy=True)

    def is_expired(self) -> bool:
        """Prueft ob der Key abgelaufen ist."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        """Serialisiert den API Key – token_hash wird NIE serialisiert."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_type": self.key_type,
            "identifier": self.identifier,
            "memo": self.memo,
            "allowed_ips": self.allowed_ips,
            "permissions": self.permissions,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def generate_token() -> tuple[str, str, str]:
        """Generiert ein neues API-Token.

        Returns:
            (raw_token, identifier, token_hash)
            raw_token wird genau EINMAL zurueckgegeben und nie gespeichert.
        """
        identifier = "astra_" + secrets.token_hex(4)
        secret_part = secrets.token_urlsafe(32)
        raw_token = f"{identifier}.{secret_part}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        return raw_token, identifier, token_hash

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Hasht einen Raw-Token fuer Vergleich."""
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def __repr__(self):
        return f"<ApiKey {self.identifier} (user={self.user_id})>"
