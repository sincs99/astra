"""Zentrale Berechtigungslogik für Instance-Zugriff."""

from typing import Literal
from app.domain.instances.models import Instance
from app.domain.collaborators.models import Collaborator


Role = Literal["owner", "collaborator", "none"]


def get_instance_role(user_id: int, instance: Instance) -> Role:
    """Bestimmt die Rolle eines Users für eine Instance."""
    if instance.owner_id == user_id:
        return "owner"

    collab = Collaborator.query.filter_by(
        user_id=user_id, instance_id=instance.id
    ).first()
    if collab:
        return "collaborator"

    return "none"


def can_access_instance(
    user_id: int, instance: Instance, permission: str | None = None
) -> bool:
    """
    Prüft ob ein User auf eine Instance zugreifen darf.

    - Owner hat immer vollen Zugriff
    - Collaborator braucht die spezifische Permission
    - Ohne Permission-Angabe: prüft nur ob Zugriff besteht
    """
    if instance.owner_id == user_id:
        return True

    collab = Collaborator.query.filter_by(
        user_id=user_id, instance_id=instance.id
    ).first()

    if not collab:
        return False

    # Ohne Permission-Anforderung: Zugriff ja/nein
    if permission is None:
        return True

    # Permission in der Liste des Collaborators?
    return permission in (collab.permissions or [])


def get_user_instance(uuid: str, user_id: int) -> Instance | None:
    """
    Holt eine Instance, auf die der User Zugriff hat (Owner oder Collaborator).
    Ersetzt die bisherige _get_user_instance-Funktion.
    """
    # Erst als Owner suchen
    instance = Instance.query.filter_by(uuid=uuid, owner_id=user_id).first()
    if instance:
        return instance

    # Dann als Collaborator suchen
    instance = Instance.query.filter_by(uuid=uuid).first()
    if not instance:
        return None

    collab = Collaborator.query.filter_by(
        user_id=user_id, instance_id=instance.id
    ).first()
    if collab:
        return instance

    return None
