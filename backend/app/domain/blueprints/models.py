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

Prozess-Konfiguration fuer Wings (M33, Format wie Pterodactyl/Pelican-Eggs):
- config_startup: {"done": ["Done ("], "strip_ansi": false}
- config_stop:    "stop"  (Konsolenbefehl) oder "^SIGTERM" (Signal)
- config_files:   {"server.properties": {"parser": "properties",
                    "find": {"server-port": "{{server.build.default.port}}"}}}
- file_denylist:  ["*.jar"]
"""

from app.extensions import db
from datetime import datetime, timezone
from app.utils.timeutil import iso_utc

DEFAULT_INSTALL_CONTAINER = "ghcr.io/parkervcp/installers:debian"  # M82: Debian 12 (das pterodactyl-Image ist Debian 11, apt scheitert)
LEGACY_INSTALL_CONTAINER = "ghcr.io/pterodactyl/installers:debian"
DEFAULT_INSTALL_ENTRYPOINT = "bash"
DEFAULT_CONFIG_STOP = "stop"


class Blueprint(db.Model):
    __tablename__ = "blueprints"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    docker_image = db.Column(db.String(255), nullable=True)
    startup_command = db.Column(db.Text, nullable=True)
    install_script = db.Column(db.Text, nullable=True)
    # M33: Install-Container und Entrypoint fuer das Install-Script (Wings)
    install_container = db.Column(db.String(255), nullable=True)
    install_entrypoint = db.Column(db.String(64), nullable=True)
    # Variablen-Definitionen: Liste von Variable-Objekten (siehe Doku oben)
    variables = db.Column(db.JSON, nullable=True, default=list)
    config_schema = db.Column(db.JSON, nullable=True)
    # M33: Prozess-Konfiguration fuer Wings (siehe Modul-Doku)
    config_startup = db.Column(db.JSON, nullable=True)
    config_stop = db.Column(db.String(64), nullable=True)
    config_files = db.Column(db.JSON, nullable=True)
    file_denylist = db.Column(db.JSON, nullable=True)
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

    # ── Wings-Hilfsmethoden (M33) ──────────────────────

    def get_install_container(self) -> str:
        return self.install_container or DEFAULT_INSTALL_CONTAINER

    def get_install_entrypoint(self) -> str:
        return self.install_entrypoint or DEFAULT_INSTALL_ENTRYPOINT

    def get_startup_done_lines(self) -> list[str]:
        """Zeilen, bei denen Wings den Server als 'running' markiert."""
        cfg = self.config_startup or {}
        done = cfg.get("done") if isinstance(cfg, dict) else None
        if isinstance(done, str):
            return [done] if done else []
        if isinstance(done, list):
            return [str(d) for d in done if d]
        return []

    def get_startup_strip_ansi(self) -> bool:
        cfg = self.config_startup or {}
        return bool(cfg.get("strip_ansi", False)) if isinstance(cfg, dict) else False

    def get_stop_configuration(self) -> dict:
        """Wandelt config_stop in das Wings-Format {type, value} um.

        "stop"      -> {"type": "command", "value": "stop"}
        "^SIGTERM"  -> {"type": "signal",  "value": "SIGTERM"}
        """
        stop = (self.config_stop or DEFAULT_CONFIG_STOP).strip()
        if stop.startswith("^"):
            return {"type": "signal", "value": stop[1:].upper()}
        return {"type": "command", "value": stop}

    def get_file_denylist(self) -> list[str]:
        return [str(f) for f in (self.file_denylist or []) if f]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "docker_image": self.docker_image,
            "startup_command": self.startup_command,
            "install_script": self.install_script,
            "install_container": self.install_container,
            "install_entrypoint": self.install_entrypoint,
            "variables": self.variables or [],
            "config_schema": self.config_schema,
            "config_startup": self.config_startup,
            "config_stop": self.config_stop,
            "config_files": self.config_files,
            "file_denylist": self.file_denylist or [],
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self):
        return f"<Blueprint {self.name}>"
