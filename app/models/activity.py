from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Activity(db.Model):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    # Values: manual, garmin, strava
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    media: Mapped[list["ActivityMedia"]] = relationship(
        "ActivityMedia",
        back_populates="activity",
        cascade="all, delete-orphan",
        order_by="ActivityMedia.created_at",
    )
    likes: Mapped[list["ActivityLike"]] = relationship(
        "ActivityLike", back_populates="activity", cascade="all, delete-orphan"
    )
    comments: Mapped[list["ActivityComment"]] = relationship(
        "ActivityComment", back_populates="activity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_activity_user_external"),
    )


class ActivityMedia(db.Model):
    __tablename__ = "activity_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(10))   # "image" | "video"
    original_filename: Mapped[str] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="media")


class ActivityLike(db.Model):
    __tablename__ = "activity_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_activity_like_user"),
    )


# Kommentar-Rumpf – KEIN UI, nur Code-Struktur für spätere Implementierung
class ActivityComment(db.Model):
    __tablename__ = "activity_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()
