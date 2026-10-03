"""Gemeinsame Helfer fuer die Testskripte (Wings Remote-API als Agent-Schnittstelle).

Ersetzt die frueheren Aufrufe der Legacy-Routen unter /api/agent (in M40 entfernt).
Alle Funktionen muessen innerhalb eines app_context() laufen.
"""

from app.extensions import db
from app.domain.agents.models import Agent
from app.domain.instances.models import Instance


def node_headers(agent: Agent) -> dict:
    """Bearer-Header eines Agents; erzeugt fehlende Credentials."""
    if not agent.has_daemon_credentials:
        agent.generate_daemon_credentials()
        db.session.commit()
    return {"Authorization": f"Bearer {agent.daemon_token_id}.{agent.daemon_token}"}


def node_headers_for_instance(uuid: str) -> dict:
    inst = Instance.query.filter_by(uuid=uuid).first()
    return node_headers(db.session.get(Agent, inst.agent_id))


def report_container_state(client, uuid: str, state):
    """Wie Wings: POST /api/remote/servers/{uuid}/container/status."""
    return client.post(
        f"/api/remote/servers/{uuid}/container/status",
        json={"data": {"new_state": state}},
        headers=node_headers_for_instance(uuid),
    )


def report_install(client, uuid: str, successful: bool):
    """Wie Wings: POST /api/remote/servers/{uuid}/install."""
    return client.post(
        f"/api/remote/servers/{uuid}/install",
        json={"successful": successful},
        headers=node_headers_for_instance(uuid),
    )
