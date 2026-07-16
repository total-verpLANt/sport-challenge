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
    ACTIVITY_COMMENTED = "activity_commented"  # Urheber: Beitrag kommentiert
    DONATION_POLL_OPENED = "donation_poll_opened"  # Teilnehmer: Spendenziel-Abstimmung eröffnet


def create_notification(
    user_id: int,
    type: str,
    message: str,
    link_url: str | None = None,
    actor_id: int | None = None,
    commit: bool = False,
) -> Notification:
    """Legt eine Notification an (ungelesen).

    `actor_id` benennt den Auslöser (z.B. den Liker) – optional, da nicht
    jeder Typ einen hat. `commit=False` (Default): nur `add()` – fügt sich
    in die bestehende Transaktion des Auslösers ein, der ohnehin committet.
    `commit=True` committet sofort (für isolierte Aufrufe).
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        link_url=link_url,
        actor_id=actor_id,
    )
    db.session.add(notification)
    if commit:
        db.session.commit()
    return notification


def render_like_message(liker_names: list[str]) -> str:
    """Baut den gebündelten Like-Text. `liker_names`: neueste zuerst.

    1 → „A hat …", 2 → „A und B haben …", >2 → „A und N weitere haben …".
    """
    n = len(liker_names)
    if n == 1:
        return f"{liker_names[0]} hat deinen Beitrag geliked"
    if n == 2:
        return f"{liker_names[0]} und {liker_names[1]} haben deinen Beitrag geliked"
    return f"{liker_names[0]} und {n - 1} weitere haben deinen Beitrag geliked"


def upsert_like_notification(
    user_id: int,
    link_url: str,
    liker_names: list[str],
    latest_actor_id: int | None = None,
    commit: bool = False,
) -> Notification | None:
    """Pflegt die EINE gebündelte, ungelesene Like-Notification je Beitrag.

    `liker_names` = aktuelle fremde Liker (ohne Urheber), neueste zuerst.
    - Leere Liste → vorhandene UNGELESENE Bündel-Notif entfernen (Un-Like
      des letzten Likers), Rückgabe None.
    - Sonst: existierende ungelesene Bündel-Notif aktualisieren (Text,
      Actor, created_at → wieder nach oben) oder neu anlegen.
    Bereits GELESENE Notifications bleiben unberührt (historisch); ein neuer
    Like nach dem Lesen erzeugt so eine frische ungelesene Bündel-Notif.
    Notif-Identität: (Empfänger, Typ activity_liked, Beitrag, read_at NULL) –
    stets auf `user_id` gefiltert (kein IDOR).
    """
    existing = db.session.scalar(
        db.select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == NotificationType.ACTIVITY_LIKED,
            Notification.link_url == link_url,
            Notification.read_at.is_(None),
        )
    )

    if not liker_names:
        if existing is not None:
            db.session.delete(existing)
        if commit:
            db.session.commit()
        return None

    message = render_like_message(liker_names)
    if existing is not None:
        existing.message = message
        existing.actor_id = latest_actor_id
        existing.created_at = datetime.now(timezone.utc)
        notification = existing
    else:
        notification = Notification(
            user_id=user_id,
            type=NotificationType.ACTIVITY_LIKED,
            message=message,
            link_url=link_url,
            actor_id=latest_actor_id,
        )
        db.session.add(notification)

    if commit:
        db.session.commit()
    return notification


def render_comment_message(commenter_names: list[str]) -> str:
    """Baut den gebündelten Kommentar-Text. `commenter_names`: neueste zuerst.

    1 → „A hat …", 2 → „A und B haben …", >2 → „A und N weitere haben …".
    """
    n = len(commenter_names)
    if n == 1:
        return f"{commenter_names[0]} hat deinen Beitrag kommentiert"
    if n == 2:
        return f"{commenter_names[0]} und {commenter_names[1]} haben deinen Beitrag kommentiert"
    return f"{commenter_names[0]} und {n - 1} weitere haben deinen Beitrag kommentiert"


def upsert_comment_notification(
    user_id: int,
    link_url: str,
    commenter_names: list[str],
    latest_actor_id: int | None = None,
    commit: bool = False,
) -> Notification | None:
    """Pflegt die EINE gebündelte, ungelesene Kommentar-Notification je Beitrag.

    `commenter_names` = aktuelle fremde Kommentatoren (ohne Autor, distinct
    user_id), neueste zuerst – bereits vom Aufrufer dedupliziert/gefiltert.
    - Leere Liste → vorhandene UNGELESENE Bündel-Notif entfernen (letzter
      Kommentar gelöscht), Rückgabe None.
    - Sonst: existierende ungelesene Bündel-Notif aktualisieren (Text,
      Actor, created_at → wieder nach oben) oder neu anlegen.
    Bereits GELESENE Notifications bleiben unberührt (historisch); ein neuer
    Kommentar nach dem Lesen erzeugt so eine frische ungelesene Bündel-Notif.
    Notif-Identität: (Empfänger, Typ activity_commented, Beitrag, read_at
    NULL) – stets auf `user_id` gefiltert (kein IDOR).

    SICHERHEIT: `message` enthält NIE Kommentar-Freitext, nur die generischen
    Namens-Templates aus `render_comment_message` (XSS-Invariante).
    """
    existing = db.session.scalar(
        db.select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == NotificationType.ACTIVITY_COMMENTED,
            Notification.link_url == link_url,
            Notification.read_at.is_(None),
        )
    )

    if not commenter_names:
        if existing is not None:
            db.session.delete(existing)
        if commit:
            db.session.commit()
        return None

    message = render_comment_message(commenter_names)
    if existing is not None:
        existing.message = message
        existing.actor_id = latest_actor_id
        existing.created_at = datetime.now(timezone.utc)
        notification = existing
    else:
        notification = Notification(
            user_id=user_id,
            type=NotificationType.ACTIVITY_COMMENTED,
            message=message,
            link_url=link_url,
            actor_id=latest_actor_id,
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


def delete_notification(user_id: int, notification_id: int, commit: bool = True) -> bool:
    """Löscht EINE Notification – nur wenn sie dem User gehört (kein IDOR).

    Gibt True zurück, wenn etwas gelöscht wurde, sonst False.
    """
    result = db.session.execute(
        db.delete(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if commit:
        db.session.commit()
    return (result.rowcount or 0) > 0


def delete_all(user_id: int, commit: bool = True) -> int:
    """Löscht ALLE Notifications eines Users. Gibt die Anzahl zurück."""
    result = db.session.execute(
        db.delete(Notification).where(Notification.user_id == user_id)
    )
    if commit:
        db.session.commit()
    return result.rowcount or 0


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
