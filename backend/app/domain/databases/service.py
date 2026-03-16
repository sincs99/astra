"""Service-Logik fuer Database-Provisioning."""

import logging
import re
import secrets

from app.extensions import db
from app.domain.databases.models import DatabaseProvider, Database
from app.domain.instances.models import Instance

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ── Provider CRUD ───────────────────────────────────────


def list_providers() -> list[DatabaseProvider]:
    return DatabaseProvider.query.order_by(DatabaseProvider.name).all()


def get_provider(provider_id: int) -> DatabaseProvider:
    provider = db.session.get(DatabaseProvider, provider_id)
    if not provider:
        raise DatabaseError(f"Provider mit ID {provider_id} nicht gefunden", 404)
    return provider


def create_provider(
    name: str,
    host: str,
    port: int = 3306,
    admin_user: str = "root",
    admin_password: str | None = None,
    max_databases: int | None = None,
) -> DatabaseProvider:
    if not name or not name.strip():
        raise DatabaseError("Field 'name' is required")
    if not host or not host.strip():
        raise DatabaseError("Field 'host' is required")
    if port < 1 or port > 65535:
        raise DatabaseError("Port must be between 1 and 65535")
    if max_databases is not None and max_databases < 0:
        raise DatabaseError("max_databases must be >= 0 or null")

    provider = DatabaseProvider(
        name=name.strip(),
        host=host.strip(),
        port=port,
        admin_user=admin_user,
        admin_password=admin_password,
        max_databases=max_databases,
    )
    db.session.add(provider)
    db.session.commit()
    logger.info("DatabaseProvider '%s' erstellt (Host: %s:%d)", name, host, port)
    return provider


def update_provider(provider_id: int, **changes) -> DatabaseProvider:
    provider = get_provider(provider_id)

    for key in ["name", "host", "port", "admin_user", "admin_password", "max_databases"]:
        if key in changes:
            value = changes[key]
            if key == "port" and value is not None:
                if value < 1 or value > 65535:
                    raise DatabaseError("Port must be between 1 and 65535")
            if key == "max_databases" and value is not None and value < 0:
                raise DatabaseError("max_databases must be >= 0 or null")
            setattr(provider, key, value)

    db.session.commit()
    return provider


def delete_provider(provider_id: int) -> None:
    provider = get_provider(provider_id)

    # Pruefen ob noch Databases auf diesem Provider existieren
    count = Database.query.filter_by(provider_id=provider_id).count()
    if count > 0:
        raise DatabaseError(
            f"Provider hat noch {count} Datenbank(en) – zuerst loeschen", 409
        )

    db.session.delete(provider)
    db.session.commit()
    logger.info("DatabaseProvider '%s' geloescht", provider.name)


# ── Database CRUD ───────────────────────────────────────


def list_databases(instance: Instance) -> list[Database]:
    return (
        Database.query.filter_by(instance_id=instance.id)
        .order_by(Database.created_at.desc())
        .all()
    )


def create_database(
    instance: Instance,
    provider_id: int,
    db_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
    remote_host: str = "%",
    max_connections: int | None = None,
) -> Database:
    """Erstellt eine neue Datenbank via Provisioning-Adapter."""
    provider = db.session.get(DatabaseProvider, provider_id)
    if not provider:
        raise DatabaseError(f"Provider mit ID {provider_id} nicht gefunden", 404)

    if not provider.has_capacity():
        raise DatabaseError(
            f"Provider '{provider.name}' hat max. Kapazitaet erreicht ({provider.max_databases})",
            409,
        )

    # db_name und username generieren falls nicht angegeben
    suffix = secrets.token_hex(4)
    if not db_name:
        safe_name = re.sub(r"[^a-zA-Z0-9]", "", instance.name[:16]).lower()
        db_name = f"astra_{safe_name}_{suffix}"
    if not username:
        username = f"u_{suffix}"
    if not password:
        password = Database.generate_password()

    # Validierung
    if len(db_name) > 64:
        raise DatabaseError("db_name darf maximal 64 Zeichen haben")
    if len(username) > 64:
        raise DatabaseError("username darf maximal 64 Zeichen haben")

    # Uniqueness pruefen
    existing = Database.query.filter_by(provider_id=provider_id, db_name=db_name).first()
    if existing:
        raise DatabaseError(f"db_name '{db_name}' existiert bereits auf diesem Provider", 409)

    existing_user = Database.query.filter_by(provider_id=provider_id, username=username).first()
    if existing_user:
        raise DatabaseError(f"username '{username}' existiert bereits auf diesem Provider", 409)

    # Provisioning-Adapter aufrufen
    from app.infrastructure.database.adapter import get_db_adapter
    adapter = get_db_adapter()
    result = adapter.create_database(provider, db_name, username, password, remote_host)

    if not result["success"]:
        raise DatabaseError(f"Provisioning fehlgeschlagen: {result.get('message', 'Unbekannt')}", 502)

    # DB-Record anlegen
    database = Database(
        instance_id=instance.id,
        provider_id=provider_id,
        db_name=db_name,
        username=username,
        password=password,
        remote_host=remote_host,
        max_connections=max_connections,
    )
    db.session.add(database)
    db.session.commit()

    logger.info("Database '%s' fuer Instance %s erstellt", db_name, instance.uuid)

    from app.domain.activity.events import log_instance_event
    log_instance_event(
        "database:created", instance.id,
        description=f"Datenbank '{db_name}' erstellt",
        properties={"db_name": db_name, "provider_id": provider_id},
    )

    return database


def rotate_password(instance: Instance, database: Database) -> Database:
    """Rotiert das Passwort einer Datenbank."""
    if database.instance_id != instance.id:
        raise DatabaseError("Datenbank gehoert nicht zu dieser Instance", 403)

    provider = db.session.get(DatabaseProvider, database.provider_id)
    if not provider:
        raise DatabaseError("Provider nicht gefunden", 500)

    new_password = Database.generate_password()

    # Provisioning-Adapter aufrufen
    from app.infrastructure.database.adapter import get_db_adapter
    adapter = get_db_adapter()
    result = adapter.change_password(provider, database.username, new_password)

    if not result["success"]:
        raise DatabaseError(f"Passwort-Rotation fehlgeschlagen: {result.get('message')}", 502)

    database.password = new_password
    db.session.commit()

    logger.info("Database '%s' Passwort rotiert", database.db_name)

    from app.domain.activity.events import log_instance_event
    log_instance_event(
        "database:password_rotated", instance.id,
        description=f"Passwort fuer Datenbank '{database.db_name}' rotiert",
        properties={"db_name": database.db_name},
    )

    return database


def delete_database(instance: Instance, database: Database) -> None:
    """Loescht eine Datenbank via Provisioning-Adapter."""
    if database.instance_id != instance.id:
        raise DatabaseError("Datenbank gehoert nicht zu dieser Instance", 403)

    provider = db.session.get(DatabaseProvider, database.provider_id)

    # Provisioning-Adapter aufrufen (best-effort)
    try:
        from app.infrastructure.database.adapter import get_db_adapter
        adapter = get_db_adapter()
        adapter.drop_database(provider, database.db_name, database.username)
    except Exception as e:
        logger.error("DB-Drop Fehler: %s (wird trotzdem aus Panel entfernt)", str(e))

    db_name = database.db_name
    db.session.delete(database)
    db.session.commit()

    logger.info("Database '%s' geloescht", db_name)

    from app.domain.activity.events import log_instance_event
    log_instance_event(
        "database:deleted", instance.id,
        description=f"Datenbank '{db_name}' geloescht",
        properties={"db_name": db_name},
    )
