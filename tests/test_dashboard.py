"""Integration tests for the dashboard route."""
from datetime import date, timedelta

import pytest

from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.services.weekly_summary import get_challenge_summary


def _create_challenge_with_participation(db, user_id, status="accepted"):
    today = date.today()
    challenge = Challenge(
        name="Dashboard Test Challenge",
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


def test_dashboard_requires_login(client, db):
    resp = client.get("/dashboard/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_dashboard_no_challenge(client, db):
    _create_and_login(client, db, email="nodash@test.com")
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert b"keine aktive Challenge" in resp.data or b"Challenge" in resp.data


def test_dashboard_with_challenge(client, app, db):
    """Verify the weekly_summary service correctly aggregates challenge data."""
    today = date.today()

    # Create admin user
    admin = User(email="admin@test.com", is_approved=True, role="admin")
    admin.set_password("pass123")
    db.session.add(admin)
    db.session.commit()

    challenge = Challenge(
        name="Active Dashboard Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=25),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()

    # Add a second participant
    participant = User(email="participant@test.com", is_approved=True)
    participant.set_password("pass123")
    db.session.add(participant)
    db.session.commit()

    participation_admin = ChallengeParticipation(
        user_id=admin.id,
        challenge_id=challenge.id,
        status="accepted",
        weekly_goal=3,
    )
    participation_p = ChallengeParticipation(
        user_id=participant.id,
        challenge_id=challenge.id,
        status="accepted",
        weekly_goal=3,
    )
    db.session.add_all([participation_admin, participation_p])

    # Add an activity for the participant
    activity = Activity(
        user_id=participant.id,
        challenge_id=challenge.id,
        activity_date=today,
        duration_minutes=45,
        sport_type="running",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()

    # Verify the summary service includes both participants
    with app.app_context():
        summary = get_challenge_summary(challenge)

    assert summary is not None
    assert summary["challenge"].name == "Active Dashboard Challenge"
    emails = {p["user"].email for p in summary["participants"]}
    assert "participant@test.com" in emails
    assert "admin@test.com" in emails

    # HTTP test: log in as participant and verify dashboard renders
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})
    resp = client.get("/dashboard/", follow_redirects=False)
    assert resp.status_code == 200


def test_user_activities_as_participant(client, db):
    today = date.today()

    # User A with challenge
    user_a = _create_and_login(client, db, email="ua_part@test.com")
    challenge = Challenge(
        name="Part Test Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user_a.id,
    )
    db.session.add(challenge)
    db.session.commit()

    participation_a = ChallengeParticipation(
        user_id=user_a.id,
        challenge_id=challenge.id,
        status="accepted",
    )
    db.session.add(participation_a)

    # Create activity for User A
    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge.id,
        activity_date=today,
        duration_minutes=45,
        sport_type="running",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()

    # User B joins same challenge
    client.post("/auth/logout")
    user_b = User(email="ub_part@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    participation_b = ChallengeParticipation(
        user_id=user_b.id,
        challenge_id=challenge.id,
        status="accepted",
    )
    db.session.add(participation_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "ub_part@test.com", "password": "testpass123"})

    resp = client.get(f"/challenge-activities/user/{user_a.id}", follow_redirects=False)
    assert resp.status_code == 200
    assert b"ua_part" in resp.data


def test_user_activities_as_non_participant(client, db):
    today = date.today()

    # User A with challenge
    user_a = _create_and_login(client, db, email="ua_npart@test.com")
    challenge = Challenge(
        name="NonPart Test Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user_a.id,
    )
    db.session.add(challenge)
    db.session.commit()

    participation_a = ChallengeParticipation(
        user_id=user_a.id,
        challenge_id=challenge.id,
        status="accepted",
    )
    db.session.add(participation_a)
    db.session.commit()

    # User B has NO participation
    client.post("/auth/logout")
    user_b = User(email="ub_npart@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "ub_npart@test.com", "password": "testpass123"})

    resp = client.get(f"/challenge-activities/user/{user_a.id}", follow_redirects=False)
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# New tests: Social-Media-Timeline, Feed, Likes, Leaderboard (Wave 4 / I-06)
# ---------------------------------------------------------------------------


def test_dashboard_top5_only(client, db):
    """Dashboard Leaderboard zeigt höchstens 5 User-Links ([:5]-Slice)."""
    user = _create_and_login(client, db, "lead@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    from app.extensions import db as _db
    from app.models.challenge import ChallengeParticipation
    from app.models.user import User

    for i in range(6):
        u = User(email=f"extra{i}@test.com", is_approved=True)
        u.set_password("pw")
        _db.session.add(u)
        _db.session.flush()
        p = ChallengeParticipation(
            user_id=u.id, challenge_id=challenge.id, status="accepted"
        )
        _db.session.add(p)
    _db.session.commit()

    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    html = resp.data.decode()
    user_links = html.count('href="/challenge-activities/user/')
    assert user_links <= 5, f"Expected <=5 user links, got {user_links}"


def test_leaderboard_full_shows_all_participants(client, db):
    """GET /dashboard/leaderboard zeigt alle Teilnehmer ohne Slice."""
    user = _create_and_login(client, db, "leadfull@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    from app.extensions import db as _db
    from app.models.challenge import ChallengeParticipation
    from app.models.user import User

    for i in range(6):
        u = User(email=f"fullex{i}@test.com", is_approved=True)
        u.set_password("pw")
        _db.session.add(u)
        _db.session.flush()
        p = ChallengeParticipation(
            user_id=u.id, challenge_id=challenge.id, status="accepted"
        )
        _db.session.add(p)
    _db.session.commit()

    resp = client.get("/dashboard/leaderboard")
    assert resp.status_code == 200
    html = resp.data.decode()
    user_links = html.count('href="/challenge-activities/user/')
    assert user_links >= 7, f"Expected >=7 user links, got {user_links}"


def test_feed_returns_json(client, db):
    """GET /dashboard/feed?challenge_id=X&page=0 liefert JSON mit activities und has_more."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity

    user = _create_and_login(client, db, "feeduser@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=datetime.date.today(),
        duration_minutes=45,
        sport_type="Laufen",
        source="manual",
    )
    _db.session.add(activity)
    _db.session.commit()

    resp = client.get(f"/dashboard/feed?challenge_id={challenge.id}&page=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "activities" in data
    assert "has_more" in data
    assert len(data["activities"]) == 1
    assert data["activities"][0]["sport_type"] == "Laufen"


def test_feed_only_challenge_participants(client, db):
    """GET /dashboard/feed liefert 403, wenn der User kein Teilnehmer der Challenge ist."""
    from app.extensions import db as _db
    from app.models.challenge import Challenge, ChallengeParticipation
    from app.models.user import User

    # User A mit eigener Challenge
    user_a = _create_and_login(client, db, "feed_a@test.com", "pw")
    challenge_a, _ = _create_challenge_with_participation(db, user_a.id)

    # User B ohne Teilnahme an challenge_a
    client.post("/auth/logout")
    user_b = User(email="feed_b@test.com", is_approved=True)
    user_b.set_password("pw")
    _db.session.add(user_b)
    _db.session.commit()
    client.post("/auth/login", data={"email": "feed_b@test.com", "password": "pw"})

    resp = client.get(f"/dashboard/feed?challenge_id={challenge_a.id}&page=0")
    assert resp.status_code == 403


def test_feed_pagination(client, db):
    """Feed liefert max. 10 Einträge pro Seite und korrektes has_more."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity

    user = _create_and_login(client, db, "feedpage@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    for i in range(12):
        a = Activity(
            user_id=user.id,
            challenge_id=challenge.id,
            activity_date=datetime.date.today(),
            duration_minutes=30 + i,
            sport_type="Radfahren",
            source="manual",
        )
        _db.session.add(a)
    _db.session.commit()

    resp0 = client.get(f"/dashboard/feed?challenge_id={challenge.id}&page=0")
    assert resp0.status_code == 200
    data0 = resp0.get_json()
    assert len(data0["activities"]) == 10
    assert data0["has_more"] is True

    resp1 = client.get(f"/dashboard/feed?challenge_id={challenge.id}&page=1")
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert len(data1["activities"]) == 2
    assert data1["has_more"] is False


def test_like_toggle_adds_like(client, db):
    """POST /dashboard/activities/<id>/like erstellt einen Like und gibt {liked:true, count:1} zurück."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity, ActivityLike

    user = _create_and_login(client, db, "likeuser@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=datetime.date.today(),
        duration_minutes=30,
        sport_type="Radfahren",
        source="manual",
    )
    _db.session.add(activity)
    _db.session.commit()

    resp = client.post(
        f"/dashboard/activities/{activity.id}/like",
        headers={"X-CSRFToken": "test"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["liked"] is True
    assert data["count"] == 1

    like = _db.session.execute(
        _db.select(ActivityLike).where(ActivityLike.activity_id == activity.id)
    ).scalars().first()
    assert like is not None
    assert like.user_id == user.id


def test_like_toggle_removes_like(client, db):
    """Doppelter POST auf like-Route entfernt den Like wieder (Toggle)."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity, ActivityLike

    user = _create_and_login(client, db, "unlike@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=datetime.date.today(),
        duration_minutes=30,
        sport_type="Schwimmen",
        source="manual",
    )
    _db.session.add(activity)
    _db.session.commit()

    # Like direkt in DB eintragen
    existing_like = ActivityLike(activity_id=activity.id, user_id=user.id)
    _db.session.add(existing_like)
    _db.session.commit()

    resp = client.post(
        f"/dashboard/activities/{activity.id}/like",
        headers={"X-CSRFToken": "test"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["liked"] is False
    assert data["count"] == 0

    like = _db.session.execute(
        _db.select(ActivityLike).where(ActivityLike.activity_id == activity.id)
    ).scalars().first()
    assert like is None


def test_like_requires_challenge_participation(client, db):
    """POST like gibt 403 zurück, wenn der User nicht an der Challenge teilnimmt."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity
    from app.models.user import User

    # User A legt Challenge + Activity an
    user_a = _create_and_login(client, db, "likeown@test.com", "pw")
    challenge_a, _ = _create_challenge_with_participation(db, user_a.id)

    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge_a.id,
        activity_date=datetime.date.today(),
        duration_minutes=40,
        sport_type="Yoga",
        source="manual",
    )
    _db.session.add(activity)
    _db.session.commit()

    # User B ohne Teilnahme an challenge_a
    client.post("/auth/logout")
    user_b = User(email="likenope@test.com", is_approved=True)
    user_b.set_password("pw")
    _db.session.add(user_b)
    _db.session.commit()
    client.post("/auth/login", data={"email": "likenope@test.com", "password": "pw"})

    resp = client.post(
        f"/dashboard/activities/{activity.id}/like",
        headers={"X-CSRFToken": "test"},
    )
    assert resp.status_code == 403
