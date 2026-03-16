"""feature_blueprint_vars_transfer

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-03-16 10:00:00.000000

Fuegt hinzu:
- blueprints.variables (JSON)
- blueprints.startup_command (Text)
- blueprints.install_script (Text)
- instances.variable_values (JSON)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in sa_inspect(bind).get_columns(table)]
    return column in columns


def upgrade():
    with op.batch_alter_table("blueprints", schema=None) as batch_op:
        if not _column_exists("blueprints", "startup_command"):
            batch_op.add_column(sa.Column("startup_command", sa.Text(), nullable=True))
        if not _column_exists("blueprints", "install_script"):
            batch_op.add_column(sa.Column("install_script", sa.Text(), nullable=True))
        if not _column_exists("blueprints", "variables"):
            batch_op.add_column(sa.Column("variables", sa.JSON(), nullable=True))

    with op.batch_alter_table("instances", schema=None) as batch_op:
        if not _column_exists("instances", "variable_values"):
            batch_op.add_column(sa.Column("variable_values", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("instances", schema=None) as batch_op:
        batch_op.drop_column("variable_values")

    with op.batch_alter_table("blueprints", schema=None) as batch_op:
        batch_op.drop_column("variables")
        batch_op.drop_column("install_script")
        batch_op.drop_column("startup_command")
