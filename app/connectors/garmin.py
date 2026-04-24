from __future__ import annotations

from datetime import datetime

from app.connectors import register
from app.connectors.base import BaseConnector
from app.garmin.client import GarminClient
from app.utils.retry import retry_on_rate_limit


@register
class GarminConnector(BaseConnector):
    """Per-User-isolierter Garmin-Connector.

    Tokens werden Fernet-verschlüsselt in ConnectorCredential.credentials
    gespeichert (Schlüssel: '_garmin_tokens'). Kein Token-Verzeichnis auf Disk.
    """

    provider_type = "garmin"
    display_name = "Garmin Connect"
    credential_fields = ["email", "password"]

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._client: GarminClient | None = None
        self._current_token_json: str | None = None

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    @retry_on_rate_limit()
    def connect(self, credentials: dict) -> None:
        """Verbinden via gespeicherte Tokens (Reconnect) oder Erstlogin."""
        self._client = GarminClient()
        existing_tokens = credentials.get("_garmin_tokens")
        if existing_tokens:
            self._current_token_json = self._client.reconnect(existing_tokens)
        else:
            self._current_token_json = self._client.login(
                email=credentials["email"],
                password=credentials["password"],
            )

    def get_fresh_token_json(self) -> str | None:
        """Gibt den (ggf. refreshten) Token-String zurück – für DB-Update."""
        return self._current_token_json

    @retry_on_rate_limit()
    def get_activities(self, start: datetime, end: datetime) -> list:
        if self._client is None:
            raise RuntimeError(
                "GarminConnector nicht verbunden – connect() zuerst aufrufen."
            )
        return self._client.get_week_activities(start, end)

    def disconnect(self) -> None:
        """Client-Referenz und Token-String freigeben."""
        self._client = None
        self._current_token_json = None
