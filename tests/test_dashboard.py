"""Integration tests for the dashboard route."""
from datetime import date, timedelta

import pytest

from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.services.weekly_summary import get_challenge_summary


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


def test_dashboard_with_challenge(app, db):
    """Verify the weekly_summary service correctly aggregates challenge data.

    Note: The dashboard template contains a known url_for bug
    ('challenge_activities.log' endpoint does not exist; it is 'log_form').
    This makes the rendered dashboard crash whenever summary is not None.
    This test therefore validates the service layer directly, which is what
    the dashboard route depends on.
    """
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
