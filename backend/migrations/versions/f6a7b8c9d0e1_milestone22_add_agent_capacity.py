"""milestone22_add_agent_capacity

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-14 07:35:00.000000

Fuegt Kapazitaetsfelder zum Agent-Modell hinzu fuer M22 Fleet Monitoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    cols = [
        ("memory_total", sa.Integer(), "0"),
        ("disk_total", sa.Integer(), "0"),
        ("cpu_total", sa.Integer(), "0"),
        ("memory_overalloc", sa.Integer(), "0"),
        ("disk_overalloc", sa.Integer(), "0"),
        ("cpu_overalloc", sa.Integer(), "0"),
    ]
    with op.batch_alter_table("agents", schema=None) as batch_op:
        for col_name, col_type, default in cols:
            if not _column_exists("agents", col_name):
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True, server_default=default))


def downgrade():
    with op.batch_alter_table("agents", schema=None) as batch_op:
        batch_op.drop_column("cpu_overalloc")
        batch_op.drop_column("disk_overalloc")
        batch_op.drop_column("memory_overalloc")
        batch_op.drop_column("cpu_total")
        batch_op.drop_column("disk_total")
        batch_op.drop_column("memory_total")
