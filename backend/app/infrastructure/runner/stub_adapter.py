"""StubRunnerAdapter – Dummy-Implementierung für Entwicklung."""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.domain.agents.models import Agent
from app.domain.instances.models import Instance
from app.infrastructure.runner.protocol import (
    RunnerProtocol,
    RunnerResponse,
    ResourceStats,
    PowerAction,
    FileEntry,
    FileListResult,
    FileContentResult,
)

if TYPE_CHECKING:
    from app.domain.backups.models import Backup

logger = logging.getLogger(__name__)


# ── Virtuelles Dateisystem ──────────────────────────────

_STUB_FILES: dict[str, dict[str, str | int]] = {
    "/server.jar": {"content": "", "size": 45_000_000},
    "/eula.txt": {"content": "eula=true\n", "size": 10},
    "/logs/latest.log": {
        "content": (
            "[10:00:01] [Server thread/INFO]: Starting minecraft server version 1.20.4\n"
            "[10:00:02] [Server thread/INFO]: Loading properties\n"
            "[10:00:02] [Server thread/INFO]: Default game type: SURVIVAL\n"
            "[10:00:03] [Server thread/INFO]: Preparing level \"world\"\n"
            "[10:00:05] [Server thread/INFO]: Done (3.2s)! For help, type \"help\"\n"
        ),
        "size": 320,
    },
    "/config/server.properties": {
        "content": (
            "# Minecraft server properties\n"
            "server-port=25565\n"
            "gamemode=survival\n"
            "difficulty=normal\n"
            "max-players=20\n"
            "motd=Astra Managed Server\n"
            "view-distance=10\n"
            "online-mode=true\n"
            "enable-command-block=false\n"
        ),
        "size": 230,
    },
    "/config/ops.json": {"content": "[]", "size": 2},
    "/plugins/": {"content": "", "size": 0},
    "/world/level.dat": {"content": "", "size": 2048},
}

_DIRECTORIES = {"/", "/logs", "/config", "/plugins", "/world"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(path: str) -> str:
    """Normalisiert einen Pfad."""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") if path != "/" else path


class StubRunnerAdapter(RunnerProtocol):
    """
    Stub-Runner für lokale Entwicklung.
    Enthält ein kleines virtuelles Dateisystem pro Instance.
    """

    def __init__(self) -> None:
        # Kopie des Stub-FS pro Instance (uuid → files)
        self._filesystems: dict[str, dict[str, dict[str, str | int]]] = {}
        self._directories: dict[str, set[str]] = {}

    def _get_fs(self, instance: Instance) -> dict[str, dict[str, str | int]]:
        if instance.uuid not in self._filesystems:
            self._filesystems[instance.uuid] = dict(_STUB_FILES)
            self._directories[instance.uuid] = set(_DIRECTORIES)
        return self._filesystems[instance.uuid]

    def _get_dirs(self, instance: Instance) -> set[str]:
        self._get_fs(instance)  # Sicherstellen, dass initialisiert
        return self._directories[instance.uuid]

    # ── Instance-Lifecycle ──────────────────────────────

    def create_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        logger.info("[STUB] create_instance: agent=%s, instance=%s", agent.name, instance.uuid)
        return RunnerResponse(success=True, message=f"Stub: Instance '{instance.name}' provisioniert")

    def delete_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        logger.info("[STUB] delete_instance: agent=%s, instance=%s", agent.name, instance.uuid)
        self._filesystems.pop(instance.uuid, None)
        self._directories.pop(instance.uuid, None)
        return RunnerResponse(success=True, message=f"Stub: Instance '{instance.name}' gelöscht")

    def sync_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        logger.info("[STUB] sync_instance: agent=%s, instance=%s", agent.name, instance.uuid)
        return RunnerResponse(success=True, message=f"Stub: Instance '{instance.name}' synchronisiert")

    def send_power_action(self, agent: Agent, instance: Instance, action: PowerAction) -> RunnerResponse:
        logger.info("[STUB] send_power_action: agent=%s, instance=%s, action=%s", agent.name, instance.uuid, action)
        return RunnerResponse(success=True, message=f"Stub: Power-Aktion '{action}' gesendet")

    def get_instance_resources(self, agent: Agent, instance: Instance) -> ResourceStats:
        memory_limit = instance.memory * 1024 * 1024
        return ResourceStats(
            cpu_percent=round(random.uniform(1.0, 45.0), 1),
            memory_bytes=random.randint(int(memory_limit * 0.2), int(memory_limit * 0.8)),
            memory_limit_bytes=memory_limit,
            disk_bytes=random.randint(50_000_000, instance.disk * 1024 * 1024),
            network_rx_bytes=random.randint(1_000_000, 500_000_000),
            network_tx_bytes=random.randint(500_000, 100_000_000),
            uptime_seconds=random.randint(60, 86400),
            container_status="running",
        )

    # ── Dateisystem ─────────────────────────────────────

    def list_files(self, agent: Agent, instance: Instance, directory: str) -> FileListResult:
        logger.info("[STUB] list_files: instance=%s, dir=%s", instance.uuid, directory)
        fs = self._get_fs(instance)
        dirs = self._get_dirs(instance)
        directory = _normalize(directory)

        entries: list[FileEntry] = []

        # Unterverzeichnisse
        for d in sorted(dirs):
            if d == directory:
                continue
            parent = "/".join(d.rsplit("/", 1)[:-1]) or "/"
            if parent == directory:
                entries.append(FileEntry(
                    name=d.rsplit("/", 1)[-1],
                    path=d,
                    is_file=False,
                    is_directory=True,
                    size=0,
                    modified_at=_now_iso(),
                ))

        # Dateien
        prefix = directory if directory == "/" else directory + "/"
        for path, meta in sorted(fs.items()):
            if path.endswith("/"):
                continue
            file_dir = "/".join(path.rsplit("/", 1)[:-1]) or "/"
            if file_dir == directory:
                entries.append(FileEntry(
                    name=path.rsplit("/", 1)[-1],
                    path=path,
                    is_file=True,
                    is_directory=False,
                    size=int(meta.get("size", 0)),
                    modified_at=_now_iso(),
                ))

        return FileListResult(directory=directory, entries=entries)

    def read_file(self, agent: Agent, instance: Instance, path: str) -> FileContentResult:
        logger.info("[STUB] read_file: instance=%s, path=%s", instance.uuid, path)
        fs = self._get_fs(instance)
        path = _normalize(path)

        if path not in fs:
            raise FileNotFoundError(f"Datei '{path}' nicht gefunden")

        meta = fs[path]
        return FileContentResult(
            path=path,
            content=str(meta.get("content", "")),
            size=int(meta.get("size", 0)),
        )

    def write_file(self, agent: Agent, instance: Instance, path: str, content: str) -> RunnerResponse:
        logger.info("[STUB] write_file: instance=%s, path=%s, len=%d", instance.uuid, path, len(content))
        fs = self._get_fs(instance)
        path = _normalize(path)
        fs[path] = {"content": content, "size": len(content)}
        return RunnerResponse(success=True, message=f"Datei '{path}' gespeichert")

    def delete_file(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        logger.info("[STUB] delete_file: instance=%s, path=%s", instance.uuid, path)
        fs = self._get_fs(instance)
        dirs = self._get_dirs(instance)
        path = _normalize(path)

        if path in fs:
            del fs[path]
            return RunnerResponse(success=True, message=f"Datei '{path}' gelöscht")
        elif path in dirs:
            # Verzeichnis und Inhalte löschen
            to_remove = [k for k in fs if k.startswith(path + "/")]
            for k in to_remove:
                del fs[k]
            sub_dirs = [d for d in dirs if d.startswith(path + "/") or d == path]
            for d in sub_dirs:
                dirs.discard(d)
            return RunnerResponse(success=True, message=f"Verzeichnis '{path}' gelöscht")

        return RunnerResponse(success=False, message=f"Pfad '{path}' nicht gefunden")

    def create_directory(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        logger.info("[STUB] create_directory: instance=%s, path=%s", instance.uuid, path)
        dirs = self._get_dirs(instance)
        path = _normalize(path)

        if path in dirs:
            return RunnerResponse(success=False, message=f"Verzeichnis '{path}' existiert bereits")

        dirs.add(path)
        return RunnerResponse(success=True, message=f"Verzeichnis '{path}' erstellt")

    def rename_file(self, agent: Agent, instance: Instance, source: str, target: str) -> RunnerResponse:
        logger.info("[STUB] rename_file: instance=%s, %s → %s", instance.uuid, source, target)
        fs = self._get_fs(instance)
        dirs = self._get_dirs(instance)
        source = _normalize(source)
        target = _normalize(target)

        if source in fs:
            fs[target] = fs.pop(source)
            return RunnerResponse(success=True, message=f"'{source}' umbenannt zu '{target}'")
        elif source in dirs:
            dirs.discard(source)
            dirs.add(target)
            # Alle Dateien unter dem Verzeichnis umbenennen
            keys = [k for k in fs if k.startswith(source + "/")]
            for k in keys:
                new_k = target + k[len(source):]
                fs[new_k] = fs.pop(k)
            return RunnerResponse(success=True, message=f"'{source}' umbenannt zu '{target}'")

        return RunnerResponse(success=False, message=f"Pfad '{source}' nicht gefunden")

    def compress_files(self, agent: Agent, instance: Instance, files: list[str], destination: str) -> RunnerResponse:
        logger.info("[STUB] compress_files: instance=%s, files=%s → %s", instance.uuid, files, destination)
        fs = self._get_fs(instance)
        fs[destination] = {"content": "", "size": sum(int(fs.get(f, {}).get("size", 0)) for f in files)}
        return RunnerResponse(success=True, message=f"Stub: {len(files)} Datei(en) komprimiert → '{destination}'")

    def decompress_file(self, _agent: Agent, instance: Instance, file: str, destination: str) -> RunnerResponse:
        logger.info("[STUB] decompress_file: instance=%s, file=%s → %s", instance.uuid, file, destination)
        dirs = self._get_dirs(instance)
        dest = _normalize(destination)
        dirs.add(dest)
        return RunnerResponse(success=True, message=f"Stub: '{file}' entpackt nach '{destination}'")

    # ── Backups ─────────────────────────────────────────

    def create_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        logger.info("[STUB] create_backup: instance=%s, backup=%s", instance.uuid, backup.uuid)
        return RunnerResponse(
            success=True,
            message=f"Stub: Backup '{backup.name}' erstellt",
            data={
                "checksum": hashlib.sha256(backup.uuid.encode()).hexdigest()[:16],
                "bytes": random.randint(10_000_000, 500_000_000),
            },
        )

    def restore_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        logger.info("[STUB] restore_backup: instance=%s, backup=%s", instance.uuid, backup.uuid)
        return RunnerResponse(
            success=True,
            message=f"Stub: Backup '{backup.name}' wiederhergestellt",
        )

    def delete_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        logger.info("[STUB] delete_backup: instance=%s, backup=%s", instance.uuid, backup.uuid)
        return RunnerResponse(
            success=True,
            message=f"Stub: Backup '{backup.name}' gelöscht",
        )
