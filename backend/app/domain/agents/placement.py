"""Kapazitaetspruefung und automatische Platzierung von Instanzen (M42).

Agents mit `memory_total`/`disk_total`/`cpu_total` = 0 gelten je Dimension als
"ohne Limit", damit bestehende Installationen nicht ploetzlich blockieren.
Belegt wird alles, was Instanzen des Agents zugewiesen haben (auch suspendierte).
"""

from __future__ import annotations

from sqlalchemy import func

from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.endpoints.models import Endpoint
from app.domain.instances.models import Instance


def used_resources(agent_id: int) -> dict:
    """Summe der zugewiesenen Ressourcen aller Instanzen auf dem Agent."""
    memory, disk, cpu, count = db.session.query(
        func.coalesce(func.sum(Instance.memory), 0),
        func.coalesce(func.sum(Instance.disk), 0),
        func.coalesce(func.sum(Instance.cpu), 0),
        func.count(Instance.id),
    ).filter(Instance.agent_id == agent_id).one()
    return {"memory": int(memory), "disk": int(disk), "cpu": int(cpu), "instances": int(count)}


def _limits(agent: Agent) -> dict:
    return {
        "memory": agent.get_effective_memory(),
        "disk": agent.get_effective_disk(),
        "cpu": agent.get_effective_cpu(),
    }


def capacity_problem(agent: Agent, memory: int, disk: int, cpu: int) -> str | None:
    """Fehlertext, wenn die Anfrage nicht mehr auf den Agent passt, sonst None."""
    used = used_resources(agent.id)
    want = {"memory": memory or 0, "disk": disk or 0, "cpu": cpu or 0}
    units = {"memory": "MB RAM", "disk": "MB Disk", "cpu": "% CPU"}
    for dim, limit in _limits(agent).items():
        if limit <= 0:
            continue  # ohne Limit
        if used[dim] + want[dim] > limit:
            free = max(limit - used[dim], 0)
            return (f"Agent '{agent.name}' hat nicht genug freie Kapazitaet: "
                    f"{want[dim]} {units[dim]} angefragt, {free} frei")
    return None


def has_free_endpoint(agent_id: int) -> bool:
    return db.session.query(Endpoint.id).filter_by(
        agent_id=agent_id, instance_id=None, is_locked=False
    ).first() is not None


def _load_after_placement(agent: Agent, used: dict, want: dict) -> float:
    """Hoechste Auslastung (0..1+) ueber alle begrenzten Dimensionen nach der Platzierung."""
    ratios = [
        (used[dim] + want[dim]) / limit
        for dim, limit in _limits(agent).items() if limit > 0
    ]
    return max(ratios) if ratios else 0.0


def pick_agent(memory: int, disk: int, cpu: int) -> Agent | None:
    """Waehlt den passenden Agent mit der geringsten Auslastung nach der Platzierung.

    Voraussetzungen: aktiv, nicht in Wartung, freier Endpoint, genug freie effektive Kapazitaet.
    Gleichstand: weniger Instanzen, dann kleinere ID.
    """
    want = {"memory": memory or 0, "disk": disk or 0, "cpu": cpu or 0}
    best = None
    best_key = None
    for agent in Agent.query.filter_by(is_active=True).order_by(Agent.id).all():
        if agent.in_maintenance or not has_free_endpoint(agent.id):
            continue
        if capacity_problem(agent, memory, disk, cpu):
            continue
        used = used_resources(agent.id)
        key = (_load_after_placement(agent, used, want), used["instances"], agent.id)
        if best_key is None or key < best_key:
            best, best_key = agent, key
    return best
