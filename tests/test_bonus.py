"""Integration tests for the Bonus Challenge routes."""
import io
import os
from datetime import date, timedelta

import pytest
from werkzeug.datastructures import MultiDict

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


def _make_participant(db, challenge_id, email="participant@test.com", password="pass123"):
    user = User(email=email, is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    participation = ChallengeParticipation(
        user_id=user.id,
        challenge_id=challenge_id,
        status="accepted",
        weekly_goal=3,
    )
    db.session.add(participation)
    db.session.commit()
    return user


def _fake_video(filename="proof.mp4"):
    return (io.BytesIO(b"fake video content"), filename)


def test_admin_can_create_bonus_challenge(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)

    d1 = date.today() + timedelta(days=5)
    d2 = date.today() + timedelta(days=19)
    resp = client.post(
        "/bonus/create",
        data=MultiDict([
            ("description", "50 Burpees"),
            ("scheduled_date", d1.isoformat()),
            ("scheduled_date", d2.isoformat()),
        ]),
        follow_redirects=False,
    )
    assert resp.status_code == 302

    bonuses = db.session.execute(
        db.select(BonusChallenge).where(BonusChallenge.challenge_id == challenge.id)
    ).scalars().all()
    assert len(bonuses) == 2
    assert all(b.description == "50 Burpees" for b in bonuses)


def test_submit_bonus_entry(client, db, app):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="50 Squat Jumps",
    )
    db.session.add(bonus)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:35", "video": _fake_video()},
        content_type="multipart/form-data",
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
    assert entry.video_path is not None


def test_duplicate_entry_rejected(client, db, app):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="100 Push-ups",
    )
    db.session.add(bonus)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    # First entry
    client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "3:00", "video": _fake_video("first.mp4")},
        content_type="multipart/form-data",
    )
    # Second entry (duplicate) — should be handled gracefully
    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:50", "video": _fake_video("second.mp4")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

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


def test_entry_accepted_for_past_date(client, db):
    """Einsendungen sind auch nach dem scheduled_date erlaubt (kein Datum-Limit)."""
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today() - timedelta(days=14),  # längst vergangen
        description="50 Squat Jumps",
    )
    db.session.add(bonus)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:35", "video": _fake_video()},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    entry = db.session.execute(
        db.select(BonusChallengeEntry).where(BonusChallengeEntry.user_id == participant.id)
    ).scalar_one_or_none()
    assert entry is not None  # Nachträgliche Einsendung muss akzeptiert werden


def test_entry_requires_video(client, db):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="50 Squat Jumps",
    )
    db.session.add(bonus)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:35"},  # kein video
        follow_redirects=False,
    )
    assert resp.status_code == 302

    entry = db.session.execute(
        db.select(BonusChallengeEntry).where(BonusChallengeEntry.user_id == participant.id)
    ).scalar_one_or_none()
    assert entry is None


def test_entry_rejects_image_file(client, db, app):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date.today(),
        description="50 Squat Jumps",
    )
    db.session.add(bonus)
    db.session.commit()

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "participant@test.com", "password": "pass123"})

    upload_folder = app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    files_before = set(os.listdir(upload_folder))

    resp = client.post(
        f"/bonus/{bonus.id}/entry",
        data={"time": "2:35", "video": (io.BytesIO(b"fake image"), "photo.jpg")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    entry = db.session.execute(
        db.select(BonusChallengeEntry).where(BonusChallengeEntry.user_id == participant.id)
    ).scalar_one_or_none()
    assert entry is None

    # Kein Orphan auf Disk – delete_upload() muss das .jpg wieder entfernt haben
    files_after = set(os.listdir(upload_folder))
    assert files_after == files_before


def test_overall_ranking_best_time(client, db, app):
    admin = _create_and_login(client, db, email="admin@test.com", is_admin=True)
    challenge = _create_challenge(db, admin.id)
    participant = _make_participant(db, challenge.id)

    # Zwei Bonus-Challenges: User hat 3:00 beim ersten, 2:00 beim zweiten
    bc1 = BonusChallenge(challenge_id=challenge.id, scheduled_date=date.today() - timedelta(days=14), description="Runde 1")
    bc2 = BonusChallenge(challenge_id=challenge.id, scheduled_date=date.today() - timedelta(days=7), description="Runde 2")
    db.session.add_all([bc1, bc2])
    db.session.commit()

    db.session.add(BonusChallengeEntry(user_id=participant.id, bonus_challenge_id=bc1.id, time_seconds=180.0))
    db.session.add(BonusChallengeEntry(user_id=participant.id, bonus_challenge_id=bc2.id, time_seconds=120.0))
    db.session.commit()

    resp = client.get("/bonus/")
    assert resp.status_code == 200
    # Beste Zeit 2:00 muss erscheinen, nicht 3:00
    assert b"2:00" in resp.data
