"""Tests für die Kommentar-Routen (Aktivitäten + Abwesenheiten) inkl. Notifications.

Fixture-Muster wiederverwendet aus tests/test_dashboard.py (siehe Briefing
8kr1.6): `_create_and_login`, `_create_challenge_with_participation`,
`_setup_owner_with_activity`, `_count_like_notifications`-Vorbild für die
Kommentar-Notification-Zählung.
"""
from datetime import date, timedelta

from app.models.activity import Activity, ActivityComment
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.notification import Notification
from app.models.sick_period import SickPeriod, SickPeriodComment
from app.models.user import User


# --- Fixture-Helfer (aus tests/test_dashboard.py übernommen) --------------

def _create_challenge_with_participation(db, user_id, status="accepted"):
    today = date.today()
    challenge = Challenge(
        name="Comment Test Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user_id,
    )
    db.session.add(challenge)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=user_id,
        challenge_id=challenge.id,
        status=status,
    )
    db.session.add(participation)
    db.session.commit()
    return challenge, participation


def _create_and_login(client, db, email="test@test.com", password="testpass123", is_admin=False):
    user = User(email=email, is_approved=True)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def _setup_owner_with_activity(client, db):
    """Owner A mit Aktivität anlegen, danach ausloggen. Gibt (owner, activity) zurück."""
    today = date.today()
    owner = _create_and_login(client, db, email="comment_owner@test.com")
    challenge, _ = _create_challenge_with_participation(db, owner.id, status="accepted")
    activity = Activity(
        user_id=owner.id,
        challenge_id=challenge.id,
        activity_date=today,
        duration_minutes=45,
        sport_type="running",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    client.post("/auth/logout")
    return owner, activity


def _setup_owner_with_sick_period(client, db, days=2):
    """Owner mit SickPeriod anlegen, danach ausloggen. Gibt (owner, period) zurück."""
    today = date.today()
    owner = _create_and_login(client, db, email="comment_sick_owner@test.com")
    challenge, _ = _create_challenge_with_participation(db, owner.id, status="accepted")
    period = SickPeriod(
        user_id=owner.id,
        challenge_id=challenge.id,
        start_date=today,
        end_date=today + timedelta(days=days),
        reason="Grippe",
    )
    db.session.add(period)
    db.session.commit()
    client.post("/auth/logout")
    return owner, period


def _count_comment_notifications(db, user_id):
    return db.session.scalar(
        db.select(db.func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type == "activity_commented",
        )
    )


def _latest_comment_notification(db, user_id):
    return db.session.scalar(
        db.select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type == "activity_commented",
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )


# ---------------------------------------------------------------------------
# Aktivitäts-Kommentare: create/list/delete
# ---------------------------------------------------------------------------

def test_comment_activity_creates_comment(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter1@test.com")

    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Starke Leistung!"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["comment"]["body"] == "Starke Leistung!"

    stored = db.session.scalars(
        db.select(ActivityComment).where(ActivityComment.activity_id == activity.id)
    ).all()
    assert len(stored) == 1
    assert stored[0].body == "Starke Leistung!"


def test_comment_empty_rejected(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_empty@test.com")

    resp = client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": ""})
    assert resp.status_code == 400

    count = db.session.scalar(
        db.select(db.func.count()).select_from(ActivityComment)
        .where(ActivityComment.activity_id == activity.id)
    )
    assert count == 0


def test_comment_whitespace_rejected(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_ws@test.com")

    resp = client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "   "})
    assert resp.status_code == 400

    count = db.session.scalar(
        db.select(db.func.count()).select_from(ActivityComment)
        .where(ActivityComment.activity_id == activity.id)
    )
    assert count == 0


def test_comment_too_long_rejected(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_long@test.com")

    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "x" * 1001},
    )
    assert resp.status_code == 400

    count = db.session.scalar(
        db.select(db.func.count()).select_from(ActivityComment)
        .where(ActivityComment.activity_id == activity.id)
    )
    assert count == 0


def test_comment_nonexistent_activity_404(client, db):
    _create_and_login(client, db, email="commenter_404@test.com")
    resp = client.post(
        "/dashboard/activities/999999/comments",
        data={"body": "Hallo"},
    )
    assert resp.status_code == 404


def test_comment_requires_login(client, db):
    resp = client.post(
        "/dashboard/activities/1/comments",
        data={"body": "Hallo"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_list_comments_chronological(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_chrono@test.com")

    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Erster"})
    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Zweiter"})
    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Dritter"})

    resp = client.get(f"/dashboard/activities/{activity.id}/comments")
    assert resp.status_code == 200
    bodies = [c["body"] for c in resp.get_json()["comments"]]
    assert bodies == ["Erster", "Zweiter", "Dritter"]


def test_comment_foreign_activity_creates_notification(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_foreign@test.com")

    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Nice!"},
    )
    assert resp.status_code == 200
    assert _count_comment_notifications(db, owner.id) == 1


def test_self_comment_creates_no_notification(client, db):
    today = date.today()
    owner = _create_and_login(client, db, email="self_comment@test.com")
    challenge, _ = _create_challenge_with_participation(db, owner.id, status="accepted")
    activity = Activity(
        user_id=owner.id,
        challenge_id=challenge.id,
        activity_date=today,
        duration_minutes=45,
        sport_type="running",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()

    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Eigener Kommentar"},
    )
    assert resp.status_code == 200
    assert _count_comment_notifications(db, owner.id) == 0


def test_two_commenters_bundled_into_one(client, db):
    owner, activity = _setup_owner_with_activity(client, db)

    _create_and_login(client, db, email="commenter_a@test.com")
    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Kommentar A"})
    client.post("/auth/logout")

    _create_and_login(client, db, email="commenter_b@test.com")
    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Kommentar B"})

    assert _count_comment_notifications(db, owner.id) == 1
    msg = _latest_comment_notification(db, owner.id).message
    assert " und " in msg and msg.endswith("haben deinen Beitrag kommentiert")


def test_same_user_comments_twice_single_name(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    commenter = _create_and_login(client, db, email="commenter_twice@test.com")

    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Erster"})
    client.post(f"/dashboard/activities/{activity.id}/comments", data={"body": "Zweiter"})

    assert _count_comment_notifications(db, owner.id) == 1
    msg = _latest_comment_notification(db, owner.id).message
    # Nur einmal genannt (Dedup), nicht "X und X haben..."
    assert msg == f"{commenter.display_name} hat deinen Beitrag kommentiert"
    assert msg.count(commenter.display_name) == 1


def test_delete_own_comment(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_del_own@test.com")

    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Wird gelöscht"},
    )
    comment_id = resp.get_json()["comment"]["id"]

    del_resp = client.post(f"/dashboard/activity-comments/{comment_id}/delete")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["count"] == 0
    assert db.session.get(ActivityComment, comment_id) is None


def test_delete_foreign_comment_403(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_author@test.com")
    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Fremder Kommentar"},
    )
    comment_id = resp.get_json()["comment"]["id"]
    client.post("/auth/logout")

    _create_and_login(client, db, email="commenter_intruder@test.com")
    del_resp = client.post(f"/dashboard/activity-comments/{comment_id}/delete")
    assert del_resp.status_code == 403
    assert db.session.get(ActivityComment, comment_id) is not None


def test_admin_deletes_foreign_comment(client, db):
    owner, activity = _setup_owner_with_activity(client, db)
    _create_and_login(client, db, email="commenter_author2@test.com")
    resp = client.post(
        f"/dashboard/activities/{activity.id}/comments",
        data={"body": "Von Admin zu löschen"},
    )
    comment_id = resp.get_json()["comment"]["id"]
    client.post("/auth/logout")

    _create_and_login(client, db, email="admin_deleter@test.com", is_admin=True)
    del_resp = client.post(f"/dashboard/activity-comments/{comment_id}/delete")
    assert del_resp.status_code == 200
    assert db.session.get(ActivityComment, comment_id) is None


# ---------------------------------------------------------------------------
# SickPeriod-Kommentare: Kernfälle
# ---------------------------------------------------------------------------

def test_comment_sick_period_creates_comment(client, db):
    owner, period = _setup_owner_with_sick_period(client, db)
    _create_and_login(client, db, email="sick_commenter1@test.com")

    resp = client.post(
        f"/dashboard/sick-periods/{period.id}/comments",
        data={"body": "Gute Besserung!"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["comment"]["body"] == "Gute Besserung!"

    stored = db.session.scalars(
        db.select(SickPeriodComment).where(SickPeriodComment.sick_period_id == period.id)
    ).all()
    assert len(stored) == 1


def test_comment_sick_period_notification(client, db):
    owner, period = _setup_owner_with_sick_period(client, db)
    _create_and_login(client, db, email="sick_commenter2@test.com")

    resp = client.post(
        f"/dashboard/sick-periods/{period.id}/comments",
        data={"body": "Alles Gute"},
    )
    assert resp.status_code == 200
    assert _count_comment_notifications(db, owner.id) == 1


def test_delete_sick_period_comment_foreign_403(client, db):
    owner, period = _setup_owner_with_sick_period(client, db)
    _create_and_login(client, db, email="sick_commenter_author@test.com")
    resp = client.post(
        f"/dashboard/sick-periods/{period.id}/comments",
        data={"body": "Fremder Kommentar"},
    )
    comment_id = resp.get_json()["comment"]["id"]
    client.post("/auth/logout")

    _create_and_login(client, db, email="sick_commenter_intruder@test.com")
    del_resp = client.post(f"/dashboard/sick-period-comments/{comment_id}/delete")
    assert del_resp.status_code == 403
    assert db.session.get(SickPeriodComment, comment_id) is not None
