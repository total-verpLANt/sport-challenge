"""Integration tests for challenge activity logging routes."""
from datetime import date, timedelta
from io import BytesIO

import pytest

from app.models.activity import Activity, ActivityMedia
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


def _create_challenge_with_participation(db, user_id, status="accepted"):
    today = date.today()
    challenge = Challenge(
        name="Log Test Challenge",
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


def test_log_manual_activity(client, db):
    user = _create_and_login(client, db, email="logger@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    today = date.today()
    activity_date = today  # within challenge period

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": activity_date.isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(
            Activity.user_id == user.id,
            Activity.challenge_id == challenge.id,
        )
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.duration_minutes == 45
    assert activity.sport_type == "running"
    assert activity.source == "manual"
    assert activity.activity_date == activity_date


def test_log_activity_requires_participation(client, db):
    # Login without any accepted participation
    _create_and_login(client, db, email="nopart@test.com")

    resp = client.get("/challenge-activities/log", follow_redirects=False)
    assert resp.status_code == 302
    assert "/challenges" in resp.headers["Location"]


def test_delete_own_activity(client, db):
    user = _create_and_login(client, db, email="deleter@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="cycling",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    resp = client.post(
        f"/challenge-activities/{activity_id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    gone = db.session.get(Activity, activity_id)
    assert gone is None


def test_cannot_delete_others_activity(client, db):
    # User A creates activity
    user_a = _create_and_login(client, db, email="usera@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)

    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="swimming",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    # Login as user B
    client.post("/auth/logout")
    user_b = User(email="userb@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "userb@test.com", "password": "testpass123"})

    resp = client.post(
        f"/challenge-activities/{activity_id}/delete",
        follow_redirects=False,
    )
    # Should redirect (flash error + redirect), not delete the activity
    assert resp.status_code == 302

    still_there = db.session.get(Activity, activity_id)
    assert still_there is not None


def test_activity_detail_owner(client, db):
    user = _create_and_login(client, db, email="detail_owner@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=45,
        sport_type="Laufen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()

    resp = client.get(f"/challenge-activities/{activity.id}", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Laufen" in resp.data


def test_activity_detail_other_participant(client, db):
    # User A creates activity
    user_a = _create_and_login(client, db, email="detail_usera@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)

    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=45,
        sport_type="Laufen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    # User B joins the same challenge
    client.post("/auth/logout")
    user_b = User(email="detail_userb@test.com", is_approved=True)
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
    client.post("/auth/login", data={"email": "detail_userb@test.com", "password": "testpass123"})

    resp = client.get(f"/challenge-activities/{activity_id}", follow_redirects=False)
    assert resp.status_code == 200


def test_activity_detail_non_participant(client, db):
    # User A creates activity
    user_a = _create_and_login(client, db, email="detail_npart_a@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)

    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=45,
        sport_type="Laufen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    # User B has NO participation
    client.post("/auth/logout")
    user_b = User(email="detail_npart_b@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "detail_npart_b@test.com", "password": "testpass123"})

    resp = client.get(f"/challenge-activities/{activity_id}", follow_redirects=False)
    assert resp.status_code == 302


# --- Upload-Tests ---

def test_log_activity_with_image(client, db):
    user = _create_and_login(client, db, email="upload_img@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Laufen",
            "media": (BytesIO(b"fake jpeg content"), "foto.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    media = db.session.execute(
        db.select(ActivityMedia).where(ActivityMedia.activity_id == activity.id)
    ).scalars().all()
    assert len(media) == 1
    assert media[0].media_type == "image"
    assert media[0].original_filename == "foto.jpg"


def test_log_activity_with_video(client, db):
    user = _create_and_login(client, db, email="upload_vid@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Radfahren",
            "media": (BytesIO(b"fake mp4 content"), "clip.mp4"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    media = db.session.execute(
        db.select(ActivityMedia).where(ActivityMedia.activity_id == activity.id)
    ).scalars().all()
    assert len(media) == 1
    assert media[0].media_type == "video"


def test_log_activity_invalid_format(client, db):
    user = _create_and_login(client, db, email="upload_invalid@test.com")
    _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Schwimmen",
            "media": (BytesIO(b"fake bmp"), "photo.bmp"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    # Flash + Redirect zurück zu log_form
    assert resp.status_code == 302
    # Keine Activity angelegt
    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is None


def test_log_activity_no_file(client, db):
    user = _create_and_login(client, db, email="upload_nofile@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Yoga",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.media == []


def test_add_media_get(client, db):
    user = _create_and_login(client, db, email="addmedia_get@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="Joggen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()

    resp = client.get(f"/challenge-activities/{activity.id}/media/add", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Medien hinzuf" in resp.data


def test_add_media_post(client, db):
    user = _create_and_login(client, db, email="addmedia_post@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="Joggen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    resp = client.post(
        f"/challenge-activities/{activity_id}/media/add",
        data={"media": (BytesIO(b"fake png"), "bild.png")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302

    media = db.session.execute(
        db.select(ActivityMedia).where(ActivityMedia.activity_id == activity_id)
    ).scalars().all()
    assert len(media) == 1
    assert media[0].media_type == "image"


def test_add_media_non_owner_redirected(client, db):
    user_a = _create_and_login(client, db, email="addmedia_owner@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)

    activity = Activity(
        user_id=user_a.id,
        challenge_id=challenge.id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="Joggen",
        source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id

    client.post("/auth/logout")
    user_b = User(email="addmedia_other@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "addmedia_other@test.com", "password": "testpass123"})

    resp = client.get(f"/challenge-activities/{activity_id}/media/add", follow_redirects=False)
    assert resp.status_code == 302


def _create_activity_with_media(db, user_id, challenge_id):
    activity = Activity(
        user_id=user_id,
        challenge_id=challenge_id,
        activity_date=date.today(),
        duration_minutes=30,
        sport_type="Joggen",
        source="manual",
    )
    db.session.add(activity)
    db.session.flush()
    media = ActivityMedia(
        activity_id=activity.id,
        file_path="uploads/fake_test.jpg",
        media_type="image",
        original_filename="fake_test.jpg",
        file_size_bytes=0,
    )
    db.session.add(media)
    db.session.commit()
    return activity, media


def test_delete_media_happy_path(client, db):
    user = _create_and_login(client, db, email="delmedia_owner@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    activity, media = _create_activity_with_media(db, user.id, challenge.id)

    resp = client.post(
        f"/challenge-activities/{activity.id}/media/{media.id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.session.get(ActivityMedia, media.id) is None


def test_delete_media_non_owner_redirected(client, db):
    user_a = _create_and_login(client, db, email="delmedia_ownerA@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)
    activity, media = _create_activity_with_media(db, user_a.id, challenge.id)

    client.post("/auth/logout")
    user_b = User(email="delmedia_otherB@test.com", is_approved=True)
    user_b.set_password("testpass123")
    db.session.add(user_b)
    db.session.commit()
    client.post("/auth/login", data={"email": "delmedia_otherB@test.com", "password": "testpass123"})

    resp = client.post(
        f"/challenge-activities/{activity.id}/media/{media.id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "my-week" in resp.headers["Location"]
    assert db.session.get(ActivityMedia, media.id) is not None


def test_delete_media_wrong_activity(client, db):
    user = _create_and_login(client, db, email="delmedia_wrong@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    activity_a, media_a = _create_activity_with_media(db, user.id, challenge.id)
    activity_b, _ = _create_activity_with_media(db, user.id, challenge.id)

    resp = client.post(
        f"/challenge-activities/{activity_b.id}/media/{media_a.id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.session.get(ActivityMedia, media_a.id) is not None
