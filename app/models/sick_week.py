from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SickWeek(db.Model):
    __tablename__ = "sick_weeks"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "week_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)  # Monday of the week
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
