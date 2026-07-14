"""add sick_period_comments

Rein additiv/non-destruktiv (siehe 8kr1): legt nur die neue Tabelle
sick_period_comments samt ihrer zwei Indizes an. Der von Alembic-Autogenerate
mitgenerierte Drift an challenges.public_id (bekannter Autogenerate-Bug,
siehe lessons-learned) wurde bewusst entfernt.

Revision ID: 15377314500e
Revises: 4e0eeef0019b
Create Date: 2026-07-14 11:59:58.822806

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '15377314500e'
down_revision = '4e0eeef0019b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sick_period_comments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sick_period_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['sick_period_id'], ['sick_periods.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sick_period_comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sick_period_comments_sick_period_id'), ['sick_period_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sick_period_comments_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('sick_period_comments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sick_period_comments_user_id'))
        batch_op.drop_index(batch_op.f('ix_sick_period_comments_sick_period_id'))

    op.drop_table('sick_period_comments')
