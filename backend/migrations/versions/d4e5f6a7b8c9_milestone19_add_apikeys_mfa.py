"""milestone19_add_apikeys_mfa

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
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
    # API Keys Tabelle
    if not _table_exists('api_keys'):
        op.create_table(
            'api_keys',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('key_type', sa.String(32), nullable=False, server_default='account'),
            sa.Column('identifier', sa.String(16), unique=True, nullable=False),
            sa.Column('token_hash', sa.String(128), nullable=False),
            sa.Column('memo', sa.String(255), nullable=True),
            sa.Column('allowed_ips', sa.Text(), nullable=True),
            sa.Column('permissions', sa.JSON(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    # MFA-Felder am User
    if not _column_exists('users', 'mfa_secret'):
        op.add_column('users', sa.Column('mfa_secret', sa.String(64), nullable=True))
    if not _column_exists('users', 'mfa_enabled'):
        op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), server_default='0'))
    if not _column_exists('users', 'mfa_recovery_codes'):
        op.add_column('users', sa.Column('mfa_recovery_codes', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('users', 'mfa_recovery_codes')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret')
    op.drop_table('api_keys')
