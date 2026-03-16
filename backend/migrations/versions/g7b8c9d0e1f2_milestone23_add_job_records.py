"""milestone23_add_job_records

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-14 09:40:00.000000

Fuegt die job_records Tabelle fuer M23 Job-Tracking hinzu.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    return name in sa_inspect(bind).get_table_names()


def upgrade():
    if not _table_exists("job_records"):
        op.create_table(
            "job_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("uuid", sa.String(36), unique=True, nullable=False),
            sa.Column("job_type", sa.String(64), nullable=False, index=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
            sa.Column("attempts", sa.Integer(), server_default="0"),
            sa.Column("max_attempts", sa.Integer(), server_default="3"),
            sa.Column("payload_summary", sa.JSON(), nullable=True),
            sa.Column("result", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table("job_records")
