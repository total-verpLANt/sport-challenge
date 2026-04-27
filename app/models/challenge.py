import uuid as _uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.extensions import db


class Challenge(db.Model):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[_uuid.UUID] = mapped_column(
        Uuid, default=_uuid.uuid4, nullable=False, unique=True, index=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    penalty_per_miss: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    bailout_fee: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    participations = db.relationship("ChallengeParticipation", back_populates="challenge")


class ChallengeParticipation(db.Model):
    __tablename__ = "challenge_participations"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    weekly_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 2 or 3
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    # Values: invited, accepted, bailed_out
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bailed_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    challenge = db.relationship("Challenge", back_populates="participations")
    user = db.relationship("User")
