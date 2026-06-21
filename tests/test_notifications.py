"""Unit-Tests für den Notification-Service (Ticket gau4, Fundament)."""
from app.models.notification import Notification
from app.models.user import User
from app.services.notifications import (
    NotificationType,
    create_notification,
    list_for_user,
    mark_read,
    unread_count,
)


def _make_user(db, email="notif@test.com"):
    user = User(email=email, is_approved=True)
    user.set_password("pass12345")
    db.session.add(user)
    db.session.commit()
    return user


def test_create_notification_is_unread(db):
    user = _make_user(db)
    n = create_notification(
        user.id,
        NotificationType.CHALLENGE_INVITE,
        "Du wurdest zu 'Sommer' eingeladen",
        link_url="/dashboard/",
        commit=True,
    )
    assert n.id is not None
    assert n.read_at is None
    assert n.type == NotificationType.CHALLENGE_INVITE
    assert n.link_url == "/dashboard/"


def test_create_without_commit_needs_caller_commit(db):
    """commit=False fügt nur hinzu – sichtbar erst nach Commit des Aufrufers."""
    user = _make_user(db)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "X gefällt dein Beitrag")
    # Noch nicht committet, aber in der Session sichtbar (flush bei Query):
    assert unread_count(user.id) == 1
    db.session.commit()
    assert unread_count(user.id) == 1


def test_unread_count_isolated_per_user(db):
    a = _make_user(db, "a@test.com")
    b = _make_user(db, "b@test.com")
    create_notification(a.id, NotificationType.NEW_REGISTRATION, "m1", commit=True)
    create_notification(a.id, NotificationType.NEW_REGISTRATION, "m2", commit=True)
    create_notification(b.id, NotificationType.NEW_REGISTRATION, "m3", commit=True)
    assert unread_count(a.id) == 2
    assert unread_count(b.id) == 1


def test_list_for_user_newest_first_and_limited(db):
    user = _make_user(db)
    for i in range(5):
        create_notification(user.id, NotificationType.ACTIVITY_LIKED, f"m{i}", commit=True)
    items = list_for_user(user.id, limit=3)
    assert len(items) == 3
    # Neueste zuerst (m4 vor m3 vor m2)
    assert items[0].message == "m4"
    assert items[2].message == "m2"


def test_mark_read_all(db):
    user = _make_user(db)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m1", commit=True)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m2", commit=True)
    assert unread_count(user.id) == 2
    affected = mark_read(user.id)
    assert affected == 2
    assert unread_count(user.id) == 0


def test_mark_read_specific_ids(db):
    user = _make_user(db)
    n1 = create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m1", commit=True)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m2", commit=True)
    affected = mark_read(user.id, ids=[n1.id])
    assert affected == 1
    assert unread_count(user.id) == 1


def test_mark_read_does_not_touch_other_users(db):
    """IDOR-Schutz: mark_read filtert stets auf user_id, auch bei fremden IDs."""
    a = _make_user(db, "a@test.com")
    b = _make_user(db, "b@test.com")
    nb = create_notification(b.id, NotificationType.ACTIVITY_LIKED, "b-msg", commit=True)
    # User a versucht, die Notification von b als gelesen zu markieren:
    affected = mark_read(a.id, ids=[nb.id])
    assert affected == 0
    assert unread_count(b.id) == 1
    assert db.session.get(Notification, nb.id).read_at is None


def test_mark_read_empty_ids_noop(db):
    user = _make_user(db)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m1", commit=True)
    affected = mark_read(user.id, ids=[])
    assert affected == 0
    assert unread_count(user.id) == 1
