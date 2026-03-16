"""Database-Domain-Modelle: DatabaseProvider und Database."""

import secrets
from app.extensions import db
from datetime import datetime, timezone


class DatabaseProvider(db.Model):
    """Datenbank-Host-Provider (z.B. ein MySQL/MariaDB-Server)."""
    __tablename__ = "database_providers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=3306)
    admin_user = db.Column(db.String(120), nullable=False, default="root")
    admin_password = db.Column(db.String(256), nullable=True)
    max_databases = db.Column(db.Integer, nullable=True)  # None = unbegrenzt
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    databases = db.relationship("Database", backref="provider", lazy=True)

    def database_count(self) -> int:
        """Aktuelle Anzahl Datenbanken auf diesem Provider."""
        return Database.query.filter_by(provider_id=self.id).count()

    def has_capacity(self) -> bool:
        """Prueft ob der Provider noch Kapazitaet hat."""
        if self.max_databases is None:
            return True
        return self.database_count() < self.max_databases

    def to_dict(self) -> dict:
        """Serialisiert den Provider – admin_password wird NIE serialisiert."""
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "admin_user": self.admin_user,
            "max_databases": self.max_databases,
            "database_count": self.database_count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<DatabaseProvider {self.name} ({self.host}:{self.port})>"


class Database(db.Model):
    """Eine provisionierte Datenbank auf einem Provider, gehoert zu einer Instance."""
    __tablename__ = "databases"

    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.Integer, db.ForeignKey("instances.id"), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey("database_providers.id"), nullable=False)
    db_name = db.Column(db.String(64), nullable=False)
    username = db.Column(db.String(64), nullable=False)
    password = db.Column(db.String(256), nullable=False)
    remote_host = db.Column(db.String(255), nullable=False, default="%")
    max_connections = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    instance = db.relationship("Instance", backref="databases", lazy=True)

    # Unique: db_name pro Provider
    __table_args__ = (
        db.UniqueConstraint("provider_id", "db_name", name="uq_provider_db_name"),
        db.UniqueConstraint("provider_id", "username", name="uq_provider_username"),
    )

    def to_dict(self, include_password: bool = False) -> dict:
        """Serialisiert die Datenbank – password nur bei expliziter Anforderung."""
        d = {
            "id": self.id,
            "instance_id": self.instance_id,
            "provider_id": self.provider_id,
            "db_name": self.db_name,
            "username": self.username,
            "remote_host": self.remote_host,
            "max_connections": self.max_connections,
            "provider_host": self.provider.host if self.provider else None,
            "provider_port": self.provider.port if self.provider else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_password:
            d["password"] = self.password
        return d

    @staticmethod
    def generate_password(length: int = 24) -> str:
        """Generiert ein sicheres zufaelliges Passwort."""
        return secrets.token_urlsafe(length)

    def __repr__(self):
        return f"<Database {self.db_name} on Provider#{self.provider_id}>"
