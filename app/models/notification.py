from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


class Notification(db.Model):
    """Persistente Benachrichtigung für einen Empfänger.

    `message` ist der fertig gerenderte Anzeigetext (wird im Template
    auto-escaped → kein XSS). `link_url` wird ausschließlich serverseitig
    per `url_for()` gesetzt, nie aus User-Input → kein `javascript:`-Vektor.
    Ungelesen ⇔ `read_at IS NULL`.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Auslöser der Notification (z.B. der Liker). Nullable, da nicht jeder
    # Typ einen Actor hat (Lifecycle/System). SET NULL: wird der Actor
    # gelöscht, bleibt die Notification erhalten (kein verwaister FK).
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Empfänger. foreign_keys explizit, da mit actor_id zwei FK-Pfade zu users existieren.
    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    # Composite-Index für die Badge-/Ungelesen-Query (user_id + read_at).
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "read_at"),
    )
