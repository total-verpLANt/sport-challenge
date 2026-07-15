"""Tests für die Spendenziel-Routen (Teil 1: Seite + Vorschläge, Epic 1t8s).

Fixture-Muster wiederverwendet aus tests/test_comments.py (`_create_and_login`);
Challenge-/Participation-Helfer mit konfigurierbarem Enddatum und Status.
"""
from datetime import date, timedelta

from app.models.challenge import Challenge, ChallengeParticipation
from app.models.donation import DonationPoll, DonationProposal


# --- Fixture-Helfer --------------------------------------------------------

def _create_and_login(client, db, email="test@test.com", password="testpass123", is_admin=False):
    from app.models.user import User
    user = User(email=email, is_approved=True)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def _create_challenge(db, created_by_id, days_until_end=30, is_public=False):
    today = date.today()
    challenge = Challenge(
        name="Donation Test Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=days_until_end),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        is_public=is_public,
        created_by_id=created_by_id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def _add_participation(db, user_id, challenge_id, status="accepted"):
    participation = ChallengeParticipation(
        user_id=user_id,
        challenge_id=challenge_id,
        status=status,
    )
    db.session.add(participation)
    db.session.commit()
    return participation


def _create_proposal(db, challenge_id, created_by_id, name="Seenotretter"):
    proposal = DonationProposal(
        challenge_id=challenge_id,
        created_by_id=created_by_id,
        name=name,
    )
    db.session.add(proposal)
    db.session.commit()
    return proposal


def _open_poll(db, challenge_id, created_by_id):
    poll = DonationPoll(
        challenge_id=challenge_id,
        created_by_id=created_by_id,
        max_votes_per_user=1,
    )
    db.session.add(poll)
    db.session.commit()
    return poll


def _proposal_count(db, challenge_id):
    return db.session.scalar(
        db.select(db.func.count())
        .select_from(DonationProposal)
        .where(DonationProposal.challenge_id == challenge_id)
    )


# --- Seite -----------------------------------------------------------------

def test_page_requires_login(client, db):
    from app.models.user import User
    user = User(email="owner@test.com", is_approved=True)
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    challenge = _create_challenge(db, user.id)

    response = client.get(f"/donation/{challenge.public_id}")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


# --- Vorschlag anlegen -----------------------------------------------------

def test_create_proposal_as_participant(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    _add_participation(db, user.id, challenge.id, status="accepted")

    response = client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "Seenotretter", "description": "DGzRS – Rettung auf See"},
    )
    assert response.status_code == 302

    proposal = db.session.scalar(
        db.select(DonationProposal).where(DonationProposal.challenge_id == challenge.id)
    )
    assert proposal is not None
    assert proposal.name == "Seenotretter"
    assert proposal.description == "DGzRS – Rettung auf See"
    assert proposal.created_by_id == user.id


def test_create_proposal_bailed_out_allowed(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    _add_participation(db, user.id, challenge.id, status="bailed_out")

    response = client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "Tafel Hamburg"},
    )
    assert response.status_code == 302
    assert _proposal_count(db, challenge.id) == 1


def test_create_proposal_non_participant_rejected(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    # Keine Participation angelegt

    client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "Seenotretter"},
    )
    assert _proposal_count(db, challenge.id) == 0


def test_create_proposal_empty_name_400(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    _add_participation(db, user.id, challenge.id)

    response = client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "   "},
    )
    assert response.status_code == 400
    assert _proposal_count(db, challenge.id) == 0


def test_create_proposal_bad_url_rejected(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    _add_participation(db, user.id, challenge.id)

    response = client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "Boese", "url": "javascript:alert(1)"},
    )
    assert response.status_code == 400
    assert _proposal_count(db, challenge.id) == 0


def test_create_proposal_blocked_after_poll_opened(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id)

    client.post(
        f"/donation/{challenge.public_id}/proposals",
        data={"name": "Zu spaet"},
    )
    assert _proposal_count(db, challenge.id) == 1  # nur der bestehende Vorschlag


# --- Vorschlag löschen -----------------------------------------------------

def test_delete_own_proposal_before_poll(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id)

    response = client.post(f"/donation/proposals/{proposal.id}/delete")
    assert response.status_code == 302
    assert db.session.get(DonationProposal, proposal.id) is None


def test_delete_foreign_proposal_403(client, db):
    owner = _create_and_login(client, db, email="proposal_owner@test.com")
    challenge = _create_challenge(db, owner.id)
    _add_participation(db, owner.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, owner.id)
    client.post("/auth/logout")

    other = _create_and_login(client, db, email="other@test.com")
    _add_participation(db, other.id, challenge.id)

    response = client.post(f"/donation/proposals/{proposal.id}/delete")
    assert response.status_code == 403
    assert db.session.get(DonationProposal, proposal.id) is not None


def test_admin_deletes_proposal_during_poll(client, db):
    owner = _create_and_login(client, db, email="proposal_owner@test.com")
    challenge = _create_challenge(db, owner.id, days_until_end=-1)
    _add_participation(db, owner.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, owner.id)
    _open_poll(db, challenge.id, owner.id)
    client.post("/auth/logout")

    _create_and_login(client, db, email="admin@test.com", is_admin=True)

    response = client.post(f"/donation/proposals/{proposal.id}/delete")
    assert response.status_code == 302
    assert db.session.get(DonationProposal, proposal.id) is None
