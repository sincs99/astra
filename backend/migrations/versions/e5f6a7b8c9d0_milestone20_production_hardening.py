"""milestone20_production_hardening

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-13 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    return name in sa_inspect(bind).get_table_names()


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    # Agent Health
    if not _column_exists('agents', 'last_seen_at'):
        op.add_column('agents', sa.Column('last_seen_at', sa.DateTime(), nullable=True))

    # Webhook Delivery Tracking
    if not _table_exists('webhook_deliveries'):
        op.create_table(
            'webhook_deliveries',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('webhook_id', sa.Integer(), sa.ForeignKey('webhooks.id'), nullable=False),
            sa.Column('event', sa.String(64), nullable=False),
            sa.Column('endpoint_url', sa.String(2048), nullable=False),
            sa.Column('attempts', sa.Integer(), server_default='1'),
            sa.Column('success', sa.Boolean(), server_default='0'),
            sa.Column('status_code', sa.Integer(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table('webhook_deliveries')
    op.drop_column('agents', 'last_seen_at')
