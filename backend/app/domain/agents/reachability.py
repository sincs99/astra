"""Erreichbarkeits-Check Panel -> Wings (M41).

Fragt `GET /api/system` am Wings-Daemon ab (Bearer daemon_token, kurzer Timeout)
und cached das Ergebnis pro Agent kurz, damit Monitoring-Seiten nicht bei jedem
Aufruf alle Nodes anfunken. Mit dem Stub-Adapter gilt jeder Agent als erreichbar.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from flask import current_app

from app.domain.agents.models import Agent
from app.infrastructure.runner.wings_http import WingsHttpClient

CACHE_TTL_SECONDS = 30
TIMEOUT_SECONDS = 3
MAX_PARALLEL = 8

_cache: dict[tuple, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


class _AgentSnapshot:
    """Reine Wertkopie eines Agents, damit der HTTP-Call ohne DB-Session im Thread laufen kann."""

    def __init__(self, agent: Agent):
        self.id = agent.id
        self.name = agent.name
        self.daemon_token = agent.daemon_token
        self._url = agent.get_connection_url()

    def get_connection_url(self) -> str:
        return self._url


def _is_stub() -> bool:
    name = str(current_app.config.get("_RUNNER_ADAPTER_NAME")
               or current_app.config.get("RUNNER_ADAPTER", "stub")).lower()
    return name != "wings"


def _key(snap: _AgentSnapshot) -> tuple:
    # URL und Token im Schluessel: eine geaenderte Konfiguration entwertet den Cache sofort
    return (snap.id, snap._url, snap.daemon_token)


def _cached(snap: _AgentSnapshot) -> dict | None:
    with _cache_lock:
        hit = _cache.get(_key(snap))
    if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _probe(snap: _AgentSnapshot) -> dict:
    client = WingsHttpClient(timeout=(TIMEOUT_SECONDS, TIMEOUT_SECONDS))
    response = client.get(snap, "/api/system")
    if response.success:
        version = (response.data or {}).get("version")
        result = {"daemon_reachable": True, "daemon_version": version, "daemon_error": None}
    else:
        result = {"daemon_reachable": False, "daemon_version": None,
                  "daemon_error": response.error or f"HTTP {response.status_code}"}
    with _cache_lock:
        _cache[_key(snap)] = (time.monotonic(), result)
    return result


def check_daemon(agent: Agent, force: bool = False) -> dict:
    """{"daemon_reachable": bool, "daemon_version": str|None, "daemon_error": str|None}"""
    if _is_stub():
        return {"daemon_reachable": True, "daemon_version": "stub", "daemon_error": None}
    snap = _AgentSnapshot(agent)
    return (None if force else _cached(snap)) or _probe(snap)


def check_daemons(agents: list[Agent], force: bool = False) -> dict[int, dict]:
    """Prueft mehrere Agents parallel. Ergebnis: {agent_id: check_daemon-Ergebnis}."""
    if _is_stub():
        return {a.id: check_daemon(a) for a in agents}

    snaps = [_AgentSnapshot(a) for a in agents]
    results: dict[int, dict] = {}
    todo = []
    for snap in snaps:
        hit = None if force else _cached(snap)
        if hit is not None:
            results[snap.id] = hit
        else:
            todo.append(snap)
    if todo:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(todo))) as pool:
            for snap, res in zip(todo, pool.map(_probe, todo)):
                results[snap.id] = res
    return results


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
