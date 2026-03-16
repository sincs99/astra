"""Service-Logik für Collaborators."""

from app.extensions import db
from app.domain.collaborators.models import Collaborator
from app.domain.collaborators.permissions import validate_permissions
from app.domain.instances.models import Instance
from app.domain.users.models import User


class CollaboratorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def list_collaborators(instance: Instance) -> list[Collaborator]:
    """Listet alle Collaborators einer Instance."""
    return (
        Collaborator.query.filter_by(instance_id=instance.id)
        .order_by(Collaborator.created_at.desc())
        .all()
    )


def add_collaborator(
    instance: Instance,
    user_id: int,
    permissions: list[str],
) -> Collaborator:
    """Fügt einen Collaborator hinzu."""

    # User prüfen
    user = db.session.get(User, user_id)
    if not user:
        raise CollaboratorError(f"User mit ID {user_id} nicht gefunden", 404)

    # Owner kann nicht Collaborator werden
    if instance.owner_id == user_id:
        raise CollaboratorError("Owner kann nicht als Collaborator hinzugefügt werden", 400)

    # Duplikat prüfen
    existing = Collaborator.query.filter_by(
        user_id=user_id, instance_id=instance.id
    ).first()
    if existing:
        raise CollaboratorError(
            f"User {user_id} ist bereits Collaborator dieser Instance", 409
        )

    # Permissions validieren
    ok, invalid = validate_permissions(permissions)
    if not ok:
        raise CollaboratorError(
            f"Ungültige Permissions: {', '.join(invalid)}", 400
        )

    collaborator = Collaborator(
        user_id=user_id,
        instance_id=instance.id,
        permissions=permissions,
    )
    db.session.add(collaborator)
    db.session.commit()
    return collaborator


def update_collaborator(
    collaborator: Collaborator,
    permissions: list[str],
) -> Collaborator:
    """Aktualisiert die Permissions eines Collaborators."""

    ok, invalid = validate_permissions(permissions)
    if not ok:
        raise CollaboratorError(
            f"Ungültige Permissions: {', '.join(invalid)}", 400
        )

    collaborator.permissions = permissions
    db.session.commit()
    return collaborator


def remove_collaborator(collaborator: Collaborator) -> None:
    """Entfernt einen Collaborator."""
    db.session.delete(collaborator)
    db.session.commit()
