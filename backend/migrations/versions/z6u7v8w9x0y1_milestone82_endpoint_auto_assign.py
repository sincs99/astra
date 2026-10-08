"""milestone82_endpoint_auto_assign

Revision ID: z6u7v8w9x0y1
Revises: y5t6u7v8w9x0
Create Date: 2026-10-08 15:00:00.000000

Fuegt hinzu (zweite Pilot-Liste):
- endpoints.auto_assign (Boolean, NOT NULL, Standard true): false nimmt einen Endpoint aus der automatischen Vergabe
  (z.B. den Query-Port eines Spiels), ohne ihn zu sperren; die explizite Zuweisung bleibt moeglich
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "z6u7v8w9x0y1"
down_revision = "y5t6u7v8w9x0"
branch_labels = None
depends_on = None


def _columns(table):
    return {c["name"] for c in sa_inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "auto_assign" not in _columns("endpoints"):
        with op.batch_alter_table("endpoints") as batch:
            batch.add_column(sa.Column("auto_assign", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    if "auto_assign" in _columns("endpoints"):
        with op.batch_alter_table("endpoints") as batch:
            batch.drop_column("auto_assign")
