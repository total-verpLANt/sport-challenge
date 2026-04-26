"""Integration tests for the Bonus Challenge routes."""
from datetime import date, timedelta

import pytest

from app.models.bonus import BonusChallenge, BonusChallengeEntry
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User


def _create_and_login(client, db, email="test@test.com", password="testpass123", is_admin=False):
    user = User(email=email, is_approved=True)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def _create_challenge(db, creator_id):
    today = date.today()
    challenge = Challenge(
        name="Bonus Base Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=creator_id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def test_admin_can_create_bonus_challenge(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    scheduled_date = date.today() + timedelta(days=5)
    resp = client.post(
        "/bonus/create",
        data={
            "scheduled_date": scheduled_date.isoformat(),
            "description": "50 Burpees",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    bonus = db.session.execute(
        db.select(BonusChallenge).where(BonusChallenge.challenge_id == challenge.id)
    ).scalar_one_or_none()
    assert bonus is not None
    assert bonus.description == "50 Burpees"


def test_submit_bonus_entry(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    # Create an accepted participant
    participant = User(email="participant@test.com", is_approved=True)
    participant.set_password("pass123")
    db.session.add(participant)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=participant.id,
        challenge_id=challenge.id,
        status="accepted",
        weekly_goal=3,
    )
    db.session.add(participation)
    db.session.commit()

    # Create a bonus challenge
    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="50 Squat Jumps",
    )
    db.session.add(bonus)
    db.session.commit()

    # Login as participant and submit
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:35"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    entry = db.session.execute(
        db.select(BonusChallengeEntry).where(
            BonusChallengeEntry.user_id == participant.id,
            BonusChallengeEntry.bonus_challenge_id == bonus.id,
        )
    ).scalar_one_or_none()
    assert entry is not None
    assert entry.time_seconds == 155  # 2*60 + 35


def test_duplicate_entry_rejected(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    participant = User(email="participant@test.com", is_approved=True)
    participant.set_password("pass123")
    db.session.add(participant)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=participant.id,
        challenge_id=challenge.id,
        status="accepted",
        weekly_goal=3,
    )
    db.session.add(participation)
    db.session.commit()

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="100 Push-ups",
    )
    db.session.add(bonus)
    db.session.commit()

    # Login as participant
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    # First entry
    client.post(f"/bonus/{bonus.id}/entry", data={"time": "3:00"})
    # Second entry (duplicate) — should be handled gracefully (IntegrityError)
    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:50"},
        follow_redirects=False,
    )
    assert resp.status_code == 302  # Redirect with flash, no 500

    entries = db.session.execute(
        db.select(BonusChallengeEntry).where(
            BonusChallengeEntry.user_id == participant.id,
            BonusChallengeEntry.bonus_challenge_id == bonus.id,
        )
    ).scalars().all()
    assert len(entries) == 1


def test_bonus_requires_login(client, db):
    resp = client.get("/bonus/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
