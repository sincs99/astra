"""milestone29_suspension

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-03-16 14:00:00.000000

Fuegt hinzu:
- instances.suspended_reason (String(500), nullable)
- instances.suspended_at (DateTime, nullable)
- instances.suspended_by_user_id (Integer FK users.id, nullable)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    with op.batch_alter_table("instances", schema=None) as batch_op:
        if not _column_exists("instances", "suspended_reason"):
            batch_op.add_column(sa.Column("suspended_reason", sa.String(500), nullable=True))
        if not _column_exists("instances", "suspended_at"):
            batch_op.add_column(sa.Column("suspended_at", sa.DateTime(), nullable=True))
        if not _column_exists("instances", "suspended_by_user_id"):
            batch_op.add_column(
                sa.Column(
                    "suspended_by_user_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id"),
                    nullable=True,
                )
            )


def downgrade():
    with op.batch_alter_table("instances", schema=None) as batch_op:
        batch_op.drop_column("suspended_by_user_id")
        batch_op.drop_column("suspended_at")
        batch_op.drop_column("suspended_reason")
