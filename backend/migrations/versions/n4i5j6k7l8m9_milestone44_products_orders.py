"""milestone44_products_orders

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-10-03 14:00:00.000000

Fuegt hinzu:
- Tabelle products (Pakete: Blueprint, Ressourcen, Preis, Laufzeit)
- Tabelle orders (Bestellungen mit Preis-/Ressourcen-Schnappschuss)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "n4i5j6k7l8m9"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def _table_exists(name):
    return name in sa_inspect(op.get_bind()).get_table_names()


def upgrade():
    if not _table_exists("products"):
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("blueprints.id"), nullable=False),
            sa.Column("memory", sa.Integer(), nullable=False),
            sa.Column("swap", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("disk", sa.Integer(), nullable=False),
            sa.Column("io", sa.Integer(), nullable=False, server_default="500"),
            sa.Column("cpu", sa.Integer(), nullable=False),
            sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
            sa.Column("billing_period_days", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("max_instances_per_user", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", sa.String(36), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("instance_id", sa.Integer(), sa.ForeignKey("instances.id"), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending_payment"),
            sa.Column("instance_name", sa.String(120), nullable=False),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("billing_period_days", sa.Integer(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("payment_reference", sa.String(191), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_orders_user_id", "orders", ["user_id"])
        op.create_index("ix_orders_product_id", "orders", ["product_id"])
        op.create_index("ix_orders_status", "orders", ["status"])


def downgrade():
    if _table_exists("orders"):
        op.drop_table("orders")  # entfernt auch die Indizes
    if _table_exists("products"):
        op.drop_table("products")
