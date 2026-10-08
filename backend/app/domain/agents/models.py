"""Agent-Domain-Modell mit Health-Tracking, Kapazitaet (M22), Maintenance (M25)
und Wings-Node-Credentials (M33)."""

import secrets
import string
import uuid as _uuid
from app.extensions import db
from datetime import datetime, timezone
from app.utils.timeutil import iso_utc

# Laengen wie im Referenz-Panel (Node::DAEMON_TOKEN_ID_LENGTH / DAEMON_TOKEN_LENGTH)
DAEMON_TOKEN_ID_LENGTH = 16
DAEMON_TOKEN_LENGTH = 64
_TOKEN_ALPHABET = string.ascii_letters + string.digits


def _random_string(length: int) -> str:
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(length))


class Agent(db.Model):
    __tablename__ = "agents"

    id = db.Column(db.Integer, primary_key=True)
    # M33: Node-UUID fuer die Wings config.yml
    uuid = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(_uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    fqdn = db.Column(db.String(255), unique=True, nullable=False)
    token_hash = db.Column(db.String(256), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Wings-Verbindung
    scheme = db.Column(db.String(8), default="https")
    behind_proxy = db.Column(db.Boolean, default=False)       # M33: TLS terminiert ein Proxy vor Wings
    daemon_connect = db.Column(db.Integer, default=8080)
    daemon_listen = db.Column(db.Integer, default=8080)
    daemon_sftp = db.Column(db.Integer, default=2022)          # M33: SFTP-Port von Wings
    daemon_base = db.Column(db.String(255), default="/var/lib/pterodactyl/volumes")  # M33: Daten-Verzeichnis
    upload_size = db.Column(db.Integer, default=256)           # M33: Upload-Limit in MB
    # Node-Credentials: Wings authentifiziert sich am Panel mit "Bearer {token_id}.{token}"
    daemon_token_id = db.Column(db.String(16), nullable=True)
    daemon_token = db.Column(db.String(256), nullable=True)

    # Health-Tracking (M20)
    last_seen_at = db.Column(db.DateTime, nullable=True)

    # Kapazitaet (M22) – Gesamtressourcen des Agents (physischer/virtueller Node)
    memory_total = db.Column(db.Integer, default=0)     # MB – Gesamt-RAM
    disk_total = db.Column(db.Integer, default=0)        # MB – Gesamt-Disk
    cpu_total = db.Column(db.Integer, default=0)         # % – Gesamt-CPU (z.B. 400 = 4 Kerne)
    memory_overalloc = db.Column(db.Integer, default=0)  # % – erlaubte Ueberallokation
    disk_overalloc = db.Column(db.Integer, default=0)    # % – erlaubte Ueberallokation
    cpu_overalloc = db.Column(db.Integer, default=0)     # % – erlaubte Ueberallokation

    # Maintenance (M25) – administrativer Betriebszustand
    maintenance_mode = db.Column(db.Boolean, default=False)
    maintenance_reason = db.Column(db.String(500), nullable=True)
    maintenance_started_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_connection_url(self) -> str:
        """Erzeugt die Basis-URL fuer Wings-Kommunikation."""
        scheme = self.scheme or "https"
        port = self.daemon_connect or 8080
        return f"{scheme}://{self.fqdn}:{port}"

    # ── Node-Credentials (M33) ──────────────────────────

    def generate_daemon_credentials(self) -> None:
        """Erzeugt neue Wings-Node-Credentials (token_id + token).

        Danach muss die config.yml auf dem Node neu ausgerollt werden,
        sonst kann sich Wings nicht mehr am Panel authentifizieren.
        """
        self.daemon_token_id = _random_string(DAEMON_TOKEN_ID_LENGTH)
        self.daemon_token = _random_string(DAEMON_TOKEN_LENGTH)

    @property
    def has_daemon_credentials(self) -> bool:
        return bool(self.daemon_token_id and self.daemon_token)

    @staticmethod
    def wings_docker_network() -> tuple[str, str]:
        """(Subnetz, Gateway) fuer das Docker-Netz von Wings (M78): WINGS_DOCKER_SUBNET, Gateway = erste Hostadresse."""
        import ipaddress
        from flask import current_app, has_app_context
        raw = (current_app.config.get("WINGS_DOCKER_SUBNET") if has_app_context() else None) or "172.30.0.0/16"
        try:
            net = ipaddress.IPv4Network(str(raw).strip(), strict=True)
        except ValueError:
            net = ipaddress.IPv4Network("172.30.0.0/16")
        return str(net), str(net.network_address + 1)

    def get_wings_configuration(self, remote_url: str) -> dict:
        """Erzeugt die Wings-Konfiguration (Inhalt von /etc/pterodactyl/config.yml).

        Format entspricht Node::getConfiguration() im Referenz-Panel.
        """
        fqdn = (self.fqdn or "").lower()
        scheme = self.scheme or "https"
        subnet, gateway = self.wings_docker_network()
        return {
            "debug": False,
            "uuid": self.uuid,
            "token_id": self.daemon_token_id,
            "token": self.daemon_token,
            "api": {
                "host": "0.0.0.0",
                "port": self.daemon_listen or 8080,
                "ssl": {
                    "enabled": (not self.behind_proxy) and scheme == "https",
                    "cert": f"/etc/letsencrypt/live/{fqdn}/fullchain.pem",
                    "key": f"/etc/letsencrypt/live/{fqdn}/privkey.pem",
                },
                "upload_limit": self.upload_size or 256,
            },
            "system": {
                "data": self.daemon_base or "/var/lib/pterodactyl/volumes",
                "sftp": {
                    "bind_port": self.daemon_sftp or 2022,
                },
            },
            # M78: eigenes Docker-Netz, damit Wings nicht mit dem Netz von docker compose (172.18.0.0/16) kollidiert
            "docker": {
                "network": {
                    "interface": gateway,
                    "interfaces": {"v4": {"subnet": subnet, "gateway": gateway}},
                },
            },
            "allowed_mounts": [],
            "remote": remote_url.rstrip("/"),
        }

    def get_wings_configuration_yaml(self, remote_url: str) -> str:
        import yaml
        return yaml.safe_dump(
            self.get_wings_configuration(remote_url),
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )

    def touch(self) -> None:
        """Aktualisiert last_seen_at auf jetzt."""
        self.last_seen_at = datetime.now(timezone.utc)

    def is_stale(self, max_minutes: int = 10) -> bool:
        """Prueft ob der Agent seit max_minutes nicht mehr gesehen wurde."""
        if not self.last_seen_at:
            return True
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        last = self.last_seen_at
        # SQLite gibt naive Datetimes zurueck – Kompatibilitaet
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return now - last > timedelta(minutes=max_minutes)

    # ── Kapazitaets-Hilfsmethoden (M22) ─────────────────

    def _effective_capacity(self, base: int, overalloc: int) -> int:
        """Berechnet die effektive Kapazitaet inkl. Ueberallokation.

        Formel: base * (1 + overalloc/100)
        Beispiel: 8192 MB RAM mit 20% Overalloc -> 9830 MB effektiv
        """
        if base <= 0:
            return 0
        return int(base * (1 + (overalloc or 0) / 100))

    def get_effective_memory(self) -> int:
        """Effektive Memory-Kapazitaet in MB (inkl. Overalloc)."""
        return self._effective_capacity(self.memory_total or 0, self.memory_overalloc or 0)

    def get_effective_disk(self) -> int:
        """Effektive Disk-Kapazitaet in MB (inkl. Overalloc)."""
        return self._effective_capacity(self.disk_total or 0, self.disk_overalloc or 0)

    def get_effective_cpu(self) -> int:
        """Effektive CPU-Kapazitaet in % (inkl. Overalloc)."""
        return self._effective_capacity(self.cpu_total or 0, self.cpu_overalloc or 0)

    def get_capacity_summary(self) -> dict:
        """Liefert eine Zusammenfassung der Agent-Kapazitaet.

        Enthaelt rohe Werte, Overalloc-Regeln und effektive Kapazitaeten.
        """
        return {
            "memory_total_mb": self.memory_total or 0,
            "disk_total_mb": self.disk_total or 0,
            "cpu_total_percent": self.cpu_total or 0,
            "memory_overalloc_percent": self.memory_overalloc or 0,
            "disk_overalloc_percent": self.disk_overalloc or 0,
            "cpu_overalloc_percent": self.cpu_overalloc or 0,
            "effective_memory_mb": self.get_effective_memory(),
            "effective_disk_mb": self.get_effective_disk(),
            "effective_cpu_percent": self.get_effective_cpu(),
        }

    def get_utilization_summary(self) -> dict:
        """Berechnet die Auslastung basierend auf zugewiesenen Instances.

        Nutzt die backref 'instances' (via Instance.agent relationship).
        """
        instances = getattr(self, "instances", []) or []
        used_memory = sum(getattr(i, "memory", 0) or 0 for i in instances)
        used_disk = sum(getattr(i, "disk", 0) or 0 for i in instances)
        used_cpu = sum(getattr(i, "cpu", 0) or 0 for i in instances)
        instance_count = len(instances)

        eff_mem = self.get_effective_memory()
        eff_disk = self.get_effective_disk()
        eff_cpu = self.get_effective_cpu()

        return {
            "instance_count": instance_count,
            "used_memory_mb": used_memory,
            "used_disk_mb": used_disk,
            "used_cpu_percent": used_cpu,
            "memory_utilization": round(used_memory / eff_mem * 100, 1) if eff_mem > 0 else 0.0,
            "disk_utilization": round(used_disk / eff_disk * 100, 1) if eff_disk > 0 else 0.0,
            "cpu_utilization": round(used_cpu / eff_cpu * 100, 1) if eff_cpu > 0 else 0.0,
        }

    def get_health_status(self, stale_threshold_minutes: int = 10) -> str:
        """Bestimmt den standardisierten Health-Status.

        Moegliche Werte:
        - 'healthy': Agent aktiv und kuerzlich gesehen
        - 'stale': Agent aktiv aber seit laengerem nicht gesehen
        - 'unreachable': Agent aktiv aber noch nie gesehen
        - 'degraded': Agent inaktiv oder deaktiviert
        """
        if not self.is_active:
            return "degraded"
        if not self.last_seen_at:
            return "unreachable"
        if self.is_stale(max_minutes=stale_threshold_minutes):
            return "stale"
        return "healthy"

    def get_health_summary(self, stale_threshold_minutes: int = 10) -> dict:
        """Liefert eine Zusammenfassung des Health-Status."""
        return {
            "health_status": self.get_health_status(stale_threshold_minutes),
            "is_active": self.is_active,
            "is_stale": self.is_stale(stale_threshold_minutes),
            "last_seen_at": iso_utc(self.last_seen_at),
        }

    # ── Maintenance-Hilfsmethoden (M25) ─────────────────

    @property
    def in_maintenance(self) -> bool:
        """Prueft ob der Agent im Maintenance-Modus ist."""
        return bool(self.maintenance_mode)

    def is_available_for_deployment(self) -> bool:
        """Prueft ob der Agent fuer neue Deployments verfuegbar ist."""
        return self.is_active and not self.in_maintenance

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "fqdn": self.fqdn,
            "is_active": self.is_active,
            "scheme": self.scheme,
            "behind_proxy": bool(self.behind_proxy),
            "daemon_connect": self.daemon_connect,
            "daemon_listen": self.daemon_listen,
            "daemon_sftp": self.daemon_sftp,
            "daemon_base": self.daemon_base,
            "upload_size": self.upload_size,
            "daemon_token_id": self.daemon_token_id,
            "has_daemon_credentials": self.has_daemon_credentials,
            # daemon_token bewusst NICHT in to_dict – Secret
            "last_seen_at": iso_utc(self.last_seen_at),
            "memory_total": self.memory_total or 0,
            "disk_total": self.disk_total or 0,
            "cpu_total": self.cpu_total or 0,
            "memory_overalloc": self.memory_overalloc or 0,
            "disk_overalloc": self.disk_overalloc or 0,
            "cpu_overalloc": self.cpu_overalloc or 0,
            "maintenance_mode": bool(self.maintenance_mode),
            "maintenance_reason": self.maintenance_reason,
            "maintenance_started_at": iso_utc(self.maintenance_started_at),
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }

    def __repr__(self):
        return f"<Agent {self.name}>"
