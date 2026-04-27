"""add unique constraint user_id external_id to activities

Revision ID: 6edd5dce59eb
Revises: cc5be1106ffa
Create Date: 2026-04-27 16:55:29.925366

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '6edd5dce59eb'
down_revision = 'cc5be1106ffa'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_activity_user_external', ['user_id', 'external_id']
        )


def downgrade():
    with op.batch_alter_table('activities', schema=None) as batch_op:
        batch_op.drop_constraint('uq_activity_user_external', type_='unique')
