"""milestone25_add_agent_maintenance

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-14 11:39:00.000000

Fuegt Maintenance-Felder zum Agent-Modell hinzu (M25).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "h8c9d0e1f2g3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    with op.batch_alter_table("agents", schema=None) as batch_op:
        if not _column_exists("agents", "maintenance_mode"):
            batch_op.add_column(sa.Column("maintenance_mode", sa.Boolean(), nullable=True, server_default="0"))
        if not _column_exists("agents", "maintenance_reason"):
            batch_op.add_column(sa.Column("maintenance_reason", sa.String(500), nullable=True))
        if not _column_exists("agents", "maintenance_started_at"):
            batch_op.add_column(sa.Column("maintenance_started_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("maintenance_started_at")
        batch_op.drop_column("maintenance_reason")
        batch_op.drop_column("maintenance_mode")
