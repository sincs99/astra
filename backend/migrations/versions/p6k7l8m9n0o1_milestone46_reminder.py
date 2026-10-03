"""milestone46_reminder

Revision ID: p6k7l8m9n0o1
Revises: o5j6k7l8m9n0
Create Date: 2026-10-03 16:00:00.000000

Fuegt hinzu:
- orders.reminded_for_period_end (DateTime, nullable): Laufzeitende, fuer das die Erinnerung schon verschickt wurde
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "p6k7l8m9n0o1"
down_revision = "o5j6k7l8m9n0"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def upgrade():
    cols = [c["name"] for c in sa_inspect(op.get_bind()).get_columns("orders")]
    if "reminded_for_period_end" not in cols:
        with op.batch_alter_table("orders", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("reminded_for_period_end", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("orders", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("reminded_for_period_end")
