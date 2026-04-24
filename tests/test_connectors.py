"""Tests für Connector-Architektur (I-25).

Abgedeckte Fälle:
1. BaseConnector kann nicht direkt instanziiert werden (ABC)
2. GarminConnector ist im PROVIDER_REGISTRY unter "garmin" registriert
3. GarminConnector._token_dir() ist user_id-spezifisch
4. FernetField verschlüsselt beim Schreiben und entschlüsselt beim Lesen
"""
import pytest

from app.connectors import PROVIDER_REGISTRY
from app.connectors.base import BaseConnector
from app.connectors.garmin import GarminConnector
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
# 3. Token-Pfad ist user_id-spezifisch (erfordert App-Kontext für current_app)
# ---------------------------------------------------------------------------


def test_garmin_connector_token_path_per_user(app):
    """_token_dir() gibt pro User einen eigenen Pfad zurück (User-Isolation)."""
    with app.app_context():
        app.config["GARMIN_TOKEN_DIR"] = "/tmp/garmin-tokens"
        connector_user1 = GarminConnector(user_id=1)
        connector_user2 = GarminConnector(user_id=2)

        path1 = connector_user1._token_dir()
        path2 = connector_user2._token_dir()

    # Pfade müssen verschieden sein
    assert path1 != path2

    # Jeder Pfad muss die user_id enthalten
    assert "1" in path1
    assert "2" in path2


# ---------------------------------------------------------------------------
# 4. FernetField: Verschlüsselung beim Schreiben, Entschlüsselung beim Lesen
# ---------------------------------------------------------------------------


def test_credential_fernet_roundtrip():
    """FernetField verschlüsselt den Klartext und gibt ihn entschlüsselt zurück.

    Wir testen den TypeDecorator direkt (process_bind_param / process_result_value),
    weil ConnectorCredential.credentials als plain String-Column deklariert ist –
    die Verschlüsselungslogik lebt in FernetField, nicht im ORM-Mapping.
    """
    secret_key = "test-secret-key-not-for-production"
    plaintext = "super-secret-password"

    field = FernetField(secret_key)

    # Simuliert das Speichern in die DB (bind_param = was in die DB geht)
    encrypted = field.process_bind_param(plaintext, dialect=None)

    # Muss verschlüsselt sein (nicht gleich dem Klartext)
    assert encrypted is not None
    assert encrypted != plaintext

    # Simuliert das Lesen aus der DB (result_value = was Python bekommt)
    decrypted = field.process_result_value(encrypted, dialect=None)

    # Muss wieder dem Original entsprechen
    assert decrypted == plaintext
