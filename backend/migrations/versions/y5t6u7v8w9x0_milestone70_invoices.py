"""milestone70_invoices

Revision ID: y5t6u7v8w9x0
Revises: x4s5t6u7v8w9
Create Date: 2026-10-04 23:00:00.000000

Fuegt hinzu (Rechnungen mit Umsatzsteuer):
- users.billing_name, users.billing_address (Rechnungsempfaenger, optional)
- receipts.kind ("invoice" | "credit_note", vorhandene Belege = invoice) und receipts.references_id (Gutschrift -> Rechnung)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "y5t6u7v8w9x0"
down_revision = "x4s5t6u7v8w9"
branch_labels = None
depends_on = None


def _columns(table):
    return {c["name"] for c in sa_inspect(op.get_bind()).get_columns(table)}


def upgrade():
    users = _columns("users")
    with op.batch_alter_table("users") as batch:
        if "billing_name" not in users:
            batch.add_column(sa.Column("billing_name", sa.String(200), nullable=True))
        if "billing_address" not in users:
            batch.add_column(sa.Column("billing_address", sa.Text(), nullable=True))
    receipts = _columns("receipts")
    with op.batch_alter_table("receipts") as batch:
        if "kind" not in receipts:
            batch.add_column(sa.Column("kind", sa.String(16), nullable=False, server_default="invoice"))
        if "references_id" not in receipts:
            batch.add_column(sa.Column("references_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_receipts_references", "receipts", ["references_id"], ["id"])


def downgrade():
    receipts = _columns("receipts")
    # Der Fremdschluessel heisst je nach Herkunft der Datenbank anders (Migration: fk_receipts_references, create_all: ohne Namen)
    named_fks = [fk["name"] for fk in sa_inspect(op.get_bind()).get_foreign_keys("receipts")
                 if fk.get("constrained_columns") == ["references_id"] and fk.get("name")]
    with op.batch_alter_table("receipts") as batch:
        if "references_id" in receipts:
            for name in named_fks:
                batch.drop_constraint(name, type_="foreignkey")
            batch.drop_column("references_id")
        if "kind" in receipts:
            batch.drop_column("kind")
    users = _columns("users")
    with op.batch_alter_table("users") as batch:
        if "billing_address" in users:
            batch.drop_column("billing_address")
        if "billing_name" in users:
            batch.drop_column("billing_name")
