"""Blueprint-Domain-Modell.

Variables-Format (blueprint.variables):
[
  {
    "name": "Server Port",
    "description": "Port the server listens on",
    "env_var": "SERVER_PORT",
    "default_value": "25565",
    "user_viewable": true,
    "user_editable": true
  }
]
"""

from app.extensions import db
from datetime import datetime, timezone


class Blueprint(db.Model):
    __tablename__ = "blueprints"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    docker_image = db.Column(db.String(255), nullable=True)
    startup_command = db.Column(db.Text, nullable=True)
    install_script = db.Column(db.Text, nullable=True)
    # Variablen-Definitionen: Liste von Variable-Objekten (siehe Doku oben)
    variables = db.Column(db.JSON, nullable=True, default=list)
    config_schema = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_default_env(self) -> dict:
        """Gibt die Standard-Umgebungsvariablen aus den Blueprint-Variablen zurück."""
        env = {}
        for var in (self.variables or []):
            env_key = var.get("env_var")
            default = var.get("default_value", "")
            if env_key:
                env[env_key] = str(default) if default is not None else ""
        return env

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "docker_image": self.docker_image,
            "startup_command": self.startup_command,
            "install_script": self.install_script,
            "variables": self.variables or [],
            "config_schema": self.config_schema,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Blueprint {self.name}>"
