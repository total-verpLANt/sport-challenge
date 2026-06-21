"""Integrationstests für das Notification-Center (Routen + Navbar-Glocke, wsco)."""
from app.models.notification import Notification
from app.models.user import User
from app.services.notifications import NotificationType, create_notification, unread_count


def _create_and_login(client, db, email="notif@test.com", password="testpass123"):
    user = User(email=email, is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def test_go_marks_read_and_redirects_to_link(client, db):
    user = _create_and_login(client, db)
    n = create_notification(
        user.id, NotificationType.CHALLENGE_INVITE, "Einladung", link_url="/challenges/", commit=True
    )
    resp = client.get(f"/notifications/{n.id}/go", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/challenges/")
    assert db.session.get(Notification, n.id).read_at is not None
    assert unread_count(user.id) == 0


def test_go_open_redirect_guard(client, db):
    """Externe/protocol-relative link_url wird auf das Dashboard umgeleitet."""
    user = _create_and_login(client, db)
    for evil in ["https://evil.example.com", "//evil.example.com", "/\\evil"]:
        n = create_notification(user.id, NotificationType.ACTIVITY_LIKED, "x", link_url=evil, commit=True)
        resp = client.get(f"/notifications/{n.id}/go", follow_redirects=False)
        assert resp.status_code == 302
        assert "evil" not in resp.headers["Location"]
        assert "/dashboard/" in resp.headers["Location"]


def test_go_foreign_notification_not_marked(client, db):
    """Fremde Notification: kein Lesen, Redirect aufs Dashboard."""
    owner = User(email="owner@test.com", is_approved=True)
    owner.set_password("pass12345")
    db.session.add(owner)
    db.session.commit()
    n = create_notification(owner.id, NotificationType.ACTIVITY_LIKED, "geheim", link_url="/x", commit=True)

    _create_and_login(client, db, email="intruder@test.com")
    resp = client.get(f"/notifications/{n.id}/go", follow_redirects=False)
    assert resp.status_code == 302
    assert "/dashboard/" in resp.headers["Location"]
    assert db.session.get(Notification, n.id).read_at is None


def test_delete_endpoint_removes_and_returns_count(client, db):
    user = _create_and_login(client, db)
    n1 = create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m1", commit=True)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m2", commit=True)
    resp = client.post(f"/notifications/{n1.id}/delete")
    assert resp.status_code == 200
    assert resp.get_json()["unread_count"] == 1
    assert db.session.get(Notification, n1.id) is None


def test_delete_all_endpoint(client, db):
    user = _create_and_login(client, db)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m1", commit=True)
    create_notification(user.id, NotificationType.ACTIVITY_LIKED, "m2", commit=True)
    resp = client.post("/notifications/delete-all")
    assert resp.status_code == 200
    assert resp.get_json()["unread_count"] == 0
    assert unread_count(user.id) == 0


def test_navbar_bell_shows_unread_badge_and_highlight(client, db):
    user = _create_and_login(client, db)
    create_notification(user.id, NotificationType.CHALLENGE_INVITE, "Frische Einladung", commit=True)
    resp = client.get("/dashboard/")
    body = resp.get_data(as_text=True)
    assert "notif-center" in body
    assert "Frische Einladung" in body
    # Ungelesene tragen die Hervorhebungs-Klasse:
    assert "bg-primary-subtle" in body
    # Badge ist sichtbar (nicht d-none), da 1 ungelesen:
    assert "notif-badge" in body


def test_navbar_bell_requires_login(client, db):
    """Anonyme werden zum Login geleitet – keine Glocke."""
    resp = client.get("/dashboard/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
