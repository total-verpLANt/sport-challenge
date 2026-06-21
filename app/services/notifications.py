"""Service-Layer für persistente Benachrichtigungen (Notification-Fundament).

Auslöser (Registrierung, Challenge-Einladung, …) rufen `create_notification`
auf; die Navbar-Glocke nutzt `unread_count` / `list_for_user`; das Markieren
als gelesen läuft über `mark_read`.

Sicherheits-Invariante: `link_url` wird IMMER vom aufrufenden Code per
`url_for()` erzeugt (interne Ziele), NIE aus User-Input übernommen.
"""
from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db
from app.models.notification import Notification


# --- Notification-Typen (für Icon/Filter im Frontend) ---------------------
class NotificationType:
    NEW_REGISTRATION = "new_registration"      # Admin: User wartet auf Freischaltung
    CHALLENGE_INVITE = "challenge_invite"      # User: zu Challenge eingeladen
    CHALLENGE_LIFECYCLE = "challenge_lifecycle"  # Teilnehmer: Start/Ende
    ACTIVITY_LIKED = "activity_liked"          # Urheber: Beitrag geliked


def create_notification(
    user_id: int,
    type: str,
    message: str,
    link_url: str | None = None,
    commit: bool = False,
) -> Notification:
    """Legt eine Notification an (ungelesen).

    `commit=False` (Default): nur `add()` – fügt sich in die bestehende
    Transaktion des Auslösers ein, der ohnehin committet. `commit=True`
    committet sofort (für isolierte Aufrufe).
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        link_url=link_url,
    )
    db.session.add(notification)
    if commit:
        db.session.commit()
    return notification


def unread_count(user_id: int) -> int:
    """Anzahl ungelesener Notifications (read_at IS NULL) eines Users."""
    return db.session.scalar(
        db.select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    ) or 0


def list_for_user(user_id: int, limit: int = 10) -> list[Notification]:
    """Neueste Notifications eines Users (für das Glocken-Dropdown)."""
    return list(
        db.session.scalars(
            db.select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )


def mark_read(user_id: int, ids: list[int] | None = None, commit: bool = True) -> int:
    """Markiert Notifications als gelesen (setzt read_at).

    `ids=None` → alle ungelesenen des Users. Sonst nur die genannten IDs,
    aber STETS auf `user_id` gefiltert (kein Fremdzugriff/IDOR). Gibt die
    Anzahl der betroffenen Zeilen zurück.
    """
    stmt = (
        db.update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    if ids is not None:
        if not ids:
            return 0
        stmt = stmt.where(Notification.id.in_(ids))
    result = db.session.execute(
        stmt.values(read_at=datetime.now(timezone.utc))
    )
    if commit:
        db.session.commit()
    return result.rowcount or 0
