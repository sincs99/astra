"""milestone67_user_locale

Revision ID: w3r4s5t6u7v8
Revises: v2q3r4s5t6u7
Create Date: 2026-10-04 21:00:00.000000

Fuegt hinzu:
- users.locale (Sprache fuer Mails und Belege, NULL = Deutsch)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "w3r4s5t6u7v8"
down_revision = "v2q3r4s5t6u7"
branch_labels = None
depends_on = None


def _columns():
    return {c["name"] for c in sa_inspect(op.get_bind()).get_columns("users")}


def upgrade():
    if "locale" not in _columns():
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("locale", sa.String(5), nullable=True))


def downgrade():
    if "locale" in _columns():
        with op.batch_alter_table("users") as batch:
            batch.drop_column("locale")
