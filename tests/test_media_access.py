"""Tests für die login-geschützte Medien-Auslieferung (Issue 1ye).

Deckt ab:
- Anonyme Direktzugriffe auf Medien werden abgewiesen (302 zum Login).
- Eingeloggte Nutzer erhalten den Dateiinhalt + Härtungs-Header.
- Der alte static/uploads-Pfad liefert keine Upload-Dateien mehr (ActivityMedia
  UND Bonus-Video sind dadurch nicht mehr anonym abrufbar).
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models.activity import Activity, ActivityMedia
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User

# Minimales gültiges PNG (1x1, transparent) – Inhalt egal, Hauptsache erkennbar.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def _login(client, db, email="media@test.com", password="testpass123"):
    user = User(email=email, is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def _write_upload(app, filename: str) -> None:
    upload_dir = Path(app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / filename).write_bytes(_PNG_BYTES)


def _make_activity_with_media(db, user_id):
    today = date.today()
    challenge = Challenge(
        name="Media Test Challenge",
        start_date=today - timedelta(days=7),
        end_date=today + timedelta(days=30),
        penalty_per_miss=5.0,
        bailout_fee=25.0,
        created_by_id=user_id,
    )
    db.session.add(challenge)
    db.session.commit()
    db.session.add(
        ChallengeParticipation(user_id=user_id, challenge_id=challenge.id, status="accepted")
    )
    activity = Activity(
        user_id=user_id,
        challenge_id=challenge.id,
        activity_date=today,
        duration_minutes=45,
        sport_type="Laufen",
        screenshot_path="uploads/shot_abc123.png",
    )
    db.session.add(activity)
    db.session.commit()
    media = ActivityMedia(
        activity_id=activity.id,
        file_path="uploads/media_def456.png",
        media_type="image",
        original_filename="beweis.png",
        file_size_bytes=len(_PNG_BYTES),
    )
    db.session.add(media)
    db.session.commit()
    return activity, media


class TestAnonymousBlocked:
    def test_activity_media_anonymous_redirects_to_login(self, client, app, db):
        user = User(email="owner@test.com", is_approved=True)
        user.set_password("pass12345")
        db.session.add(user)
        db.session.commit()
        _activity, media = _make_activity_with_media(db, user.id)
        _write_upload(app, "media_def456.png")

        resp = client.get(f"/media/activity/{media.id}", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]
        # Kein Dateiinhalt im Redirect-Body
        assert _PNG_BYTES not in resp.data

    def test_screenshot_anonymous_redirects_to_login(self, client, app, db):
        user = User(email="owner2@test.com", is_approved=True)
        user.set_password("pass12345")
        db.session.add(user)
        db.session.commit()
        activity, _media = _make_activity_with_media(db, user.id)
        _write_upload(app, "shot_abc123.png")

        resp = client.get(f"/media/screenshot/{activity.id}", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


class TestAuthenticatedAllowed:
    def test_activity_media_served_to_logged_in_user(self, client, app, db):
        user = _login(client, db)
        _activity, media = _make_activity_with_media(db, user.id)
        _write_upload(app, "media_def456.png")

        resp = client.get(f"/media/activity/{media.id}")
        assert resp.status_code == 200
        assert resp.data == _PNG_BYTES
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert "private" in resp.headers.get("Cache-Control", "")

    def test_screenshot_served_to_logged_in_user(self, client, app, db):
        user = _login(client, db)
        activity, _media = _make_activity_with_media(db, user.id)
        _write_upload(app, "shot_abc123.png")

        resp = client.get(f"/media/screenshot/{activity.id}")
        assert resp.status_code == 200
        assert resp.data == _PNG_BYTES

    def test_unknown_media_id_returns_404(self, client, db):
        _login(client, db)
        resp = client.get("/media/activity/999999")
        assert resp.status_code == 404


class TestStaticPathNoLongerServesUploads:
    def test_static_uploads_path_returns_404(self, client, app, db):
        """Der alte öffentliche static-Pfad darf keine Uploads mehr ausliefern.

        Deckt sowohl ActivityMedia als auch Bonus-Videos ab: Dateien liegen nicht
        mehr unter app/static/uploads, also liefert die static-Route 404.
        """
        # Selbst wenn eine Datei im (neuen) Upload-Verzeichnis existiert ...
        _write_upload(app, "media_def456.png")
        # ... ist sie über den static-Pfad nicht erreichbar.
        resp = client.get("/static/uploads/media_def456.png")
        assert resp.status_code == 404
        resp_video = client.get("/static/uploads/bonus_clip.mp4")
        assert resp_video.status_code == 404
