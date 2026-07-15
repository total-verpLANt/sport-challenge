from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db


class DonationProposal(db.Model):
    __tablename__ = "donation_proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class DonationPoll(db.Model):
    __tablename__ = "donation_polls"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # Values: open, closed
    max_votes_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    winner_proposal_id: Mapped[int | None] = mapped_column(ForeignKey("donation_proposals.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DonationVote(db.Model):
    __tablename__ = "donation_votes"
    __table_args__ = (UniqueConstraint("user_id", "proposal_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("donation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
