"""Tests für StravaConnector und Strava OAuth2-Routen.

Abgedeckte Fälle:
1. StravaConnector ist im PROVIDER_REGISTRY unter "strava" registriert
2. StravaConnector.connect() nutzt bestehenden Token (kein Refresh nötig)
3. StravaConnector.connect() refresht abgelaufenen Token
4. get_token_updates() gibt leeres Dict zurück wenn kein Refresh
5. get_token_updates() gibt neue Token-Daten zurück nach Refresh
6. get_activities() gibt konvertierte Aktivitätsliste zurück
7. get_activities() wirft RuntimeError ohne vorheriges connect()
8. disconnect() setzt Client und Token-Daten zurück
9. OAuth-Callback: ungültiger State → Flash + Redirect
10. OAuth-Callback: erfolgreicher Code-Exchange → ConnectorCredential in DB
"""
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.connectors import PROVIDER_REGISTRY
from app.connectors.strava import StravaConnector
from app.models.connector import ConnectorCredential
from app.models.user import User


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _valid_credentials(expires_offset=3600):
    """Erstellt gültige Strava-Credentials (nicht abgelaufen)."""
    return {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": int(time.time()) + expires_offset,
    }


def _expired_credentials():
    """Erstellt abgelaufene Strava-Credentials."""
    return {
        "access_token": "old_access_token",
        "refresh_token": "old_refresh_token",
        "expires_at": int(time.time()) - 3600,  # vor einer Stunde abgelaufen
    }


def _login_user(client, db):
    """Legt Testuser an, genehmigt ihn und loggt ihn ein."""
    user = User(email="strava@example.com")
    user.set_password("password123")
    user.is_approved = True
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": "strava@example.com", "password": "password123"})
    return user


# ---------------------------------------------------------------------------
# 1. PROVIDER_REGISTRY
# ---------------------------------------------------------------------------

def test_strava_registered_in_provider_registry():
    """StravaConnector muss unter dem Key 'strava' im PROVIDER_REGISTRY stehen."""
    assert "strava" in PROVIDER_REGISTRY
    assert PROVIDER_REGISTRY["strava"] is StravaConnector


# ---------------------------------------------------------------------------
# 2. connect() – gültiger Token, kein Refresh
# ---------------------------------------------------------------------------

def test_strava_connector_connect_uses_existing_valid_token():
    """connect() mit gültigem expires_at → kein Refresh, Client wird gesetzt."""
    connector = StravaConnector(user_id=1)
    creds = _valid_credentials()

    with patch("app.connectors.strava.Client") as MockClient:
        connector.connect(creds)
        # Kein refresh_access_token-Aufruf
        MockClient.return_value.refresh_access_token.assert_not_called()
        assert connector._client is not None


# ---------------------------------------------------------------------------
# 3. connect() – abgelaufener Token → Refresh
# ---------------------------------------------------------------------------

def test_strava_connector_connect_refreshes_expired_token(app):
    """connect() mit abgelaufenem expires_at → refresh_access_token() aufgerufen."""
    connector = StravaConnector(user_id=1)
    creds = _expired_credentials()

    new_token_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_at": int(time.time()) + 21600,
    }

    with app.app_context():
        app.config["STRAVA_CLIENT_ID"] = "test_client_id"
        app.config["STRAVA_CLIENT_SECRET"] = "test_client_secret"
        with patch("app.connectors.strava.Client") as MockClient:
            MockClient.return_value.refresh_access_token.return_value = new_token_response
            connector.connect(creds)
            MockClient.return_value.refresh_access_token.assert_called_once()


# ---------------------------------------------------------------------------
# 4. get_token_updates() – kein Refresh → leeres Dict
# ---------------------------------------------------------------------------

def test_strava_connector_get_token_updates_empty_without_refresh():
    """get_token_updates() gibt leeres Dict zurück wenn kein Refresh nötig."""
    connector = StravaConnector(user_id=1)
    creds = _valid_credentials()

    with patch("app.connectors.strava.Client"):
        connector.connect(creds)

    assert connector.get_token_updates() == {}


# ---------------------------------------------------------------------------
# 5. get_token_updates() – nach Refresh → neue Token-Daten
# ---------------------------------------------------------------------------

def test_strava_connector_get_token_updates_after_refresh(app):
    """get_token_updates() gibt neue Tokens zurück nach Refresh."""
    connector = StravaConnector(user_id=1)
    creds = _expired_credentials()

    new_token_response = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_at": int(time.time()) + 21600,
    }

    with app.app_context():
        app.config["STRAVA_CLIENT_ID"] = "test_client_id"
        app.config["STRAVA_CLIENT_SECRET"] = "test_client_secret"
        with patch("app.connectors.strava.Client") as MockClient:
            MockClient.return_value.refresh_access_token.return_value = new_token_response
            connector.connect(creds)

    updates = connector.get_token_updates()
    assert updates["access_token"] == "new_access_token"
    assert updates["refresh_token"] == "new_refresh_token"
    assert "expires_at" in updates


# ---------------------------------------------------------------------------
# 6. get_activities() – konvertierte Liste
# ---------------------------------------------------------------------------

def test_strava_connector_get_activities_returns_mapped_list():
    """get_activities() gibt Liste mit internem Dict-Format zurück."""
    connector = StravaConnector(user_id=1)
    creds = _valid_credentials()

    mock_activity = MagicMock()
    mock_activity.start_date_local = datetime(2026, 4, 25, 10, 0, 0)
    mock_activity.name = "Morgenrunde"
    mock_activity.type = "Run"
    mock_activity.elapsed_time.total_seconds.return_value = 3600.0
    mock_activity.distance = 10000.0
    mock_activity.average_heartrate = 145
    mock_activity.calories = 600

    with patch("app.connectors.strava.Client") as MockClient:
        MockClient.return_value.get_activities.return_value = [mock_activity]
        connector.connect(creds)
        result = connector.get_activities(datetime(2026, 4, 21), datetime(2026, 4, 27))

    assert len(result) == 1
    assert result[0]["activityName"] == "Morgenrunde"
    assert result[0]["duration"] == 3600.0
    assert result[0]["distance"] == 10000.0


# ---------------------------------------------------------------------------
# 7. get_activities() – RuntimeError ohne connect()
# ---------------------------------------------------------------------------

def test_strava_connector_get_activities_raises_without_connect():
    """get_activities() ohne connect() → RuntimeError."""
    connector = StravaConnector(user_id=1)
    with pytest.raises(RuntimeError, match="nicht verbunden"):
        connector.get_activities(datetime(2026, 4, 21), datetime(2026, 4, 27))


# ---------------------------------------------------------------------------
# 8. disconnect()
# ---------------------------------------------------------------------------

def test_strava_connector_disconnect_clears_state():
    """disconnect() setzt _client=None und _token_data={}."""
    connector = StravaConnector(user_id=1)
    creds = _valid_credentials()

    with patch("app.connectors.strava.Client"):
        connector.connect(creds)

    assert connector._client is not None
    connector.disconnect()
    assert connector._client is None
    assert connector._token_data == {}


# ---------------------------------------------------------------------------
# 9. OAuth-Callback – ungültiger State
# ---------------------------------------------------------------------------

def test_oauth_callback_rejects_invalid_state(client, db):
    """GET /connectors/strava/oauth/callback?state=FALSCH → Flash + Redirect."""
    user = _login_user(client, db)

    with client.session_transaction() as sess:
        sess["strava_oauth_state"] = "correct_state"

    response = client.get(
        "/connectors/strava/oauth/callback?code=abc&state=WRONG_STATE",
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("Ungültiger OAuth-State" in msg for _, msg in flashes)


# ---------------------------------------------------------------------------
# 10. OAuth-Callback – erfolgreicher Code-Exchange
# ---------------------------------------------------------------------------

def test_oauth_callback_stores_credential_on_success(app, client, db):
    """OAuth-Callback mit korrektem State + Code → ConnectorCredential in DB."""
    app.config["STRAVA_CLIENT_ID"] = "test_client_id"
    app.config["STRAVA_CLIENT_SECRET"] = "test_client_secret"
    user = _login_user(client, db)

    correct_state = "test_state_12345"
    with client.session_transaction() as sess:
        sess["strava_oauth_state"] = correct_state

    mock_token_response = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",
        "expires_at": int(time.time()) + 21600,
    }

    with patch("app.routes.strava_oauth.Client") as MockClient:
        MockClient.return_value.exchange_code_for_token.return_value = mock_token_response

        response = client.get(
            f"/connectors/strava/oauth/callback?code=authcode&state={correct_state}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    cred = ConnectorCredential.query.filter_by(
        user_id=user.id, provider_type="strava"
    ).first()
    assert cred is not None
    assert cred.credentials["access_token"] == "new_access"
