"""milestone53_system_state

Revision ID: r8m9n0o1p2q3
Revises: q7l8m9n0o1p2
Create Date: 2026-10-03 18:00:00.000000

Fuegt hinzu:
- Tabelle system_state (Schluessel-Wert-Speicher fuer Betriebszustand, z.B. letzter Lauf des Billing-Ticks)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "r8m9n0o1p2q3"
down_revision = "q7l8m9n0o1p2"
branch_labels = None
depends_on = None


def upgrade():
    if "system_state" not in sa_inspect(op.get_bind()).get_table_names():
        op.create_table(
            "system_state",
            sa.Column("key", sa.String(64), primary_key=True),
            sa.Column("value", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )


def downgrade():
    if "system_state" in sa_inspect(op.get_bind()).get_table_names():
        op.drop_table("system_state")
