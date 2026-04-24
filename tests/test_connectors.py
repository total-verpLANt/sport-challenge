"""Tests für Connector-Architektur.

Abgedeckte Fälle:
1. BaseConnector kann nicht direkt instanziiert werden (ABC)
2. GarminConnector ist im PROVIDER_REGISTRY unter "garmin" registriert
3. GarminConnector.connect() nutzt login() beim Erstlogin (kein _garmin_tokens)
4. GarminConnector.connect() nutzt reconnect() wenn _garmin_tokens vorhanden
5. get_fresh_token_json() gibt Token-String nach connect() zurück
6. disconnect() setzt _client und _current_token_json auf None
7. GarminClient.login() gibt Token-JSON-String zurück (gemockt)
8. GarminClient.reconnect() übergibt Token-String an Garmin.login()
9. FernetField verschlüsselt beim Schreiben und entschlüsselt beim Lesen
"""
from unittest.mock import MagicMock, patch

import pytest

from app.connectors import PROVIDER_REGISTRY
from app.connectors.base import BaseConnector
from app.connectors.garmin import GarminConnector
from app.garmin.client import GarminClient
from app.utils.crypto import FernetField


# ---------------------------------------------------------------------------
# 1. BaseConnector ist abstract
# ---------------------------------------------------------------------------


def test_base_connector_abstract():
    """BaseConnector darf nicht direkt instanziiert werden (hat @abstractmethod)."""
    with pytest.raises(TypeError):
        BaseConnector()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# 2. PROVIDER_REGISTRY enthält GarminConnector
# ---------------------------------------------------------------------------


def test_registry_registers_provider():
    """GarminConnector muss unter dem Key 'garmin' im PROVIDER_REGISTRY stehen."""
    assert "garmin" in PROVIDER_REGISTRY
    assert PROVIDER_REGISTRY["garmin"] is GarminConnector


# ---------------------------------------------------------------------------
# 3. GarminConnector.connect() – Erstlogin-Pfad
# ---------------------------------------------------------------------------


def test_garmin_connector_connect_triggers_login_on_first_connect():
    """connect() ohne _garmin_tokens ruft GarminClient.login() auf."""
    connector = GarminConnector(user_id=1)
    fake_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.connectors.garmin.GarminClient") as MockClient:
        instance = MockClient.return_value
        instance.login.return_value = fake_token

        connector.connect({"email": "test@example.com", "password": "secret"})

        instance.login.assert_called_once_with(
            email="test@example.com", password="secret"
        )
        instance.reconnect.assert_not_called()


# ---------------------------------------------------------------------------
# 4. GarminConnector.connect() – Reconnect-Pfad
# ---------------------------------------------------------------------------


def test_garmin_connector_connect_uses_reconnect_with_existing_tokens():
    """connect() mit _garmin_tokens ruft GarminClient.reconnect() auf."""
    connector = GarminConnector(user_id=1)
    stored_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.connectors.garmin.GarminClient") as MockClient:
        instance = MockClient.return_value
        instance.reconnect.return_value = stored_token

        connector.connect({
            "email": "test@example.com",
            "password": "secret",
            "_garmin_tokens": stored_token,
        })

        instance.reconnect.assert_called_once_with(stored_token)
        instance.login.assert_not_called()


# ---------------------------------------------------------------------------
# 5. get_fresh_token_json() nach connect()
# ---------------------------------------------------------------------------


def test_garmin_connector_get_fresh_token_json_after_connect():
    """get_fresh_token_json() gibt Token-String zurück nach connect()."""
    connector = GarminConnector(user_id=1)
    fake_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.connectors.garmin.GarminClient") as MockClient:
        instance = MockClient.return_value
        instance.login.return_value = fake_token

        connector.connect({"email": "u@example.com", "password": "pw"})
        result = connector.get_fresh_token_json()

    assert result == fake_token


# ---------------------------------------------------------------------------
# 6. disconnect() räumt auf
# ---------------------------------------------------------------------------


def test_garmin_connector_disconnect_clears_client():
    """disconnect() setzt _client und _current_token_json auf None."""
    connector = GarminConnector(user_id=1)
    fake_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.connectors.garmin.GarminClient") as MockClient:
        instance = MockClient.return_value
        instance.login.return_value = fake_token
        connector.connect({"email": "u@example.com", "password": "pw"})

    assert connector._client is not None
    connector.disconnect()
    assert connector._client is None
    assert connector._current_token_json is None


# ---------------------------------------------------------------------------
# 7. GarminClient.login() gibt Token-JSON zurück
# ---------------------------------------------------------------------------


def test_garmin_client_login_returns_token_json():
    """GarminClient.login() gibt den serialisierten Token-String zurück."""
    fake_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.garmin.client.Garmin") as MockGarmin:
        mock_api = MockGarmin.return_value
        mock_api.client.dumps.return_value = fake_token

        client = GarminClient()
        result = client.login("user@example.com", "password")

    assert result == fake_token
    mock_api.login.assert_called_once()


# ---------------------------------------------------------------------------
# 8. GarminClient.reconnect() übergibt Token-String direkt
# ---------------------------------------------------------------------------


def test_garmin_client_reconnect_uses_token_string():
    """GarminClient.reconnect() ruft Garmin().login(tokenstore=token_json) auf."""
    stored_token = '{"di_token": "tok", "di_refresh_token": "ref", "di_client_id": "id"}'

    with patch("app.garmin.client.Garmin") as MockGarmin:
        mock_api = MockGarmin.return_value
        mock_api.client.dumps.return_value = stored_token

        client = GarminClient()
        result = client.reconnect(stored_token)

    mock_api.login.assert_called_once_with(tokenstore=stored_token)
    assert result == stored_token


# ---------------------------------------------------------------------------
# 9. FernetField: Verschlüsselung beim Schreiben, Entschlüsselung beim Lesen
# ---------------------------------------------------------------------------


def test_credential_fernet_roundtrip():
    """FernetField verschlüsselt den Klartext und gibt ihn entschlüsselt zurück."""
    secret_key = "test-secret-key-not-for-production"
    plaintext = "super-secret-password"

    field = FernetField(secret_key)

    encrypted = field.process_bind_param(plaintext, dialect=None)
    assert encrypted is not None
    assert encrypted != plaintext

    decrypted = field.process_result_value(encrypted, dialect=None)
    assert decrypted == plaintext
