"""Database-Provisioning-Adapter.

Kapselt die eigentliche Datenbank-Provisionierung.
Aktuell: StubAdapter (simuliert Erfolg).
Spaeter: MysqlAdapter fuer echte MySQL-Verbindungen.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DatabaseProvisioningAdapter(ABC):
    """Abstrakte Schnittstelle fuer DB-Provisioning."""

    @abstractmethod
    def create_database(self, provider, db_name: str, username: str,
                        password: str, remote_host: str) -> dict:
        ...

    @abstractmethod
    def change_password(self, provider, username: str, new_password: str) -> dict:
        ...

    @abstractmethod
    def drop_database(self, provider, db_name: str, username: str) -> dict:
        ...


class StubDatabaseAdapter(DatabaseProvisioningAdapter):
    """Stub-Adapter: Simuliert erfolgreiche DB-Provisioning-Operationen."""

    def create_database(self, provider, db_name: str, username: str,
                        password: str, remote_host: str) -> dict:
        logger.info("[DB-STUB] create_database: %s@%s on %s",
                    username, db_name, provider.host if provider else "?")
        return {"success": True, "message": f"Stub: Database '{db_name}' erstellt"}

    def change_password(self, provider, username: str, new_password: str) -> dict:
        logger.info("[DB-STUB] change_password: %s on %s",
                    username, provider.host if provider else "?")
        return {"success": True, "message": f"Stub: Passwort fuer '{username}' geaendert"}

    def drop_database(self, provider, db_name: str, username: str) -> dict:
        logger.info("[DB-STUB] drop_database: %s on %s",
                    db_name, provider.host if provider else "?")
        return {"success": True, "message": f"Stub: Database '{db_name}' geloescht"}


# ── Globaler Adapter ────────────────────────────────────

_adapter: DatabaseProvisioningAdapter | None = None


def set_db_adapter(adapter: DatabaseProvisioningAdapter) -> None:
    global _adapter
    _adapter = adapter


def get_db_adapter() -> DatabaseProvisioningAdapter:
    global _adapter
    if _adapter is None:
        _adapter = StubDatabaseAdapter()
    return _adapter
