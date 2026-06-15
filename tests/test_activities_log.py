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


def _create_two_active_challenges(db, user_id):
    """Zwei aktive, ueberlappende Challenges + je accepted Participation. Gibt (cA, pA, cB, pB)."""
    today = date.today()
    ca = Challenge(name="Challenge A", start_date=today - timedelta(days=7),
                   end_date=today + timedelta(days=30), penalty_per_miss=5.0,
                   bailout_fee=25.0, created_by_id=user_id)
    cb = Challenge(name="Challenge B", start_date=today - timedelta(days=3),
                   end_date=today + timedelta(days=20), penalty_per_miss=5.0,
                   bailout_fee=25.0, created_by_id=user_id)
    db.session.add_all([ca, cb])
    db.session.commit()
    pa = ChallengeParticipation(user_id=user_id, challenge_id=ca.id, status="accepted")
    pb = ChallengeParticipation(user_id=user_id, challenge_id=cb.id, status="accepted")
    db.session.add_all([pa, pb])
    db.session.commit()
    return ca, pa, cb, pb


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

def test_log_activity_with_image(client, db, sample_jpeg_bytes):
    user = _create_and_login(client, db, email="upload_img@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Laufen",
            "media": (BytesIO(sample_jpeg_bytes), "foto.jpg"),
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


def test_log_activity_with_video(client, db, sample_mp4_bytes):
    user = _create_and_login(client, db, email="upload_vid@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Radfahren",
            "media": (BytesIO(sample_mp4_bytes), "clip.mp4"),
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


def test_add_media_post(client, db, sample_png_bytes):
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
        data={"media": (BytesIO(sample_png_bytes), "bild.png")},
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


def test_log_activity_with_notes(client, db):
    user = _create_and_login(client, db, email="notes_yes@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "45",
            "sport_type": "Laufen",
            "notes": "Gutes Training, leichter Wind, Knie hat nicht gezwickt.",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.notes == "Gutes Training, leichter Wind, Knie hat nicht gezwickt."


def test_log_activity_without_notes(client, db):
    user = _create_and_login(client, db, email="notes_no@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Schwimmen",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.notes is None


def test_log_activity_notes_too_long(client, db):
    user = _create_and_login(client, db, email="notes_toolong@test.com")
    _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "30",
            "sport_type": "Yoga",
            "notes": "x" * 2001,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is None


# --- SickPeriod Delete Tests ---

def test_delete_sick_period_own(client, db):
    """User kann eigene Krankmeldung löschen."""
    from app.models.sick_period import SickPeriod
    from datetime import date
    user = _create_and_login(client, db, email="sw_delete@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    sp = SickPeriod(user_id=user.id, challenge_id=challenge.id,
                    start_date=date.today() - timedelta(days=7),
                    end_date=date.today() - timedelta(days=5))
    db.session.add(sp)
    db.session.commit()
    sp_id = sp.id

    resp = client.post(f"/challenge-activities/sick-period/{sp_id}/delete",
                       follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(SickPeriod, sp_id) is None


def test_delete_sick_period_other_user_rejected(client, db):
    """User B kann Krankmeldung von User A nicht löschen."""
    from app.models.sick_period import SickPeriod
    from datetime import date
    # User A erstellt Krankmeldung
    user_a = _create_and_login(client, db, email="sw_a@test.com")
    challenge, _ = _create_challenge_with_participation(db, user_a.id)
    sp = SickPeriod(user_id=user_a.id, challenge_id=challenge.id,
                    start_date=date.today() - timedelta(days=7),
                    end_date=date.today() - timedelta(days=5))
    db.session.add(sp)
    db.session.commit()
    sp_id = sp.id
    # User B einloggen (explizit ausloggen vorher – Flask-Login ersetzt Session sonst nicht)
    client.post("/auth/logout")
    _create_and_login(client, db, email="sw_b@test.com")

    resp = client.post(f"/challenge-activities/sick-period/{sp_id}/delete",
                       follow_redirects=False)
    assert resp.status_code == 403
    assert db.session.get(SickPeriod, sp_id) is not None  # Noch vorhanden!


def test_admin_deletes_sick_period_of_other_user(client, db):
    """Admin kann fremde Krankmeldung löschen."""
    from app.models.sick_period import SickPeriod
    from app.models.user import User
    from datetime import date
    # User erstellt Krankmeldung
    user = _create_and_login(client, db, email="sw_victim@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    sp = SickPeriod(user_id=user.id, challenge_id=challenge.id,
                    start_date=date.today() - timedelta(days=7),
                    end_date=date.today() - timedelta(days=5))
    db.session.add(sp)
    db.session.commit()
    sp_id = sp.id
    # Admin einloggen
    admin = _create_and_login(client, db, email="sw_admin@test.com")
    admin.role = "admin"
    db.session.commit()

    resp = client.post(f"/challenge-activities/sick-period/{sp_id}/delete",
                       follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(SickPeriod, sp_id) is None  # Gelöscht!


def test_admin_deletes_others_activity(client, db):
    """Admin kann fremde Aktivität löschen."""
    from app.models.activity import Activity
    from datetime import date
    # User erstellt Aktivität
    user = _create_and_login(client, db, email="act_victim@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    activity = Activity(
        user_id=user.id, challenge_id=challenge.id,
        activity_date=date.today(), duration_minutes=30,
        sport_type="cycling", source="manual",
    )
    db.session.add(activity)
    db.session.commit()
    activity_id = activity.id
    # Admin einloggen
    admin = _create_and_login(client, db, email="act_admin@test.com")
    admin.role = "admin"
    db.session.commit()

    resp = client.post(f"/challenge-activities/{activity_id}/delete",
                       follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(Activity, activity_id) is None  # Gelöscht!


def test_edit_notes_saves(client, db):
    """Notiz wird über die edit_notes-Route auf der Detailseite gespeichert."""
    user = _create_and_login(client, db, email="notes_save@test.com")
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
        f"/challenge-activities/{activity_id}/notes",
        data={"notes": "Toller Lauf heute"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db.session.expire_all()
    assert db.session.get(Activity, activity_id).notes == "Toller Lauf heute"


def test_edit_notes_too_long(client, db):
    """Notiz mit mehr als 2000 Zeichen wird abgelehnt."""
    user = _create_and_login(client, db, email="notes_long@test.com")
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
        f"/challenge-activities/{activity_id}/notes",
        data={"notes": "x" * 2001},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db.session.expire_all()
    assert db.session.get(Activity, activity_id).notes is None


# --- Multi-Challenge Routing Tests (log_submit) ---

def test_log_submit_routes_to_selected_challenge(client, db):
    """Bei 2 aktiven Challenges landet die Aktivität in der GEWÄHLTEN (cb), nicht cA."""
    user = _create_and_login(client, db, email="mc_route@test.com")
    ca, _, cb, _ = _create_two_active_challenges(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "challenge_id": str(cb.id),
            "activity_date": date.today().isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.challenge_id == cb.id
    assert activity.challenge_id != ca.id


def test_log_submit_rejects_foreign_challenge(client, db):
    """challenge_id einer Challenge ohne accepted-Teilnahme → keine Activity, Redirect."""
    user = _create_and_login(client, db, email="mc_foreign@test.com")
    _create_challenge_with_participation(db, user.id)  # cA accepted

    today = date.today()
    foreign = Challenge(
        name="Foreign Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user.id,
    )
    db.session.add(foreign)
    db.session.commit()
    # Nur "invited", nicht accepted
    db.session.add(ChallengeParticipation(
        user_id=user.id, challenge_id=foreign.id, status="invited",
    ))
    db.session.commit()

    resp = client.post(
        "/challenge-activities/log",
        data={
            "challenge_id": str(foreign.id),
            "activity_date": today.isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert Activity.query.count() == 0


def test_log_submit_missing_challenge_id_with_multiple(client, db):
    """2 aktive Challenges, kein challenge_id → keine Activity, Redirect (Flash)."""
    user = _create_and_login(client, db, email="mc_missing@test.com")
    _create_two_active_challenges(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert Activity.query.count() == 0


def test_log_submit_single_challenge_no_field_still_works(client, db):
    """1 Teilnahme, kein challenge_id-Feld → Activity wird angelegt (Rückwärtskompat)."""
    user = _create_and_login(client, db, email="mc_single@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    resp = client.post(
        "/challenge-activities/log",
        data={
            "activity_date": date.today().isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.challenge_id == challenge.id


def test_log_submit_non_overlapping_periods(client, db):
    """cA beendet (Vergangenheit), cB aktiv; POST mit cb.id + heutigem Datum → Activity in cb."""
    user = _create_and_login(client, db, email="mc_nonoverlap@test.com")
    today = date.today()
    ca = Challenge(
        name="Past Challenge",
        start_date=today - timedelta(days=30),
        end_date=today - timedelta(days=1),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user.id,
    )
    cb = Challenge(
        name="Current Challenge",
        start_date=today,
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user.id,
    )
    db.session.add_all([ca, cb])
    db.session.commit()
    db.session.add_all([
        ChallengeParticipation(user_id=user.id, challenge_id=ca.id, status="accepted"),
        ChallengeParticipation(user_id=user.id, challenge_id=cb.id, status="accepted"),
    ])
    db.session.commit()

    resp = client.post(
        "/challenge-activities/log",
        data={
            "challenge_id": str(cb.id),
            "activity_date": today.isoformat(),
            "duration_minutes": "45",
            "sport_type": "running",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.challenge_id == cb.id


# --- SickPeriod POST Tests (sick_period_submit) ---

def test_sick_period_submit_creates(client, db):
    """1 Teilnahme; POST /sick-period innerhalb Periode → SickPeriod angelegt, geclamped."""
    from app.models.sick_period import SickPeriod
    user = _create_and_login(client, db, email="sp_create@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    # sick_from VOR Challenge-Start → muss auf challenge.start_date geclamped werden
    sick_from = challenge.start_date - timedelta(days=3)
    sick_to = challenge.start_date + timedelta(days=2)

    resp = client.post(
        "/challenge-activities/sick-period",
        data={
            "sick_from": sick_from.isoformat(),
            "sick_to": sick_to.isoformat(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    sp = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == user.id)
    ).scalar_one_or_none()
    assert sp is not None
    assert sp.challenge_id == challenge.id
    assert sp.start_date == challenge.start_date  # geclamped
    assert sp.end_date == sick_to


def test_sick_period_submit_routes_to_selected_challenge(client, db):
    """2 aktive; POST /sick-period mit challenge_id=cb.id → SickPeriod in cb."""
    from app.models.sick_period import SickPeriod
    user = _create_and_login(client, db, email="sp_route@test.com")
    ca, _, cb, _ = _create_two_active_challenges(db, user.id)

    sick_from = date.today()
    sick_to = date.today() + timedelta(days=2)

    resp = client.post(
        "/challenge-activities/sick-period",
        data={
            "challenge_id": str(cb.id),
            "sick_from": sick_from.isoformat(),
            "sick_to": sick_to.isoformat(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    sp = db.session.execute(
        db.select(SickPeriod).where(SickPeriod.user_id == user.id)
    ).scalar_one_or_none()
    assert sp is not None
    assert sp.challenge_id == cb.id
    assert sp.challenge_id != ca.id


def test_sick_period_submit_overlap_rejected(client, db):
    """Zweite überlappende Periode wird abgelehnt → nur 1 SickPeriod in DB."""
    from app.models.sick_period import SickPeriod
    user = _create_and_login(client, db, email="sp_overlap@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)

    sick_from = date.today()
    sick_to = date.today() + timedelta(days=4)

    resp1 = client.post(
        "/challenge-activities/sick-period",
        data={
            "sick_from": sick_from.isoformat(),
            "sick_to": sick_to.isoformat(),
        },
        follow_redirects=False,
    )
    assert resp1.status_code == 302
    assert SickPeriod.query.filter_by(user_id=user.id).count() == 1

    # Überlappende zweite Periode
    resp2 = client.post(
        "/challenge-activities/sick-period",
        data={
            "sick_from": (sick_from + timedelta(days=2)).isoformat(),
            "sick_to": (sick_to + timedelta(days=2)).isoformat(),
        },
        follow_redirects=False,
    )
    assert resp2.status_code == 302
    assert SickPeriod.query.filter_by(user_id=user.id).count() == 1


# ---------------------------------------------------------------------------
# 0bv.2: my_week-Anzeige mit Challenge-Selektor
# ---------------------------------------------------------------------------
def test_my_week_selector_shows_selected_challenge(client, db):
    """Bei 2 aktiven Challenges zeigt my_week NUR die Aktivitäten der via
    ?challenge_id gewählten Challenge – nichts 'verschwindet', es wird nur
    pro Challenge getrennt angezeigt."""
    user = _create_and_login(client, db, email="myweek_sel@test.com")
    ca, _, cb, _ = _create_two_active_challenges(db, user.id)
    today = date.today()
    db.session.add_all([
        Activity(user_id=user.id, challenge_id=ca.id, activity_date=today,
                 duration_minutes=45, sport_type="schwimmen_aaa", source="manual"),
        Activity(user_id=user.id, challenge_id=cb.id, activity_date=today,
                 duration_minutes=45, sport_type="radeln_bbb", source="manual"),
    ])
    db.session.commit()

    # Challenge A gewählt -> nur A-Aktivität, B-Aktivität ausgeblendet
    resp = client.get(f"/challenge-activities/my-week?challenge_id={ca.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "schwimmen_aaa" in body
    assert "radeln_bbb" not in body
    # Selektor listet beide Challenges
    assert "Challenge A" in body
    assert "Challenge B" in body

    # Challenge B gewählt -> nur B-Aktivität
    resp = client.get(f"/challenge-activities/my-week?challenge_id={cb.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "radeln_bbb" in body
    assert "schwimmen_aaa" not in body


def test_my_week_invalid_challenge_id_falls_back_to_default(client, db):
    """Manipuliertes/fremdes challenge_id darf nicht crashen – Default greift."""
    user = _create_and_login(client, db, email="myweek_bad@test.com")
    ca, _, cb, _ = _create_two_active_challenges(db, user.id)
    today = date.today()
    db.session.add(Activity(user_id=user.id, challenge_id=cb.id, activity_date=today,
                            duration_minutes=45, sport_type="radeln_default", source="manual"))
    db.session.commit()

    # cb ist Default (spaeteres start_date -> in _accepted_participations zuerst)
    resp = client.get("/challenge-activities/my-week?challenge_id=999999")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "radeln_default" in body  # Default = cb, kein Crash

    # Nicht-numerischer Wert ebenfalls unkritisch
    resp = client.get("/challenge-activities/my-week?challenge_id=abc")
    assert resp.status_code == 200


def test_my_week_single_challenge_no_selector(client, db):
    """Bei genau 1 Teilnahme erscheint KEIN Selektor (kein UX-Regress)."""
    user = _create_and_login(client, db, email="myweek_single@test.com")
    _create_challenge_with_participation(db, user.id)
    resp = client.get("/challenge-activities/my-week")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="challenge_select"' not in body
