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


def test_dashboard_two_active_challenges_two_boards(client, db):
    """Zwei gleichzeitig aktive Challenges → zwei Top-5-Blöcke + zwei Spendentöpfe."""
    today = date.today()
    user = _create_and_login(client, db, "twoboards@test.com", "pw")

    for name in ("Alpha Challenge", "Beta Challenge"):
        c = Challenge(
            name=name,
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=30),
            penalty_per_miss=5.0,
            bailout_fee=25.0,
            created_by_id=user.id,
        )
        db.session.add(c)
        db.session.commit()
        db.session.add(
            ChallengeParticipation(
                user_id=user.id, challenge_id=c.id, status="accepted", weekly_goal=3
            )
        )
        db.session.commit()

    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Alpha Challenge" in html
    assert "Beta Challenge" in html
    # Zwei Spendentöpfe (ein Block je aktiver Challenge)
    assert html.count("Spendentopf") == 2


def test_dashboard_finished_challenge_shows_closing_card(client, db):
    """Beendete Challenge (kein aktives) → Abschluss-Karte mit Leaderboard-Link."""
    today = date.today()
    user = _create_and_login(client, db, "finished@test.com", "pw")

    c = Challenge(
        name="Vergangene Challenge",
        start_date=today - timedelta(days=30),
        end_date=today - timedelta(days=3),  # vor RECENT_FINISHED_DAYS-Fenster
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user.id,
    )
    db.session.add(c)
    db.session.commit()
    db.session.add(
        ChallengeParticipation(
            user_id=user.id, challenge_id=c.id, status="accepted", weekly_goal=3
        )
    )
    db.session.commit()

    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Abgeschlossen" in html
    assert f"/dashboard/leaderboard/{c.public_id}" in html


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


def test_leaderboard_by_public_id_visible_to_non_participant(client, db):
    """GET /dashboard/leaderboard/<public_id> ist für JEDEN eingeloggten User sichtbar.

    'Alle sehen alles': auch ein Nicht-Teilnehmer erhält 200, kein 403/404.
    """
    owner = _create_and_login(client, db, "lb_owner@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, owner.id)
    public_id = str(challenge.public_id)

    # Outsider ohne Teilnahme
    client.post("/auth/logout")
    outsider = User(email="lb_outsider@test.com", is_approved=True)
    outsider.set_password("pw")
    db.session.add(outsider)
    db.session.commit()
    client.post("/auth/login", data={"email": "lb_outsider@test.com", "password": "pw"})

    resp = client.get(f"/dashboard/leaderboard/{public_id}")
    assert resp.status_code == 200
    assert challenge.name.encode() in resp.data


def test_leaderboard_by_public_id_invalid_uuid_404(client, db):
    """Ungültige public_id → 404."""
    _create_and_login(client, db, "lb_bad@test.com", "pw")
    resp = client.get("/dashboard/leaderboard/not-a-uuid")
    assert resp.status_code == 404


def test_leaderboard_by_public_id_unknown_404(client, db):
    """Unbekannte (gültige) UUID → 404."""
    import uuid as _uuid

    _create_and_login(client, db, "lb_unknown@test.com", "pw")
    resp = client.get(f"/dashboard/leaderboard/{_uuid.uuid4()}")
    assert resp.status_code == 404


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

    resp = client.get("/dashboard/feed?page=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "items" in data
    assert "has_more" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["type"] == "activity"
    assert data["items"][0]["sport_type"] == "Laufen"
    # Globaler Feed trägt das Challenge-Label
    assert data["items"][0]["challenge_name"] == challenge.name


def test_feed_global_shows_other_challenges(client, db):
    """Der Feed zeigt Aktivitäten ALLER Challenges, auch fremder (alle sehen alles)."""
    import datetime

    from app.extensions import db as _db
    from app.models.activity import Activity
    from app.models.user import User

    # User A legt Challenge + Activity an
    user_a = _create_and_login(client, db, "feed_a@test.com", "pw")
    challenge_a, _ = _create_challenge_with_participation(db, user_a.id)
    _db.session.add(Activity(
        user_id=user_a.id, challenge_id=challenge_a.id,
        activity_date=datetime.date.today(), duration_minutes=42,
        sport_type="Klettern", source="manual",
    ))
    _db.session.commit()

    # User B ohne Teilnahme an challenge_a sieht die Aktivität trotzdem
    client.post("/auth/logout")
    user_b = User(email="feed_b@test.com", is_approved=True)
    user_b.set_password("pw")
    _db.session.add(user_b)
    _db.session.commit()
    client.post("/auth/login", data={"email": "feed_b@test.com", "password": "pw"})

    resp = client.get("/dashboard/feed?page=0")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    sports = {it.get("sport_type") for it in items if it["type"] == "activity"}
    assert "Klettern" in sports
    labels = {it.get("challenge_name") for it in items}
    assert challenge_a.name in labels


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

    resp0 = client.get("/dashboard/feed?page=0")
    assert resp0.status_code == 200
    data0 = resp0.get_json()
    assert len(data0["items"]) == 10
    assert data0["has_more"] is True

    resp1 = client.get("/dashboard/feed?page=1")
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert len(data1["items"]) == 2
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


def test_like_allowed_for_non_participant(client, db):
    """Jeder eingeloggte Nutzer darf liken – auch ohne Teilnahme (alle sehen alles)."""
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
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["liked"] is True
    assert data["count"] == 1


def _create_sick_period(db, user_id, challenge_id, reason=None, days=2):
    from app.models.sick_period import SickPeriod
    today = date.today()
    sp = SickPeriod(
        user_id=user_id,
        challenge_id=challenge_id,
        start_date=today,
        end_date=today + timedelta(days=days),
        reason=reason,
    )
    db.session.add(sp)
    db.session.commit()
    return sp


def test_feed_includes_absence(client, db):
    """Eine Abwesenheit erscheint als absence-Item im Feed (mit Grund, ohne Spruch)."""
    user = _create_and_login(client, db, "absfeed@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    _create_sick_period(db, user.id, challenge.id, reason="Urlaub auf Malle")

    resp = client.get("/dashboard/feed?page=0")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    absences = [it for it in items if it["type"] == "absence"]
    assert len(absences) == 1
    assert absences[0]["reason"] == "Urlaub auf Malle"
    assert "quote" not in absences[0]
    assert absences[0]["like_url"].endswith(f"/sick-periods/{absences[0]['id']}/like")


def test_like_sick_period_toggle(client, db):
    """Like-Toggle auf eine Abwesenheit: hinzufügen und wieder entfernen."""
    user = _create_and_login(client, db, "abslike@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    sp = _create_sick_period(db, user.id, challenge.id)

    r1 = client.post(f"/dashboard/sick-periods/{sp.id}/like", headers={"X-CSRFToken": "test"})
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1["liked"] is True and d1["count"] == 1

    r2 = client.post(f"/dashboard/sick-periods/{sp.id}/like", headers={"X-CSRFToken": "test"})
    d2 = r2.get_json()
    assert d2["liked"] is False and d2["count"] == 0


def test_like_sick_period_allowed_for_non_participant(client, db):
    """Like auf Abwesenheit ist für jeden eingeloggten Nutzer erlaubt (alle sehen alles)."""
    owner = _create_and_login(client, db, "absowner@test.com", "pw")
    challenge, _ = _create_challenge_with_participation(db, owner.id)
    sp = _create_sick_period(db, owner.id, challenge.id)

    client.post("/auth/logout")
    outsider = User(email="absoutsider@test.com", is_approved=True)
    outsider.set_password("pw")
    db.session.add(outsider)
    db.session.commit()
    client.post("/auth/login", data={"email": "absoutsider@test.com", "password": "pw"})

    resp = client.post(f"/dashboard/sick-periods/{sp.id}/like", headers={"X-CSRFToken": "test"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["liked"] is True
    assert data["count"] == 1


def test_like_sick_period_not_found(client, db):
    """Like auf nicht existierende Abwesenheit gibt 404."""
    _create_and_login(client, db, "abs404@test.com", "pw")
    resp = client.post("/dashboard/sick-periods/999999/like", headers={"X-CSRFToken": "test"})
    assert resp.status_code == 404
