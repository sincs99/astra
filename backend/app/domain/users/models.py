"""User-Domain-Modell mit Passwort-Hashing und MFA-Feldern."""

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from datetime import datetime, timezone


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    # MFA-Felder (M19)
    mfa_secret = db.Column(db.String(64), nullable=True)  # TOTP Secret
    mfa_enabled = db.Column(db.Boolean, default=False)
    mfa_recovery_codes = db.Column(db.JSON, nullable=True)  # Liste von Recovery-Codes

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password: str) -> None:
        """Hasht und speichert das Passwort."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Prueft ob das Passwort korrekt ist."""
        if not self.password_hash or self.password_hash == "placeholder":
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """Serialisiert den User – Secrets werden NIE serialisiert."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_admin": self.is_admin,
            "mfa_enabled": self.mfa_enabled or False,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<User {self.username}>"
