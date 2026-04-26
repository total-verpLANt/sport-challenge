"""Integration tests for the Challenge routes."""
from datetime import date, timedelta

import pytest

from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
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


def _create_challenge(db, creator_id, name="Test Challenge"):
    today = date.today()
    challenge = Challenge(
        name=name,
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=creator_id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def test_admin_can_create_challenge(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    today = date.today()
    resp = client.post(
        "/challenges/create",
        data={
            "name": "Epic Challenge",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=31)).isoformat(),
            "penalty_per_miss": "5",
            "bailout_fee": "25",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    challenge = db.session.execute(
        db.select(Challenge).where(Challenge.name == "Epic Challenge")
    ).scalar_one_or_none()
    assert challenge is not None
    assert challenge.created_by_id == admin.id


def test_non_admin_cannot_create_challenge(client, db):
    _create_and_login(client, db, email="user@test.com", is_admin=False)
    today = date.today()
    resp = client.post(
        "/challenges/create",
        data={
            "name": "Unauthorized Challenge",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=31)).isoformat(),
            "penalty_per_miss": "5",
            "bailout_fee": "25",
        },
    )
    assert resp.status_code == 403


def test_invite_user_to_challenge(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    # Create a second user to invite
    invitee = User(email="invitee@test.com", is_approved=True)
    invitee.set_password("pass123")
    db.session.add(invitee)
    db.session.commit()

    resp = client.post(
        f"/challenges/{challenge.id}/invite",
        data={"user_id": invitee.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == invitee.id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert participation is not None
    assert participation.status == "invited"


def test_accept_invitation(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    # Create invitee and invitation
    invitee = User(email="invitee@test.com", is_approved=True)
    invitee.set_password("pass123")
    db.session.add(invitee)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=invitee.id,
        challenge_id=challenge.id,
        status="invited",
    )
    db.session.add(participation)
    db.session.commit()

    # Login as invitee and accept
    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "invitee@test.com", "password": "pass123"})

    resp = client.post(
        f"/challenges/{challenge.id}/accept",
        data={"weekly_goal": "2"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.session.refresh(participation)
    assert participation.status == "accepted"
    assert participation.weekly_goal == 2
    assert participation.accepted_at is not None


def test_decline_invitation(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    invitee = User(email="invitee@test.com", is_approved=True)
    invitee.set_password("pass123")
    db.session.add(invitee)
    db.session.commit()

    participation = ChallengeParticipation(
        user_id=invitee.id,
        challenge_id=challenge.id,
        status="invited",
    )
    db.session.add(participation)
    db.session.commit()
    p_id = participation.id

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "invitee@test.com", "password": "pass123"})

    resp = client.post(
        f"/challenges/{challenge.id}/decline",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    gone = db.session.get(ChallengeParticipation, p_id)
    assert gone is None


def test_bailout_from_challenge(client, db):
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
    )
    db.session.add(participation)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/challenges/{challenge.id}/bailout",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.session.refresh(participation)
    assert participation.status == "bailed_out"
    assert participation.bailed_out_at is not None


def test_sick_week_creation(client, db):
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
    )
    db.session.add(participation)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/challenges/{challenge.id}/sick",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    today = date.today()
    expected_monday = today - timedelta(days=today.weekday())
    sick_week = db.session.execute(
        db.select(SickWeek).where(
            SickWeek.user_id == participant.id,
            SickWeek.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert sick_week is not None
    assert sick_week.week_start == expected_monday


def test_duplicate_sick_week_rejected(client, db):
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
    )
    db.session.add(participation)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    # First sick report
    client.post(f"/challenges/{challenge.id}/sick")
    # Second sick report (duplicate)
    client.post(f"/challenges/{challenge.id}/sick")

    count = db.session.execute(
        db.select(SickWeek).where(
            SickWeek.user_id == participant.id,
            SickWeek.challenge_id == challenge.id,
        )
    ).scalars().all()
    assert len(count) == 1
