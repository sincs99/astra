"""milestone59_refunds_disputes

Revision ID: s9n0o1p2q3r4
Revises: r8m9n0o1p2q3
Create Date: 2026-10-04 14:00:00.000000

Fuegt hinzu (Erstattungen und Zahlungsstreitigkeiten):
- orders.refunded_at (voll erstattet) und orders.disputed_at (Zahlungsstreit offen)
Der neue Status `refunded` braucht keine Migration (orders.status ist ein String).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "s9n0o1p2q3r4"
down_revision = "r8m9n0o1p2q3"
branch_labels = None
depends_on = None


def _columns():
    return {c["name"] for c in sa_inspect(op.get_bind()).get_columns("orders")}


def upgrade():
    cols = _columns()
    with op.batch_alter_table("orders") as batch:
        if "refunded_at" not in cols:
            batch.add_column(sa.Column("refunded_at", sa.DateTime(), nullable=True))
        if "disputed_at" not in cols:
            batch.add_column(sa.Column("disputed_at", sa.DateTime(), nullable=True))


def downgrade():
    cols = _columns()
    with op.batch_alter_table("orders") as batch:
        if "disputed_at" in cols:
            batch.drop_column("disputed_at")
        if "refunded_at" in cols:
            batch.drop_column("refunded_at")
