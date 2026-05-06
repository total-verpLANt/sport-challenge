"""replace_sick_weeks_with_sick_periods

Revision ID: a3f7e2b9c1d5
Revises: fbfc6792eaa5
Create Date: 2026-05-04 00:00:00.000000

"""
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a3f7e2b9c1d5'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Neue Tabelle anlegen
    op.create_table(
        "sick_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Datenmigration: sick_weeks → sick_periods
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT user_id, challenge_id, week_start, sick_days, created_at FROM sick_weeks"
        )
    ).fetchall()
    for row in rows:
        sick_days = max(row.sick_days if row.sick_days is not None else 7, 1)
        start_date = row.week_start
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        end_date = start_date + timedelta(days=min(sick_days, 7) - 1)
        conn.execute(
            sa.text(
                "INSERT INTO sick_periods (user_id, challenge_id, start_date, end_date, created_at) "
                "VALUES (:uid, :cid, :sd, :ed, :ca)"
            ),
            {
                "uid": row.user_id,
                "cid": row.challenge_id,
                "sd": start_date,
                "ed": end_date,
                "ca": row.created_at,
            },
        )

    # 3. Alte Tabelle löschen
    op.drop_table("sick_weeks")


def downgrade():
    # 1. sick_weeks wieder anlegen
    op.create_table(
        "sick_weeks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("challenge_id", sa.Integer(), sa.ForeignKey("challenges.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("sick_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "challenge_id", "week_start"),
    )

    # 2. Datenmigration: sick_periods → sick_weeks
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT user_id, challenge_id, start_date, end_date, created_at FROM sick_periods"
        )
    ).fetchall()
    for row in rows:
        start_date = row.start_date
        end_date = row.end_date
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        sick_days = min((end_date - start_date).days + 1, 7)
        week_start = start_date - timedelta(days=start_date.weekday())
        conn.execute(
            sa.text(
                "INSERT OR IGNORE INTO sick_weeks "
                "(user_id, challenge_id, week_start, sick_days, created_at) "
                "VALUES (:uid, :cid, :ws, :sd, :ca)"
            ),
            {
                "uid": row.user_id,
                "cid": row.challenge_id,
                "ws": week_start,
                "sd": sick_days,
                "ca": row.created_at,
            },
        )

    # 3. sick_periods löschen
    op.drop_table("sick_periods")
