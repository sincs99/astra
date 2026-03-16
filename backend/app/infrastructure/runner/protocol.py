"""RunnerProtocol – Abstrakte Schnittstelle für Agent-Kommunikation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

from app.domain.agents.models import Agent
from app.domain.instances.models import Instance

if TYPE_CHECKING:
    from app.domain.backups.models import Backup


PowerAction = Literal["start", "stop", "restart", "kill"]


# ── Response-Typen ──────────────────────────────────────


@dataclass
class RunnerResponse:
    """Standard-Antwort eines Runner-Aufrufs."""
    success: bool
    message: str
    data: dict | None = None


@dataclass
class ResourceStats:
    """Ressourcenverbrauch einer Instance."""
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    memory_limit_bytes: int = 0
    disk_bytes: int = 0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    uptime_seconds: int = 0
    container_status: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_bytes": self.memory_bytes,
            "memory_limit_bytes": self.memory_limit_bytes,
            "disk_bytes": self.disk_bytes,
            "network_rx_bytes": self.network_rx_bytes,
            "network_tx_bytes": self.network_tx_bytes,
            "uptime_seconds": self.uptime_seconds,
            "container_status": self.container_status,
        }


# ── File-Typen ──────────────────────────────────────────


@dataclass
class FileEntry:
    """Ein Dateisystem-Eintrag."""
    name: str
    path: str
    is_file: bool
    is_directory: bool
    size: int = 0
    modified_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "is_file": self.is_file,
            "is_directory": self.is_directory,
            "size": self.size,
            "modified_at": self.modified_at,
        }


@dataclass
class FileListResult:
    """Ergebnis einer Verzeichnisauflistung."""
    directory: str
    entries: list[FileEntry]

    def to_dict(self) -> dict:
        return {
            "directory": self.directory,
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class FileContentResult:
    """Ergebnis eines Dateilesevorgangs."""
    path: str
    content: str
    size: int

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "content": self.content,
            "size": self.size,
        }


# ── Protocol ────────────────────────────────────────────


class RunnerProtocol(ABC):
    """
    Port-Schnittstelle für die Kommunikation mit Agents/Runnern.
    Jede konkrete Implementierung muss diese Methoden bereitstellen.
    """

    # ── Instance-Lifecycle ──────────────────────────────

    @abstractmethod
    def create_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        ...

    @abstractmethod
    def delete_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        ...

    @abstractmethod
    def sync_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        ...

    @abstractmethod
    def send_power_action(self, agent: Agent, instance: Instance, action: PowerAction) -> RunnerResponse:
        ...

    @abstractmethod
    def get_instance_resources(self, agent: Agent, instance: Instance) -> ResourceStats:
        ...

    # ── Dateisystem ─────────────────────────────────────

    @abstractmethod
    def list_files(self, agent: Agent, instance: Instance, directory: str) -> FileListResult:
        ...

    @abstractmethod
    def read_file(self, agent: Agent, instance: Instance, path: str) -> FileContentResult:
        ...

    @abstractmethod
    def write_file(self, agent: Agent, instance: Instance, path: str, content: str) -> RunnerResponse:
        ...

    @abstractmethod
    def delete_file(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        ...

    @abstractmethod
    def create_directory(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        ...

    @abstractmethod
    def rename_file(self, agent: Agent, instance: Instance, source: str, target: str) -> RunnerResponse:
        ...

    @abstractmethod
    def compress_files(self, agent: Agent, instance: Instance, files: list[str], destination: str) -> RunnerResponse:
        ...

    @abstractmethod
    def decompress_file(self, agent: Agent, instance: Instance, file: str, destination: str) -> RunnerResponse:
        ...

    # ── Backups ─────────────────────────────────────────

    @abstractmethod
    def create_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        ...

    @abstractmethod
    def restore_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        ...

    @abstractmethod
    def delete_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        ...
