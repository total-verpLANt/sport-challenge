"""add notifications.actor_id

Revision ID: 4e0eeef0019b
Revises: 7651f9766f3e
Create Date: 2026-06-22 10:49:35.153470

Rein additiv: ergänzt die Spalte `notifications.actor_id` (nullable FK auf
users, ON DELETE SET NULL). Identifiziert den Auslöser einer Notification
(z.B. den Liker), damit Like-Notifications pro (Beitrag, Liker) dedupliziert
und beim Un-Like zurückgenommen werden können. Altbestand bleibt NULL –
keine Daten-Migration, non-destruktiv.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4e0eeef0019b'
down_revision = '7651f9766f3e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_notifications_actor_id_users', 'users',
            ['actor_id'], ['id'], ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notifications_actor_id_users', type_='foreignkey')
        batch_op.drop_column('actor_id')
