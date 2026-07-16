"""Tests für die Spendenziel-Routen (Teil 1: Seite + Vorschläge, Epic 1t8s).

Fixture-Muster wiederverwendet aus tests/test_comments.py (`_create_and_login`);
Challenge-/Participation-Helfer mit konfigurierbarem Enddatum und Status.
"""
from datetime import date, timedelta

from app.models.challenge import Challenge, ChallengeParticipation
from app.models.donation import DonationPoll, DonationProposal, DonationVote


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


def _open_poll(db, challenge_id, created_by_id, max_votes=1, status="open"):
    poll = DonationPoll(
        challenge_id=challenge_id,
        created_by_id=created_by_id,
        max_votes_per_user=max_votes,
        status=status,
    )
    db.session.add(poll)
    db.session.commit()
    return poll


def _create_user(db, email, nickname=None):
    from app.models.user import User
    user = User(email=email, is_approved=True)
    if nickname:
        user.nickname = nickname
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    return user


def _add_vote(db, user_id, proposal_id):
    vote = DonationVote(user_id=user_id, proposal_id=proposal_id)
    db.session.add(vote)
    db.session.commit()
    return vote


def _poll_for(db, challenge_id):
    return db.session.scalar(
        db.select(DonationPoll).where(DonationPoll.challenge_id == challenge_id)
    )


def _vote_count_for_user(db, user_id):
    return db.session.scalar(
        db.select(db.func.count())
        .select_from(DonationVote)
        .where(DonationVote.user_id == user_id)
    )


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


# --- Poll öffnen -------------------------------------------------------------

def test_open_poll_requires_admin(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    _create_proposal(db, challenge.id, user.id)

    response = client.post(
        f"/donation/{challenge.public_id}/poll/open",
        data={"max_votes_per_user": "1"},
    )
    assert response.status_code == 403
    assert _poll_for(db, challenge.id) is None


def test_open_poll_before_end_date_rejected(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id, days_until_end=5)
    _create_proposal(db, challenge.id, admin.id)

    response = client.post(
        f"/donation/{challenge.public_id}/poll/open",
        data={"max_votes_per_user": "1"},
    )
    assert response.status_code == 302
    assert _poll_for(db, challenge.id) is None


def test_open_poll_sets_max_votes(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id, days_until_end=-1)
    _create_proposal(db, challenge.id, admin.id, name="Seenotretter")
    _create_proposal(db, challenge.id, admin.id, name="Tafel Hamburg")

    response = client.post(
        f"/donation/{challenge.public_id}/poll/open",
        data={"max_votes_per_user": "2"},
    )
    assert response.status_code == 302

    poll = _poll_for(db, challenge.id)
    assert poll is not None
    assert poll.max_votes_per_user == 2
    assert poll.status == "open"


def test_open_poll_twice_rejected(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id, days_until_end=-1)
    _create_proposal(db, challenge.id, admin.id)
    _open_poll(db, challenge.id, admin.id)

    response = client.post(
        f"/donation/{challenge.public_id}/poll/open",
        data={"max_votes_per_user": "1"},
    )
    assert response.status_code == 302

    poll_count = db.session.scalar(
        db.select(db.func.count())
        .select_from(DonationPoll)
        .where(DonationPoll.challenge_id == challenge.id)
    )
    assert poll_count == 1


# --- Abstimmen ---------------------------------------------------------------

def test_vote_within_limit(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id)

    response = client.post(f"/donation/proposals/{proposal.id}/vote")
    assert response.status_code == 302

    vote = db.session.scalar(
        db.select(DonationVote).where(
            DonationVote.user_id == user.id,
            DonationVote.proposal_id == proposal.id,
        )
    )
    assert vote is not None


def test_vote_over_limit_rejected(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal_a = _create_proposal(db, challenge.id, user.id, name="Ziel A")
    proposal_b = _create_proposal(db, challenge.id, user.id, name="Ziel B")
    _open_poll(db, challenge.id, user.id, max_votes=1)

    client.post(f"/donation/proposals/{proposal_a.id}/vote")
    client.post(f"/donation/proposals/{proposal_b.id}/vote")

    assert _vote_count_for_user(db, user.id) == 1


def test_vote_duplicate_same_proposal_rejected(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id, name="Ziel A")
    _create_proposal(db, challenge.id, user.id, name="Ziel B")
    # max_votes=2, damit der Count-Check passiert und der UNIQUE-Constraint greift
    _open_poll(db, challenge.id, user.id, max_votes=2)

    client.post(f"/donation/proposals/{proposal.id}/vote")
    client.post(f"/donation/proposals/{proposal.id}/vote")

    assert _vote_count_for_user(db, user.id) == 1


def test_vote_on_closed_poll_rejected(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id, status="closed")

    client.post(f"/donation/proposals/{proposal.id}/vote")

    assert _vote_count_for_user(db, user.id) == 0


def test_unvote_removes_own_vote(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id)
    _add_vote(db, user.id, proposal.id)

    response = client.post(f"/donation/proposals/{proposal.id}/unvote")
    assert response.status_code == 302
    assert _vote_count_for_user(db, user.id) == 0


# --- Poll schließen ----------------------------------------------------------

def test_close_poll_fixes_winner(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id, days_until_end=-1)
    proposal_a = _create_proposal(db, challenge.id, admin.id, name="Ziel A")
    proposal_b = _create_proposal(db, challenge.id, admin.id, name="Ziel B")
    _open_poll(db, challenge.id, admin.id)

    voter1 = _create_user(db, "voter1@test.com")
    voter2 = _create_user(db, "voter2@test.com")
    _add_vote(db, voter1.id, proposal_a.id)
    _add_vote(db, voter2.id, proposal_a.id)
    _add_vote(db, admin.id, proposal_b.id)

    response = client.post(f"/donation/{challenge.public_id}/poll/close")
    assert response.status_code == 302

    poll = _poll_for(db, challenge.id)
    assert poll.status == "closed"
    assert poll.winner_proposal_id == proposal_a.id
    assert poll.closed_at is not None


def test_close_poll_tie_requires_admin_choice(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id, days_until_end=-1)
    proposal_a = _create_proposal(db, challenge.id, admin.id, name="Ziel A")
    proposal_b = _create_proposal(db, challenge.id, admin.id, name="Ziel B")
    proposal_c = _create_proposal(db, challenge.id, admin.id, name="Ziel C")
    _open_poll(db, challenge.id, admin.id)

    voter1 = _create_user(db, "voter1@test.com")
    _add_vote(db, voter1.id, proposal_a.id)
    _add_vote(db, admin.id, proposal_b.id)
    # Gleichstand A:B = 1:1, C = 0

    # Ohne Auswahl → bleibt offen
    client.post(f"/donation/{challenge.public_id}/poll/close")
    poll = _poll_for(db, challenge.id)
    assert poll.status == "open"

    # Auswahl eines NICHT-punktgleichen Vorschlags → bleibt offen
    client.post(
        f"/donation/{challenge.public_id}/poll/close",
        data={"winner_proposal_id": str(proposal_c.id)},
    )
    poll = _poll_for(db, challenge.id)
    assert poll.status == "open"
    assert poll.winner_proposal_id is None

    # Gültige Auswahl → geschlossen mit korrektem Gewinner
    client.post(
        f"/donation/{challenge.public_id}/poll/close",
        data={"winner_proposal_id": str(proposal_b.id)},
    )
    poll = _poll_for(db, challenge.id)
    assert poll.status == "closed"
    assert poll.winner_proposal_id == proposal_b.id


def test_close_poll_requires_admin(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id)

    response = client.post(f"/donation/{challenge.public_id}/poll/close")
    assert response.status_code == 403

    poll = _poll_for(db, challenge.id)
    assert poll.status == "open"


# --- Live-Zwischenstand ------------------------------------------------------

def test_live_counts_visible_without_names(client, db):
    user = _create_and_login(client, db)
    challenge = _create_challenge(db, user.id, days_until_end=-1)
    _add_participation(db, user.id, challenge.id)
    proposal = _create_proposal(db, challenge.id, user.id)
    _open_poll(db, challenge.id, user.id)

    voter = _create_user(db, "zorbulax@test.com", nickname="ZorbulaxQuandrofil")
    _add_vote(db, voter.id, proposal.id)

    response = client.get(f"/donation/{challenge.public_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "1 Stimme" in html
    assert "ZorbulaxQuandrofil" not in html
    assert "zorbulax" not in html
