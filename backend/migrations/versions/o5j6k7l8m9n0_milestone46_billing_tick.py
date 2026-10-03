"""milestone46_billing_tick

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-10-03 15:00:00.000000

Fuegt hinzu:
- orders.past_due_at (DateTime, nullable): Beginn der Karenzzeit
- orders.payment_references (JSON): verbuchte Zahlungsreferenzen (idempotente Verlaengerung)

Bestehende Bestellungen mit Zahlungsreferenz uebernehmen diese als erste Eintrag.
"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "o5j6k7l8m9n0"
down_revision = "n4i5j6k7l8m9"
branch_labels = None
depends_on = None

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _columns(table):
    return [c["name"] for c in sa_inspect(op.get_bind()).get_columns(table)]


def upgrade():
    cols = _columns("orders")
    with op.batch_alter_table("orders", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        if "past_due_at" not in cols:
            batch_op.add_column(sa.Column("past_due_at", sa.DateTime(), nullable=True))
        if "payment_references" not in cols:
            batch_op.add_column(sa.Column("payment_references", sa.JSON(), nullable=True))

    orders = sa.table(
        "orders",
        sa.column("id", sa.Integer),
        sa.column("payment_reference", sa.String),
        sa.column("payment_references", sa.JSON),
    )
    bind = op.get_bind()
    for oid, ref in bind.execute(sa.select(orders.c.id, orders.c.payment_reference)).fetchall():
        bind.execute(
            orders.update().where(orders.c.id == oid).values(payment_references=[ref] if ref else [])
        )


def downgrade():
    with op.batch_alter_table("orders", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("payment_references")
        batch_op.drop_column("past_due_at")
