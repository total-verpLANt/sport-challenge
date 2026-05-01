"""add_video_path_to_bonus_challenge_entries

Revision ID: a1b2c3d4e5f6
Revises: fbfc6792eaa5
Create Date: 2026-05-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fbfc6792eaa5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bonus_challenge_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('video_path', sa.String(500), nullable=True))


def downgrade():
    with op.batch_alter_table('bonus_challenge_entries', schema=None) as batch_op:
        batch_op.drop_column('video_path')
