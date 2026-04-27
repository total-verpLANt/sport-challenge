"""Integration tests for the Garmin import flow."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.connector import ConnectorCredential
from app.models.user import User

MOCK_ACTIVITIES = [
    {
        "startTimeLocal": "2026-04-21 08:30:00",
        "activityName": "Morgenrunde",
        "activityType": {"typeKey": "running"},
        "duration": 3600.0,
        "distance": 10000.0,
    }
]

MOCK_EXT_ID = "garmin:2026-04-21 08:30:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_and_login(client, db, email="import_test@test.com", password="testpass123"):
    user = User(email=email, is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user


def _create_challenge_with_participation(db, user_id, status="accepted"):
    today = date.today()
    challenge = Challenge(
        name="Import Test Challenge",
        start_date=today - timedelta(days=14),
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


def _add_connector(db, user_id):
    cred = ConnectorCredential(
        user_id=user_id,
        provider_type="garmin",
        credentials={"username": "test@test.com", "password": "testpass"},
    )
    db.session.add(cred)
    db.session.commit()
    return cred


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_import_form_redirects_without_connector(client, db):
    """GET /import ohne ConnectorCredential → Redirect zu /connectors/."""
    user = _create_and_login(client, db, email="noconn@test.com")
    _create_challenge_with_participation(db, user.id)

    resp = client.get("/challenge-activities/import", follow_redirects=False)
    assert resp.status_code == 302
    assert "/connectors" in resp.headers["Location"]


def test_import_form_redirects_without_participation(client, db):
    """GET /import ohne aktive Participation → Redirect (nicht 200)."""
    user = _create_and_login(client, db, email="nopart_import@test.com")
    _add_connector(db, user.id)
    # Keine Participation angelegt

    resp = client.get("/challenge-activities/import", follow_redirects=False)
    assert resp.status_code == 302


def test_import_form_shows_activities_with_mock_connector(client, db):
    """GET /import mit gemocktem Connector → HTTP 200 + Aktivitätsname."""
    user = _create_and_login(client, db, email="showact@test.com")
    _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            return_value=MOCK_ACTIVITIES,
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.get("/challenge-activities/import", follow_redirects=False)

    assert resp.status_code == 200
    assert b"Morgenrunde" in resp.data


def test_import_form_marks_already_imported(client, db):
    """GET /import mit bereits importierter Aktivität → 'Bereits importiert' im Body."""
    user = _create_and_login(client, db, email="alreadyimp@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    # Aktivität bereits in DB
    existing = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date(2026, 4, 21),
        duration_minutes=60,
        sport_type="running",
        source="garmin",
        external_id=MOCK_EXT_ID,
    )
    db.session.add(existing)
    db.session.commit()

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            return_value=MOCK_ACTIVITIES,
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.get("/challenge-activities/import", follow_redirects=False)

    assert resp.status_code == 200
    assert "Bereits importiert".encode() in resp.data


def test_import_submit_creates_activity(client, db):
    """POST /import mit gültiger ext_id → Redirect + Activity in DB."""
    user = _create_and_login(client, db, email="submitact@test.com")
    _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            return_value=MOCK_ACTIVITIES,
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.post(
            "/challenge-activities/import",
            data={"selected": [MOCK_EXT_ID]},
            follow_redirects=False,
        )

    assert resp.status_code == 302

    activity = db.session.execute(
        db.select(Activity).where(
            Activity.user_id == user.id,
            Activity.external_id == MOCK_EXT_ID,
        )
    ).scalar_one_or_none()
    assert activity is not None
    assert activity.source == "garmin"
    assert activity.external_id == MOCK_EXT_ID


def test_import_submit_skips_duplicate(client, db):
    """POST /import mit bereits importierter ext_id → kein Duplikat."""
    user = _create_and_login(client, db, email="dupskip@test.com")
    challenge, _ = _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    # Aktivität bereits in DB
    existing = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date(2026, 4, 21),
        duration_minutes=60,
        sport_type="running",
        source="garmin",
        external_id=MOCK_EXT_ID,
    )
    db.session.add(existing)
    db.session.commit()

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            return_value=MOCK_ACTIVITIES,
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.post(
            "/challenge-activities/import",
            data={"selected": [MOCK_EXT_ID]},
            follow_redirects=False,
        )

    assert resp.status_code == 302

    count = db.session.execute(
        db.select(Activity).where(
            Activity.user_id == user.id,
            Activity.external_id == MOCK_EXT_ID,
        )
    ).scalars().all()
    assert len(count) == 1


def test_import_submit_handles_missing_ext_id(client, db):
    """POST /import mit unbekannter ext_id → Redirect, kein Crash, 0 neue Activities."""
    user = _create_and_login(client, db, email="missingext@test.com")
    _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    unknown_ext_id = "garmin:9999-01-01 00:00:00"

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            return_value=MOCK_ACTIVITIES,
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.post(
            "/challenge-activities/import",
            data={"selected": [unknown_ext_id]},
            follow_redirects=False,
        )

    assert resp.status_code == 302

    count = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalars().all()
    assert len(count) == 0


def test_import_submit_handles_connector_error(client, db):
    """POST /import wenn get_activities() eine Exception wirft → kein 500, 0 neue Activities."""
    user = _create_and_login(client, db, email="connectorerr@test.com")
    _create_challenge_with_participation(db, user.id)
    _add_connector(db, user.id)

    with (
        patch("app.connectors.garmin.GarminConnector.connect") as mock_connect,
        patch(
            "app.connectors.garmin.GarminConnector.get_activities",
            side_effect=RuntimeError("API nicht erreichbar"),
        ),
        patch(
            "app.connectors.garmin.GarminConnector.get_token_updates",
            return_value={},
        ),
    ):
        mock_connect.return_value = None
        resp = client.post(
            "/challenge-activities/import",
            data={"selected": [MOCK_EXT_ID]},
            follow_redirects=False,
        )

    # Exception-Handler gibt Flash + Redirect zurück – kein ungefangener 500er
    assert resp.status_code == 302

    count = db.session.execute(
        db.select(Activity).where(Activity.user_id == user.id)
    ).scalars().all()
    assert len(count) == 0
