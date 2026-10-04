"""milestone62_receipts

Revision ID: v2q3r4s5t6u7
Revises: u1p2q3r4s5t6
Create Date: 2026-10-04 20:00:00.000000

Fuegt hinzu:
- Tabelle invoice_counters (fortlaufende Zaehler der Belegnummern je Jahr)
- Tabelle receipts (Zahlungsbelege, eine Nummer pro verbuchter Zahlung)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "v2q3r4s5t6u7"
down_revision = "u1p2q3r4s5t6"
branch_labels = None
depends_on = None


def upgrade():
    tables = sa_inspect(op.get_bind()).get_table_names()
    if "invoice_counters" not in tables:
        op.create_table(
            "invoice_counters",
            sa.Column("scope", sa.String(16), primary_key=True),
            sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        )
    if "receipts" not in tables:
        op.create_table(
            "receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("number", sa.String(64), nullable=False, unique=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("payment_reference", sa.String(191), nullable=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.UniqueConstraint("order_id", "payment_reference", name="uq_receipts_order_payment"),
        )
        op.create_index("ix_receipts_order_id", "receipts", ["order_id"])


def downgrade():
    tables = sa_inspect(op.get_bind()).get_table_names()
    if "receipts" in tables:
        op.drop_table("receipts")
    if "invoice_counters" in tables:
        op.drop_table("invoice_counters")
