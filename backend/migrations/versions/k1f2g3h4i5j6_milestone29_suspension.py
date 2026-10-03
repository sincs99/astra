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
    # Spalten per ALTER TABLE ADD COLUMN (kein Batch-Neuaufbau: der scheitert auf SQLite an
    # den unbenannten Alt-Constraints mit "Constraint must have a name").
    # SQLite kann per ALTER keine FK-Constraints anlegen -> dort nur die Integer-Spalte.
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not _column_exists("instances", "suspended_reason"):
        op.add_column("instances", sa.Column("suspended_reason", sa.String(500), nullable=True))
    if not _column_exists("instances", "suspended_at"):
        op.add_column("instances", sa.Column("suspended_at", sa.DateTime(), nullable=True))
    if not _column_exists("instances", "suspended_by_user_id"):
        if is_sqlite:
            op.add_column("instances", sa.Column("suspended_by_user_id", sa.Integer(), nullable=True))
        else:
            op.add_column(
                "instances",
                sa.Column(
                    "suspended_by_user_id",
                    sa.Integer(),
                    sa.ForeignKey("users.id", name="fk_instances_suspended_by_user_id_users"),
                    nullable=True,
                ),
            )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_instances_suspended_by_user_id_users", "instances", type_="foreignkey")
    op.drop_column("instances", "suspended_by_user_id")
    op.drop_column("instances", "suspended_at")
    op.drop_column("instances", "suspended_reason")
