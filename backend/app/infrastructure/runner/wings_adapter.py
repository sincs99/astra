"""WingsRunnerAdapter - Echte Wings-kompatible RunnerProtocol-Implementierung.

Sendet echte HTTP-Requests an einen Wings-Runner.
Implementiert:
- Instance-Lifecycle: create, sync, power, delete
- Dateisystem: list, read, write, delete, create_directory, rename
- Backups: noch Stubs
"""

from __future__ import annotations

import logging
import os
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
from app.infrastructure.runner.wings_http import WingsHttpClient

if TYPE_CHECKING:
    from app.domain.backups.models import Backup

logger = logging.getLogger(__name__)


class WingsRunnerAdapter(RunnerProtocol):
    """
    Echter Wings-Runner-Adapter.
    Kommuniziert ueber HTTP mit dem Wings-Daemon.
    """

    def __init__(self, timeout: tuple[int, int] = (5, 30), debug: bool = False):
        self._http = WingsHttpClient(timeout=timeout, debug=debug)

    # ── Instance-Lifecycle ──────────────────────────────

    def create_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        """Wings API: POST /api/servers"""
        logger.info("[Wings] create_instance: agent=%s, instance=%s", agent.name, instance.uuid)

        response = self._http.post(agent, "/api/servers", {
            "uuid": instance.uuid,
            "start_on_completion": True,
        })

        if response.success:
            return RunnerResponse(
                success=True,
                message=f"Wings: Instance '{instance.name}' erstellt",
                data=response.data,
            )
        else:
            return RunnerResponse(
                success=False,
                message=f"Wings: Fehler beim Erstellen - {response.error}",
                data=response.data,
            )

    def sync_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        """Wings API: POST /api/servers/{uuid}/sync"""
        logger.info("[Wings] sync_instance: agent=%s, instance=%s", agent.name, instance.uuid)

        response = self._http.post(agent, f"/api/servers/{instance.uuid}/sync")

        if response.success:
            return RunnerResponse(success=True, message=f"Wings: Instance '{instance.name}' synchronisiert")
        else:
            return RunnerResponse(success=False, message=f"Wings: Sync-Fehler - {response.error}")

    def send_power_action(self, agent: Agent, instance: Instance, action: PowerAction) -> RunnerResponse:
        """Wings API: POST /api/servers/{uuid}/power"""
        logger.info("[Wings] send_power_action: agent=%s, instance=%s, action=%s", agent.name, instance.uuid, action)

        response = self._http.post(agent, f"/api/servers/{instance.uuid}/power", {"action": action})

        if response.success:
            return RunnerResponse(success=True, message=f"Wings: Power-Aktion '{action}' gesendet")
        else:
            return RunnerResponse(success=False, message=f"Wings: Power-Aktion fehlgeschlagen - {response.error}")

    def delete_instance(self, agent: Agent, instance: Instance) -> RunnerResponse:
        """Wings API: DELETE /api/servers/{uuid}"""
        logger.info("[Wings] delete_instance: agent=%s, instance=%s", agent.name, instance.uuid)

        response = self._http.delete(agent, f"/api/servers/{instance.uuid}")

        if response.success:
            return RunnerResponse(success=True, message=f"Wings: Instance '{instance.name}' geloescht")
        else:
            return RunnerResponse(success=False, message=f"Wings: Loeschung fehlgeschlagen - {response.error}")

    def get_instance_resources(self, agent: Agent, instance: Instance) -> ResourceStats:
        """Echte Ressourcen-Abfrage via Wings API.

        Wings API: GET /api/servers/{uuid}/resources
        Response-Format (Wings/Pelican):
        {
            "current_state": "running",
            "is_suspended": false,
            "resources": {
                "memory_bytes": 123456789,
                "memory_limit_bytes": 536870912,
                "cpu_absolute": 45.23,
                "disk_bytes": 100000000,
                "network_rx_bytes": 1234567,
                "network_tx_bytes": 7654321,
                "uptime": 3600
            }
        }
        """
        logger.info("[Wings] get_instance_resources: instance=%s", instance.uuid)

        response = self._http.get(agent, f"/api/servers/{instance.uuid}/resources")

        if not response.success:
            logger.warning(
                "[Wings] get_instance_resources fehlgeschlagen: %s",
                response.error,
            )
            return ResourceStats(container_status="error")

        return _parse_wings_resources(response.data)

    # ── Dateisystem ─────────────────────────────────────

    def list_files(self, agent: Agent, instance: Instance, directory: str) -> FileListResult:
        """Verzeichnisinhalt auflisten.

        Wings API: GET /api/servers/{uuid}/files/list-directory?directory={path}

        Wings gibt ein Array von Objekten zurueck:
        [{"name": "...", "mode": "...", "mode_bits": "...",
          "size": 123, "is_file": true, "is_symlink": false,
          "mimetype": "...", "created_at": "...", "modified_at": "..."}]
        """
        logger.info("[Wings] list_files: instance=%s, dir=%s", instance.uuid, directory)

        response = self._http.get(
            agent,
            f"/api/servers/{instance.uuid}/files/list-directory",
            params={"directory": directory},
        )

        if not response.success:
            logger.warning("[Wings] list_files fehlgeschlagen: %s", response.error)
            return FileListResult(directory=directory, entries=[])

        # Wings-Response auf interne Typen mappen
        entries = _map_wings_file_list(response.data or [], directory)
        return FileListResult(directory=directory, entries=entries)

    def read_file(self, agent: Agent, instance: Instance, path: str) -> FileContentResult:
        """Dateiinhalt lesen.

        Wings API: GET /api/servers/{uuid}/files/contents?file={path}
        Response: Raw text (Content-Type: text/plain oder aehnlich)
        """
        logger.info("[Wings] read_file: instance=%s, path=%s", instance.uuid, path)

        response = self._http.get(
            agent,
            f"/api/servers/{instance.uuid}/files/contents",
            params={"file": path},
        )

        if not response.success:
            if response.status_code == 404:
                raise FileNotFoundError(f"Datei '{path}' nicht gefunden")
            raise RuntimeError(f"Wings read_file fehlgeschlagen: {response.error}")

        content = response.text or ""
        return FileContentResult(
            path=path,
            content=content,
            size=len(content.encode("utf-8")),
        )

    def write_file(self, agent: Agent, instance: Instance, path: str, content: str) -> RunnerResponse:
        """Datei schreiben/erstellen.

        Wings API: POST /api/servers/{uuid}/files/write?file={path}
        Body: Raw text content (Content-Type: text/plain)
        """
        logger.info("[Wings] write_file: instance=%s, path=%s, len=%d", instance.uuid, path, len(content))

        response = self._http.post_raw(
            agent,
            f"/api/servers/{instance.uuid}/files/write",
            raw_body=content,
            params={"file": path},
        )

        if response.success:
            return RunnerResponse(success=True, message=f"Datei '{path}' gespeichert")
        else:
            return RunnerResponse(success=False, message=f"Wings write_file: {response.error}")

    def delete_file(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        """Datei oder Verzeichnis loeschen.

        Wings API: POST /api/servers/{uuid}/files/delete
        Body: {"root": "/", "files": ["filename"]}
        """
        logger.info("[Wings] delete_file: instance=%s, path=%s", instance.uuid, path)

        # Wings erwartet root + Dateiname relativ zum root
        root, filename = _split_path(path)

        response = self._http.post(
            agent,
            f"/api/servers/{instance.uuid}/files/delete",
            {"root": root, "files": [filename]},
        )

        if response.success:
            return RunnerResponse(success=True, message=f"'{path}' geloescht")
        else:
            return RunnerResponse(success=False, message=f"Wings delete_file: {response.error}")

    def create_directory(self, agent: Agent, instance: Instance, path: str) -> RunnerResponse:
        """Verzeichnis erstellen.

        Wings API: POST /api/servers/{uuid}/files/create-directory
        Body: {"name": "dirname", "path": "/parent"}
        """
        logger.info("[Wings] create_directory: instance=%s, path=%s", instance.uuid, path)

        # Wings erwartet "name" (neuer Ordner) und "path" (Elternverzeichnis)
        parent, name = _split_path(path)

        response = self._http.post(
            agent,
            f"/api/servers/{instance.uuid}/files/create-directory",
            {"name": name, "path": parent},
        )

        if response.success:
            return RunnerResponse(success=True, message=f"Verzeichnis '{path}' erstellt")
        else:
            return RunnerResponse(success=False, message=f"Wings create_directory: {response.error}")

    def rename_file(self, agent: Agent, instance: Instance, source: str, target: str) -> RunnerResponse:
        """Datei/Verzeichnis umbenennen oder verschieben.

        Wings API: PUT /api/servers/{uuid}/files/rename
        Body: {"root": "/", "files": [{"from": "old", "to": "new"}]}
        """
        logger.info("[Wings] rename_file: instance=%s, %s -> %s", instance.uuid, source, target)

        # Wings erwartet root + relative Pfade
        source_root, source_name = _split_path(source)
        _, target_name = _split_path(target)

        response = self._http.put(
            agent,
            f"/api/servers/{instance.uuid}/files/rename",
            {
                "root": source_root,
                "files": [{"from": source_name, "to": target_name}],
            },
        )

        if response.success:
            return RunnerResponse(success=True, message=f"'{source}' umbenannt zu '{target}'")
        else:
            return RunnerResponse(success=False, message=f"Wings rename_file: {response.error}")

    # ── Backups ─────────────────────────────────────────

    def create_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        """Backup erstellen auf dem Wings-Runner.

        Wings API: POST /api/servers/{uuid}/backup
        Body: {"adapter": "wings", "uuid": "backup-uuid", "ignore": "file1\\nfile2"}
        """
        logger.info(
            "[Wings] create_backup: instance=%s, backup=%s",
            instance.uuid, backup.uuid,
        )

        # ignored_files: Text mit Zeilenumbruechen oder leer
        ignore_str = backup.ignored_files or ""

        response = self._http.post(
            agent,
            f"/api/servers/{instance.uuid}/backup",
            {
                "adapter": backup.disk or "wings",
                "uuid": backup.uuid,
                "ignore": ignore_str,
            },
        )

        if response.success:
            # Wings kann optionale Daten zurueckgeben (checksum, bytes)
            data = response.data or {}
            return RunnerResponse(
                success=True,
                message=f"Wings: Backup '{backup.name}' erstellt",
                data={
                    "checksum": data.get("checksum"),
                    "bytes": data.get("size", data.get("bytes", 0)),
                },
            )
        else:
            return RunnerResponse(
                success=False,
                message=f"Wings: Backup-Erstellung fehlgeschlagen - {response.error}",
            )

    def restore_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        """Backup wiederherstellen auf dem Wings-Runner.

        Wings API: POST /api/servers/{uuid}/backup/{backup_uuid}/restore
        Body: {"adapter": "wings", "truncate_directory": false, "download_url": ""}
        """
        logger.info(
            "[Wings] restore_backup: instance=%s, backup=%s",
            instance.uuid, backup.uuid,
        )

        response = self._http.post(
            agent,
            f"/api/servers/{instance.uuid}/backup/{backup.uuid}/restore",
            {
                "adapter": backup.disk or "wings",
                "truncate_directory": False,
                "download_url": "",
            },
        )

        if response.success:
            return RunnerResponse(
                success=True,
                message=f"Wings: Backup '{backup.name}' wiederhergestellt",
            )
        else:
            return RunnerResponse(
                success=False,
                message=f"Wings: Restore fehlgeschlagen - {response.error}",
            )

    def delete_backup(self, agent: Agent, instance: Instance, backup: Backup) -> RunnerResponse:
        """Backup loeschen vom Wings-Runner.

        Wings API: DELETE /api/servers/{uuid}/backup/{backup_uuid}
        """
        logger.info(
            "[Wings] delete_backup: instance=%s, backup=%s",
            instance.uuid, backup.uuid,
        )

        response = self._http.delete(
            agent,
            f"/api/servers/{instance.uuid}/backup/{backup.uuid}",
        )

        if response.success:
            return RunnerResponse(
                success=True,
                message=f"Wings: Backup '{backup.name}' geloescht",
            )
        else:
            return RunnerResponse(
                success=False,
                message=f"Wings: Backup-Loeschung fehlgeschlagen - {response.error}",
            )


# ── Hilfsfunktionen ─────────────────────────────────────


def _split_path(path: str) -> tuple[str, str]:
    """Teilt einen Pfad in (Elternverzeichnis, Name) auf.

    Beispiele:
        "/logs/latest.log" -> ("/logs", "latest.log")
        "/config"          -> ("/", "config")
        "/a/b/c"           -> ("/a/b", "c")
        "/"                -> ("/", "")
    """
    path = path.rstrip("/")
    if not path or path == "/":
        return ("/", "")

    parent = os.path.dirname(path)
    name = os.path.basename(path)

    if not parent:
        parent = "/"

    return (parent, name)


def _map_wings_file_list(wings_data: list | dict, directory: str) -> list[FileEntry]:
    """Mappt Wings-Dateiantworten auf interne FileEntry-Objekte.

    Wings gibt ein Array zurueck:
    [{"name": "file.txt", "size": 123, "is_file": true,
      "is_symlink": false, "modified_at": "...", "created_at": "...",
      "mode": "0644", "mode_bits": "-rw-r--r--", "mimetype": "text/plain"}]
    """
    # Wenn wings_data ein Dict mit "data" key ist
    if isinstance(wings_data, dict):
        wings_data = wings_data.get("data", [])

    entries: list[FileEntry] = []

    for item in wings_data:
        if not isinstance(item, dict):
            continue

        name = item.get("name", "")
        is_file = item.get("is_file", True)

        # Pfad zusammenbauen
        if directory == "/":
            full_path = f"/{name}"
        else:
            full_path = f"{directory.rstrip('/')}/{name}"

        entries.append(FileEntry(
            name=name,
            path=full_path,
            is_file=is_file,
            is_directory=not is_file,
            size=item.get("size", 0),
            modified_at=item.get("modified_at"),
        ))

    return entries


def _parse_wings_resources(data: dict | None) -> ResourceStats:
    """Parst die Wings-Resource-Response auf interne ResourceStats.

    Wings-Format (typisch):
    {
        "current_state": "running",
        "is_suspended": false,
        "resources": {
            "memory_bytes": 123456789,
            "memory_limit_bytes": 536870912,
            "cpu_absolute": 45.23,
            "disk_bytes": 100000000,
            "network_rx_bytes": 1234567,
            "network_tx_bytes": 7654321,
            "uptime": 3600
        }
    }

    Alternativ kann Wings die Ressourcen auch flach zurueckgeben.
    """
    if not data or not isinstance(data, dict):
        return ResourceStats(container_status="unknown")

    # Wings kann Resources genested oder flach liefern
    resources = data.get("resources", data)
    state = data.get("current_state", resources.get("state", "unknown"))

    try:
        cpu_abs = float(resources.get("cpu_absolute", 0.0))
        cpu_percent = round(cpu_abs, 2)
    except (TypeError, ValueError):
        cpu_percent = 0.0

    try:
        memory_bytes = int(resources.get("memory_bytes", 0))
    except (TypeError, ValueError):
        memory_bytes = 0

    try:
        memory_limit = int(resources.get("memory_limit_bytes", 0))
    except (TypeError, ValueError):
        memory_limit = 0

    try:
        disk_bytes = int(resources.get("disk_bytes", 0))
    except (TypeError, ValueError):
        disk_bytes = 0

    # Netzwerk: Wings kann rx/tx direkt oder in einem "network" Sub-Objekt liefern
    network = resources.get("network", {})
    try:
        rx = int(network.get("rx_bytes", 0) if isinstance(network, dict) else 0)
        if rx == 0:
            rx = int(resources.get("network_rx_bytes", 0))
    except (TypeError, ValueError):
        rx = 0

    try:
        tx = int(network.get("tx_bytes", 0) if isinstance(network, dict) else 0)
        if tx == 0:
            tx = int(resources.get("network_tx_bytes", 0))
    except (TypeError, ValueError):
        tx = 0

    try:
        uptime = int(resources.get("uptime", 0))
    except (TypeError, ValueError):
        uptime = 0

    return ResourceStats(
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
        memory_limit_bytes=memory_limit,
        disk_bytes=disk_bytes,
        network_rx_bytes=rx,
        network_tx_bytes=tx,
        uptime_seconds=uptime,
        container_status=str(state),
    )
