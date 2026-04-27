"""add_activity_media_table

Revision ID: 149d8863712f
Revises: 6edd5dce59eb
Create Date: 2026-04-27 22:44:44.296021

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '149d8863712f'
down_revision = '6edd5dce59eb'
branch_labels = None
depends_on = None


def upgrade():
    # Schritt 1: Tabelle anlegen
    op.create_table('activity_media',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('media_type', sa.String(length=10), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('activity_media', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_activity_media_activity_id'), ['activity_id'], unique=False)

    # Schritt 2: Legacy-Daten migrieren (screenshot_path → activity_media)
    op.execute("""
        INSERT INTO activity_media (activity_id, file_path, media_type, original_filename, file_size_bytes, created_at)
        SELECT id, screenshot_path, 'image', 'screenshot', 0, created_at
        FROM activities
        WHERE screenshot_path IS NOT NULL
    """)
    # Schritt 3: screenshot_path bleibt nullable – kein DROP in dieser Migration


def downgrade():
    with op.batch_alter_table('activity_media', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_activity_media_activity_id'))

    op.drop_table('activity_media')
