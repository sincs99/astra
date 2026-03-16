"""milestone15_add_container_state

Revision ID: a1b2c3d4e5f6
Revises: 77f298ea83c4
Create Date: 2026-03-13 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '77f298ea83c4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('instances', sa.Column('container_state', sa.String(32), nullable=True))


def downgrade():
    op.drop_column('instances', 'container_state')
