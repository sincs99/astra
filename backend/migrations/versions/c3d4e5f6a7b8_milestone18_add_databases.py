"""milestone18_add_database_provisioning

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-13 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def _table_exists(name):
    bind = op.get_bind()
    return name in sa_inspect(bind).get_table_names()


def upgrade():
    if not _table_exists('database_providers'):
        op.create_table(
            'database_providers',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('host', sa.String(255), nullable=False),
            sa.Column('port', sa.Integer(), nullable=False, server_default='3306'),
            sa.Column('admin_user', sa.String(120), nullable=False, server_default='root'),
            sa.Column('admin_password', sa.String(256), nullable=True),
            sa.Column('max_databases', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )

    if not _table_exists('databases'):
        op.create_table(
            'databases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('instance_id', sa.Integer(), sa.ForeignKey('instances.id'), nullable=False),
            sa.Column('provider_id', sa.Integer(), sa.ForeignKey('database_providers.id'), nullable=False),
            sa.Column('db_name', sa.String(64), nullable=False),
            sa.Column('username', sa.String(64), nullable=False),
            sa.Column('password', sa.String(256), nullable=False),
            sa.Column('remote_host', sa.String(255), nullable=False, server_default='%'),
            sa.Column('max_connections', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('provider_id', 'db_name', name='uq_provider_db_name'),
            sa.UniqueConstraint('provider_id', 'username', name='uq_provider_username'),
        )


def downgrade():
    op.drop_table('databases')
    op.drop_table('database_providers')
