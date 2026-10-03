"""milestone33_wings_remote_api

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-10-03 12:00:00.000000

Fuegt hinzu (Wings Remote-API, M33):
- agents.uuid (String(36), unique, nullable) – Node-UUID fuer config.yml
- agents.behind_proxy (Boolean, default false)
- agents.daemon_sftp (Integer, default 2022)
- agents.daemon_base (String(255), default /var/lib/pterodactyl/volumes)
- agents.upload_size (Integer, default 256)
- blueprints.install_container (String(255), nullable)
- blueprints.install_entrypoint (String(64), nullable)
- blueprints.config_startup (JSON, nullable)
- blueprints.config_stop (String(64), nullable)
- blueprints.config_files (JSON, nullable)
- blueprints.file_denylist (JSON, nullable)

Bestehende Agents erhalten eine UUID (Backfill).
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    # Hinweis: Eindeutigkeit von agents.uuid ueber einen Unique-Index statt einer
    # Constraint im Batch-Modus. Auf SQLite wuerde create_unique_constraint die Tabelle
    # neu aufbauen und an den unbenannten Alt-Constraints (fqdn) scheitern
    # ("Constraint must have a name"); ADD COLUMN + CREATE UNIQUE INDEX laeuft ueberall.
    with op.batch_alter_table("agents", schema=None) as batch_op:
        if not _column_exists("agents", "uuid"):
            batch_op.add_column(sa.Column("uuid", sa.String(36), nullable=True))
        if not _column_exists("agents", "behind_proxy"):
            batch_op.add_column(sa.Column("behind_proxy", sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _column_exists("agents", "daemon_sftp"):
            batch_op.add_column(sa.Column("daemon_sftp", sa.Integer(), nullable=True, server_default="2022"))
        if not _column_exists("agents", "daemon_base"):
            batch_op.add_column(
                sa.Column("daemon_base", sa.String(255), nullable=True, server_default="/var/lib/pterodactyl/volumes")
            )
        if not _column_exists("agents", "upload_size"):
            batch_op.add_column(sa.Column("upload_size", sa.Integer(), nullable=True, server_default="256"))

    # Backfill: jeder bestehende Agent bekommt eine UUID
    bind = op.get_bind()
    agents = sa.table("agents", sa.column("id", sa.Integer), sa.column("uuid", sa.String))
    rows = bind.execute(sa.select(agents.c.id).where(agents.c.uuid.is_(None))).fetchall()
    for (agent_id,) in rows:
        bind.execute(agents.update().where(agents.c.id == agent_id).values(uuid=str(uuid.uuid4())))

    existing_indexes = {ix["name"] for ix in sa_inspect(bind).get_indexes("agents")}
    if "uq_agents_uuid" not in existing_indexes:
        op.create_index("uq_agents_uuid", "agents", ["uuid"], unique=True)

    with op.batch_alter_table("blueprints", schema=None) as batch_op:
        if not _column_exists("blueprints", "install_container"):
            batch_op.add_column(sa.Column("install_container", sa.String(255), nullable=True))
        if not _column_exists("blueprints", "install_entrypoint"):
            batch_op.add_column(sa.Column("install_entrypoint", sa.String(64), nullable=True))
        if not _column_exists("blueprints", "config_startup"):
            batch_op.add_column(sa.Column("config_startup", sa.JSON(), nullable=True))
        if not _column_exists("blueprints", "config_stop"):
            batch_op.add_column(sa.Column("config_stop", sa.String(64), nullable=True))
        if not _column_exists("blueprints", "config_files"):
            batch_op.add_column(sa.Column("config_files", sa.JSON(), nullable=True))
        if not _column_exists("blueprints", "file_denylist"):
            batch_op.add_column(sa.Column("file_denylist", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("blueprints", schema=None) as batch_op:
        batch_op.drop_column("file_denylist")
        batch_op.drop_column("config_files")
        batch_op.drop_column("config_stop")
        batch_op.drop_column("config_startup")
        batch_op.drop_column("install_entrypoint")
        batch_op.drop_column("install_container")

    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("upload_size")
        batch_op.drop_column("daemon_base")
        batch_op.drop_column("daemon_sftp")
        batch_op.drop_column("behind_proxy")
    op.drop_index("uq_agents_uuid", table_name="agents")
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("uuid")
