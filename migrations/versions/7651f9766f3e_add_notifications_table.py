"""add notifications table

Revision ID: 7651f9766f3e
Revises: aab58a149773
Create Date: 2026-06-21 19:06:11.652973

Rein additiv: legt ausschließlich die neue Tabelle `notifications` an.
Der von Alembic-Autogenerate zusätzlich vorgeschlagene `challenges.public_id`-
Drift (VARCHAR(32) -> Uuid, Unique-Constraint/Index) wurde BEWUSST entfernt –
er gehört nicht zu diesem Ticket und darf die laufende Prod-Tabelle nicht
anfassen (oberstes Prinzip: nur additiv/non-destruktiv).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7651f9766f3e'
down_revision = 'aab58a149773'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('link_url', sa.String(length=500), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('ix_notifications_user_read', ['user_id', 'read_at'], unique=False)


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_user_read')

    op.drop_table('notifications')
