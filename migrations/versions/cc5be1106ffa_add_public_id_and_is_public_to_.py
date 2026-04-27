"""add_public_id_and_is_public_to_challenges

Revision ID: cc5be1106ffa
Revises: 77fe1b237497
Create Date: 2026-04-27 15:49:22.028722

"""
import uuid as _uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'cc5be1106ffa'
down_revision = '77fe1b237497'
branch_labels = None
depends_on = None


def upgrade():
    # Schritt 1: Beide Spalten nullable hinzufügen
    with op.batch_alter_table("challenges", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("public_id", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("is_public", sa.Boolean(), nullable=True))

    # Schritt 2: Bestehende Rows mit UUID und Standardwert befüllen
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM challenges")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE challenges SET public_id = :uid, is_public = 0 WHERE id = :id"),
            {"uid": _uuid.uuid4().hex, "id": row.id},
        )

    # Schritt 3: NOT NULL-Constraint setzen + UNIQUE-Index anlegen
    with op.batch_alter_table("challenges", recreate="auto") as batch_op:
        batch_op.alter_column("public_id", nullable=False, existing_type=sa.String(32))
        batch_op.alter_column("is_public", nullable=False, existing_type=sa.Boolean())
        batch_op.create_unique_constraint("uq_challenges_public_id", ["public_id"])
        batch_op.create_index("ix_challenges_public_id", ["public_id"])


def downgrade():
    with op.batch_alter_table("challenges", recreate="auto") as batch_op:
        batch_op.drop_index("ix_challenges_public_id")
        batch_op.drop_constraint("uq_challenges_public_id", type_="unique")
        batch_op.drop_column("is_public")
        batch_op.drop_column("public_id")
