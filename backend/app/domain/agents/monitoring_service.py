"""Agent Fleet Monitoring Service (M22).

Zentraler Service fuer operative Uebersicht ueber alle Agents.
Berechnet Health-Status, Kapazitaet, Auslastung und Fleet-Aggregatwerte.

Design-Prinzipien:
- Nur lesende DB-Zugriffe, kein Polling
- DB-basierte Grundwerte + letzter bekannter Zustand
- Kein Activity-Logging fuer Monitoring-Abfragen
"""

from __future__ import annotations

from app.domain.agents.models import Agent
from app.domain.endpoints.models import Endpoint


# ── Konfigurierbare Schwellwerte ────────────────────────

DEFAULT_STALE_THRESHOLD_MINUTES = 10


# ── Agent-Monitoring-Eintrag ────────────────────────────


def get_agent_monitoring(agent: Agent, stale_threshold: int = DEFAULT_STALE_THRESHOLD_MINUTES) -> dict:
    """Erstellt einen vollstaendigen Monitoring-Eintrag fuer einen Agent.

    Enthaelt: Identifikation, Health, Kapazitaet, Auslastung, Endpoints.
    """
    health = agent.get_health_summary(stale_threshold)
    capacity = agent.get_capacity_summary()
    utilization = agent.get_utilization_summary()
    endpoint_summary = _get_endpoint_summary(agent)

    return {
        # Identifikation
        "id": agent.id,
        "name": agent.name,
        "fqdn": agent.fqdn,

        # Health
        "health_status": health["health_status"],
        "is_active": health["is_active"],
        "is_stale": health["is_stale"],
        "last_seen_at": health["last_seen_at"],

        # Maintenance (M25)
        "maintenance_mode": bool(agent.maintenance_mode),
        "maintenance_reason": agent.maintenance_reason,
        "maintenance_started_at": agent.maintenance_started_at.isoformat() if agent.maintenance_started_at else None,
        "available_for_deployment": agent.is_available_for_deployment(),

        # Kapazitaet
        "capacity": capacity,

        # Auslastung
        "utilization": utilization,
        "instance_count": utilization["instance_count"],

        # Endpoints
        "endpoint_summary": endpoint_summary,
    }


def _get_endpoint_summary(agent: Agent) -> dict:
    """Berechnet eine Zusammenfassung der Endpoints eines Agents."""
    endpoints = getattr(agent, "endpoints", []) or []
    total = len(endpoints)
    assigned = sum(1 for ep in endpoints if ep.instance_id is not None)
    locked = sum(1 for ep in endpoints if ep.is_locked)
    free = total - assigned - locked

    return {
        "total": total,
        "assigned": assigned,
        "free": max(free, 0),
        "locked": locked,
    }


# ── Alle Agents laden ──────────────────────────────────


def get_all_agents_monitoring(
    stale_threshold: int = DEFAULT_STALE_THRESHOLD_MINUTES,
    health_filter: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Laedt alle Agents mit Monitoring-Daten.

    Args:
        stale_threshold: Schwellwert in Minuten fuer stale-Erkennung
        health_filter: Optional – nur Agents mit diesem Health-Status ('healthy', 'stale', 'degraded', 'unreachable')
        search: Optional – Textsuche in Name oder FQDN
    """
    query = Agent.query.order_by(Agent.name)

    # Textsuche
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Agent.name.ilike(pattern) | Agent.fqdn.ilike(pattern)
        )

    agents = query.all()
    result = []

    for agent in agents:
        entry = get_agent_monitoring(agent, stale_threshold)

        # Health-Filter anwenden (nach Berechnung, da abgeleiteter Wert)
        if health_filter and entry["health_status"] != health_filter:
            continue

        result.append(entry)

    return result


def get_single_agent_monitoring(
    agent_id: int,
    stale_threshold: int = DEFAULT_STALE_THRESHOLD_MINUTES,
) -> dict | None:
    """Laedt Monitoring-Daten fuer einen einzelnen Agent.

    Returns None wenn Agent nicht gefunden.
    """
    from app.extensions import db
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return None
    return get_agent_monitoring(agent, stale_threshold)


# ── Fleet Summary (Aggregat) ───────────────────────────


def get_fleet_summary(stale_threshold: int = DEFAULT_STALE_THRESHOLD_MINUTES) -> dict:
    """Berechnet globale Kennzahlen ueber alle Agents.

    Liefert:
    - Anzahl Agents nach Status
    - Gesamt-Kapazitaet und -Auslastung
    - Gesamt-Instances
    - Endpoint-Uebersicht
    """
    agents = Agent.query.all()

    total_agents = len(agents)
    healthy_count = 0
    stale_count = 0
    degraded_count = 0
    unreachable_count = 0
    maintenance_count = 0

    total_instances = 0
    total_memory = 0
    used_memory = 0
    total_disk = 0
    used_disk = 0
    total_cpu = 0
    used_cpu = 0

    total_endpoints = 0
    assigned_endpoints = 0

    for agent in agents:
        # Health zaehlen
        status = agent.get_health_status(stale_threshold)
        if status == "healthy":
            healthy_count += 1
        elif status == "stale":
            stale_count += 1
        elif status == "degraded":
            degraded_count += 1
        elif status == "unreachable":
            unreachable_count += 1

        # Maintenance zaehlen (M25)
        if agent.in_maintenance:
            maintenance_count += 1

        # Kapazitaet aggregieren
        total_memory += agent.get_effective_memory()
        total_disk += agent.get_effective_disk()
        total_cpu += agent.get_effective_cpu()

        # Auslastung aggregieren
        util = agent.get_utilization_summary()
        total_instances += util["instance_count"]
        used_memory += util["used_memory_mb"]
        used_disk += util["used_disk_mb"]
        used_cpu += util["used_cpu_percent"]

        # Endpoints aggregieren
        endpoints = getattr(agent, "endpoints", []) or []
        total_endpoints += len(endpoints)
        assigned_endpoints += sum(1 for ep in endpoints if ep.instance_id is not None)

    return {
        "total_agents": total_agents,
        "healthy_agents": healthy_count,
        "stale_agents": stale_count,
        "degraded_agents": degraded_count,
        "unreachable_agents": unreachable_count,
        "total_instances": total_instances,
        "total_memory_mb": total_memory,
        "used_memory_mb": used_memory,
        "memory_utilization": round(used_memory / total_memory * 100, 1) if total_memory > 0 else 0.0,
        "total_disk_mb": total_disk,
        "used_disk_mb": used_disk,
        "disk_utilization": round(used_disk / total_disk * 100, 1) if total_disk > 0 else 0.0,
        "total_cpu_percent": total_cpu,
        "used_cpu_percent": used_cpu,
        "cpu_utilization": round(used_cpu / total_cpu * 100, 1) if total_cpu > 0 else 0.0,
        "total_endpoints": total_endpoints,
        "assigned_endpoints": assigned_endpoints,
        "maintenance_agents": maintenance_count,
    }
