"""milestone61_revoked_tokens

Revision ID: u1p2q3r4s5t6
Revises: t0o1p2q3r4s5
Create Date: 2026-10-04 18:00:00.000000

Fuegt hinzu:
- Tabelle revoked_tokens (Logout-Blocklist: gesperrte Token-IDs bis zum Ablauf des Tokens)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "u1p2q3r4s5t6"
down_revision = "t0o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade():
    if "revoked_tokens" not in sa_inspect(op.get_bind()).get_table_names():
        op.create_table(
            "revoked_tokens",
            sa.Column("jti", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
        op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])


def downgrade():
    if "revoked_tokens" in sa_inspect(op.get_bind()).get_table_names():
        op.drop_table("revoked_tokens")
