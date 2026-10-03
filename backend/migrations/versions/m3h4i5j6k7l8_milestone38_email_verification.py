"""milestone38_email_verification

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-10-03 13:00:00.000000

Fuegt hinzu:
- users.email_verified_at (DateTime, nullable)

Bestehende Nutzer gelten als verifiziert (Backfill mit created_at), damit sie
beim Aktivieren von EMAIL_VERIFICATION_REQUIRED nicht ausgesperrt werden.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    if not _column_exists("users", "email_verified_at"):
        with op.batch_alter_table("users", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    users = sa.table(
        "users",
        sa.column("created_at", sa.DateTime),
        sa.column("email_verified_at", sa.DateTime),
    )
    op.get_bind().execute(
        users.update()
        .where(users.c.email_verified_at.is_(None))
        .values(email_verified_at=sa.func.coalesce(users.c.created_at, sa.func.current_timestamp()))
    )


def downgrade():
    with op.batch_alter_table("users", schema=None, naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_column("email_verified_at")
