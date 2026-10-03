"""milestone48_payment_events

Revision ID: q7l8m9n0o1p2
Revises: p6k7l8m9n0o1
Create Date: 2026-10-03 17:00:00.000000

Fuegt hinzu:
- Tabelle payment_events (Ereignisse des Zahlungsanbieters: Idempotenz ueber die Event-ID)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "q7l8m9n0o1p2"
down_revision = "p6k7l8m9n0o1"
branch_labels = None
depends_on = None


def upgrade():
    if "payment_events" not in sa_inspect(op.get_bind()).get_table_names():
        op.create_table(
            "payment_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.String(255), nullable=False, unique=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("event_type", sa.String(120), nullable=True),
            sa.Column("order_uuid", sa.String(36), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="received"),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_payment_events_order_uuid", "payment_events", ["order_uuid"])


def downgrade():
    if "payment_events" in sa_inspect(op.get_bind()).get_table_names():
        op.drop_table("payment_events")
