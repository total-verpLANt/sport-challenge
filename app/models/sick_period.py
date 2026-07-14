from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class SickPeriod(db.Model):
    __tablename__ = "sick_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    likes: Mapped[list["SickPeriodLike"]] = relationship(
        "SickPeriodLike", back_populates="sick_period", cascade="all, delete-orphan"
    )
    comments: Mapped[list["SickPeriodComment"]] = relationship(
        "SickPeriodComment", back_populates="sick_period", cascade="all, delete-orphan"
    )


class SickPeriodLike(db.Model):
    __tablename__ = "sick_period_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    sick_period_id: Mapped[int] = mapped_column(
        ForeignKey("sick_periods.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    sick_period: Mapped["SickPeriod"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("sick_period_id", "user_id", name="uq_sick_period_like_user"),
    )


class SickPeriodComment(db.Model):
    __tablename__ = "sick_period_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sick_period_id: Mapped[int] = mapped_column(
        ForeignKey("sick_periods.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    sick_period: Mapped["SickPeriod"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()
