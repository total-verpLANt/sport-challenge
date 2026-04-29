"""add notes to activities

Revision ID: 72fada0b34c5
Revises: 149d8863712f
Create Date: 2026-04-29 15:23:59.678353

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72fada0b34c5'
down_revision = '149d8863712f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.drop_column('notes')
