"""milestone28_ssh_keys

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-03-16 12:00:00.000000

Fuegt hinzu:
- Tabelle user_ssh_keys (M28: SSH Keys & SFTP Access Management)
"""
from alembic import op
import sqlalchemy as sa

revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_ssh_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(191), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fingerprint", name="uq_user_ssh_key_fingerprint"),
    )
    op.create_index("ix_user_ssh_keys_user_id", "user_ssh_keys", ["user_id"])


def downgrade():
    op.drop_index("ix_user_ssh_keys_user_id", table_name="user_ssh_keys")
    op.drop_table("user_ssh_keys")
