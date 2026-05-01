from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db


class BonusChallenge(db.Model):
    __tablename__ = "bonus_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="50 Squat Jumps")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class BonusChallengeEntry(db.Model):
    __tablename__ = "bonus_challenge_entries"
    __table_args__ = (UniqueConstraint("user_id", "bonus_challenge_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bonus_challenge_id: Mapped[int] = mapped_column(ForeignKey("bonus_challenges.id"), nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
