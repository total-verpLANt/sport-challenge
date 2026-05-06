"""Integration tests for the Challenge routes."""
from datetime import date, timedelta

import pytest

from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_period import SickPeriod
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
        start_date=today - timedelta(days=1),
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
        f"/challenges/{challenge.public_id}/invite",
        data={"user_ids": [invitee.id]},
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


def test_invite_unapproved_user_rejected_detail(client, db):
    """Inviting unapproved user via detail page should be rejected."""
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    # Create an unapproved user
    unapproved = User(email="unapproved@test.com", is_approved=False)
    unapproved.set_password("pass123")
    db.session.add(unapproved)
    db.session.commit()

    # Attempt to invite the unapproved user via detail page
    resp = client.post(
        f"/challenges/{challenge.public_id}/invite",
        data={"user_ids": [unapproved.id]},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Verify the unapproved user was NOT invited
    participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == unapproved.id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert participation is None


def test_create_challenge_with_unapproved_users_rejected(client, db):
    """Creating challenge with unapproved users should skip them."""
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)

    # Create one approved and one unapproved user
    approved = User(email="approved@test.com", is_approved=True)
    approved.set_password("pass123")
    unapproved = User(email="unapproved@test.com", is_approved=False)
    unapproved.set_password("pass123")
    db.session.add_all([approved, unapproved])
    db.session.commit()

    today = date.today()
    resp = client.post(
        "/challenges/create",
        data={
            "name": "Challenge with Mixed Approval",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "penalty_per_miss": "5",
            "bailout_fee": "25",
            "invite_users": [approved.id, unapproved.id],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Verify challenge was created
    challenge = db.session.execute(
        db.select(Challenge).order_by(Challenge.id.desc()).limit(1)
    ).scalar_one()

    # Verify only the approved user was invited
    participations = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge.id
        )
    ).scalars().all()
    assert len(participations) == 1
    assert participations[0].user_id == approved.id
    assert participations[0].status == "invited"

    # Verify unapproved user was skipped
    unapproved_participation = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == unapproved.id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert unapproved_participation is None


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
        f"/challenges/{challenge.public_id}/accept",
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
        f"/challenges/{challenge.public_id}/decline",
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
        f"/challenges/{challenge.public_id}/bailout",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    db.session.refresh(participation)
    assert participation.status == "bailed_out"
    assert participation.bailed_out_at is not None


def test_sick_period_creation(client, db):
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

    today = date.today()
    # Daten innerhalb der Challenge-Grenzen (start=today-1, end=today+30)
    sick_from = today - timedelta(days=1)
    sick_to = today
    resp = client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    sick_period = db.session.execute(
        db.select(SickPeriod).where(
            SickPeriod.user_id == participant.id,
            SickPeriod.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert sick_period is not None
    assert sick_period.start_date == sick_from
    assert sick_period.end_date == sick_to


def test_overlapping_sick_period_rejected(client, db):
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

    today = date.today()
    sick_from = today - timedelta(days=3)
    sick_to = today

    # First sick period
    client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
    )
    # Second overlapping period – should be rejected
    client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
    )

    count = db.session.execute(
        db.select(SickPeriod).where(
            SickPeriod.user_id == participant.id,
            SickPeriod.challenge_id == challenge.id,
        )
    ).scalars().all()
    assert len(count) == 1


def _create_participant(db, challenge_id, email="p@test.com"):
    user = User(email=email, is_approved=True)
    user.set_password("pass123")
    db.session.add(user)
    db.session.commit()
    participation = ChallengeParticipation(
        user_id=user.id,
        challenge_id=challenge_id,
        status="accepted",
    )
    db.session.add(participation)
    db.session.commit()
    return user


def test_sick_period_submit_partial(client, db):
    """POST /sick-period mit Von/Bis legt partiellen Eintrag an."""
    admin = _create_and_login(client, db, email="admin_sw@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_sw@test.com")
    client.post("/auth/login", data={"email": "p_sw@test.com", "password": "pass123"})

    today = date.today()
    # Daten innerhalb der Challenge-Grenzen (start=today-1, end=today+30)
    sick_from = today - timedelta(days=1)
    sick_to = today + timedelta(days=1)

    resp = client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    sp = db.session.execute(
        db.select(SickPeriod).where(
            SickPeriod.user_id == participant.id,
            SickPeriod.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert sp is not None
    assert sp.start_date == sick_from
    assert sp.end_date == sick_to


def test_sick_period_update(client, db):
    """POST mit sick_period_id aktualisiert end_date statt Duplikat anzulegen."""
    admin = _create_and_login(client, db, email="admin_upd@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_upd@test.com")
    client.post("/auth/login", data={"email": "p_upd@test.com", "password": "pass123"})

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sick_from = monday
    sick_to_initial = monday + timedelta(days=6)

    # Create initial period
    client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to_initial.isoformat()},
    )

    sp = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == participant.id)
    ).scalar_one()

    # Update end_date (recovering early)
    sick_to_updated = monday + timedelta(days=3)
    client.post(
        "/challenge-activities/sick-period",
        data={
            "sick_period_id": str(sp.id),
            "sick_from": sick_from.isoformat(),
            "sick_to": sick_to_updated.isoformat(),
        },
    )

    rows = db.session.execute(
        db.select(SickPeriod).where(
            SickPeriod.user_id == participant.id,
            SickPeriod.challenge_id == challenge.id,
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].end_date == sick_to_updated


def test_sick_period_future_allowed(client, db):
    """Zukünftiger Zeitraum wird jetzt akzeptiert – Eintrag wird gespeichert."""
    admin = _create_and_login(client, db, email="admin_fut@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_fut@test.com")
    client.post("/auth/login", data={"email": "p_fut@test.com", "password": "pass123"})

    today = date.today()
    sick_from = today + timedelta(weeks=2)
    sick_to = today + timedelta(weeks=2, days=4)

    resp = client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    count = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == participant.id)
    ).scalars().all()
    assert len(count) == 1


def test_sick_period_von_bis_single_week(client, db):
    """von/bis innerhalb einer Woche: eine SickPeriod, start/end korrekt."""
    admin = _create_and_login(client, db, email="admin_vb1@test.com", is_admin=True)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    challenge = Challenge(
        name="VonBis Test",
        start_date=monday - timedelta(weeks=4),
        end_date=monday + timedelta(weeks=4),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_vb1@test.com")
    client.post("/auth/login", data={"email": "p_vb1@test.com", "password": "pass123"})

    # Di bis Do der aktuellen Woche
    sick_from = monday + timedelta(days=1)
    sick_to = monday + timedelta(days=3)
    resp = client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    rows = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == participant.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].start_date == sick_from
    assert rows[0].end_date == sick_to


def test_sick_period_von_bis_two_weeks(client, db):
    """von/bis über Wochengrenze: eine SickPeriod (kein Split), start/end korrekt."""
    admin = _create_and_login(client, db, email="admin_vb2@test.com", is_admin=True)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    prev_monday = monday - timedelta(weeks=1)
    challenge = Challenge(
        name="VonBis Zwei Wochen",
        start_date=prev_monday - timedelta(weeks=2),
        end_date=monday + timedelta(weeks=4),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_vb2@test.com")
    client.post("/auth/login", data={"email": "p_vb2@test.com", "password": "pass123"})

    # Do der Vorwoche bis Di dieser Woche
    sick_from = prev_monday + timedelta(days=3)  # Donnerstag Vorwoche
    sick_to = monday + timedelta(days=1)         # Dienstag diese Woche
    client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
    )

    rows = db.session.execute(
        db.select(SickPeriod).where(
            SickPeriod.user_id == participant.id,
            SickPeriod.challenge_id == challenge.id,
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].start_date == sick_from
    assert rows[0].end_date == sick_to


def test_sick_period_clamped_to_challenge_bounds(client, db):
    """Zeitraum außerhalb Challenge wird auf Challenge-Grenzen geclampt."""
    admin = _create_and_login(client, db, email="admin_clamp@test.com", is_admin=True)
    today = date.today()
    challenge = Challenge(
        name="Clamp Test",
        start_date=today,
        end_date=today + timedelta(days=27),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()
    client.post("/auth/logout")

    participant = _create_participant(db, challenge.id, email="p_clamp@test.com")
    client.post("/auth/login", data={"email": "p_clamp@test.com", "password": "pass123"})

    # Sende Zeitraum der vor Challenge-Start beginnt
    sick_from = today - timedelta(days=7)
    sick_to = today + timedelta(days=3)
    resp = client.post(
        "/challenge-activities/sick-period",
        data={"sick_from": sick_from.isoformat(), "sick_to": sick_to.isoformat()},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    sp = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == participant.id)
    ).scalar_one_or_none()
    assert sp is not None
    assert sp.start_date == challenge.start_date  # auf Challenge-Start geclampt
    assert sp.end_date == sick_to


def test_create_challenge_with_invites(client, db):
    """Admin creates a challenge and invites multiple users at once."""
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)

    # Create two users to invite
    user1 = User(email="user1@test.com", is_approved=True)
    user1.set_password("pass123")
    user2 = User(email="user2@test.com", is_approved=True)
    user2.set_password("pass123")
    db.session.add_all([user1, user2])
    db.session.commit()

    today = date.today()
    resp = client.post(
        "/challenges/create",
        data={
            "name": "Challenge with Invites",
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "penalty_per_miss": "5",
            "bailout_fee": "25",
            "invite_users": [user1.id, user2.id],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Verify challenge was created
    challenge = db.session.execute(
        db.select(Challenge).order_by(Challenge.id.desc()).limit(1)
    ).scalar_one()
    assert challenge.name == "Challenge with Invites"

    # Verify both users were invited
    participations = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge.id
        )
    ).scalars().all()
    assert len(participations) == 2
    assert all(p.status == "invited" for p in participations)

    user_ids = {p.user_id for p in participations}
    assert user_ids == {user1.id, user2.id}


def test_multi_invite_via_detail(client, db):
    """Admin invites multiple users via detail page."""
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    # Create three users to invite
    user1 = User(email="user1@test.com", is_approved=True)
    user1.set_password("pass123")
    user2 = User(email="user2@test.com", is_approved=True)
    user2.set_password("pass123")
    user3 = User(email="user3@test.com", is_approved=True)
    user3.set_password("pass123")
    db.session.add_all([user1, user2, user3])
    db.session.commit()

    # Invite two of them via POST
    resp = client.post(
        f"/challenges/{challenge.public_id}/invite",
        data={"user_ids": [user1.id, user2.id]},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Verify both were invited
    participations = db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.challenge_id == challenge.id
        )
    ).scalars().all()
    assert len(participations) == 2

    user_ids = {p.user_id for p in participations}
    assert user_ids == {user1.id, user2.id}
    assert all(p.status == "invited" for p in participations)
