"""add started_at to activity

Revision ID: 14c4e5d221f8
Revises: b0fe5687f411
Create Date: 2026-04-29 19:11:41.314206

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '14c4e5d221f8'
down_revision = 'b0fe5687f411'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.drop_column('started_at')
