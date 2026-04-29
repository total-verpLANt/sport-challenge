"""add_sick_days_to_sick_weeks

Revision ID: fbfc6792eaa5
Revises: 14c4e5d221f8
Create Date: 2026-04-29 19:27:18.216651

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fbfc6792eaa5'
down_revision = '14c4e5d221f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sick_weeks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sick_days', sa.Integer(), server_default='7', nullable=False))


def downgrade():
    with op.batch_alter_table('sick_weeks', schema=None) as batch_op:
        batch_op.drop_column('sick_days')
