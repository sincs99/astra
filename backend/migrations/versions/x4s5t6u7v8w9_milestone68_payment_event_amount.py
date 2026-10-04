"""milestone68_payment_event_amount

Revision ID: x4s5t6u7v8w9
Revises: w3r4s5t6u7v8
Create Date: 2026-10-04 22:00:00.000000

Fuegt hinzu:
- payment_events.amount_cents und payment_events.currency (Betrag des Anbieter-Ereignisses, NULL bei Altbestand)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "x4s5t6u7v8w9"
down_revision = "w3r4s5t6u7v8"
branch_labels = None
depends_on = None


def _columns():
    return {c["name"] for c in sa_inspect(op.get_bind()).get_columns("payment_events")}


def upgrade():
    cols = _columns()
    with op.batch_alter_table("payment_events") as batch:
        if "amount_cents" not in cols:
            batch.add_column(sa.Column("amount_cents", sa.Integer(), nullable=True))
        if "currency" not in cols:
            batch.add_column(sa.Column("currency", sa.String(3), nullable=True))


def downgrade():
    cols = _columns()
    with op.batch_alter_table("payment_events") as batch:
        if "currency" in cols:
            batch.drop_column("currency")
        if "amount_cents" in cols:
            batch.drop_column("amount_cents")
