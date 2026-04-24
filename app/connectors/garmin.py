from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flask import current_app

from app.connectors import register
from app.connectors.base import BaseConnector
from app.garmin.client import GarminClient


@register
class GarminConnector(BaseConnector):
    """Per-User-isolierter Garmin-Connector.

    Eine Instanz wird pro User erzeugt; ``user_id`` wird im Konstruktor
    übergeben, damit die drei ABC-Methoden ohne ``user_id``-Parameter
    auskommen und das Interface sauber bleibt.
    """

    provider_type = "garmin"
    display_name = "Garmin Connect"
    credential_fields = ["email", "password"]

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._client: GarminClient | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _token_dir(self) -> str:
        """Gibt den isolierten Token-Pfad für diesen User zurück."""
        base = current_app.config["GARMIN_TOKEN_DIR"]
        return str(Path(base) / str(self._user_id))

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def connect(self, credentials: dict) -> None:
        """Frisch einloggen und Tokens in das user-spezifische Dir speichern."""
        token_dir = self._token_dir()
        self._client = GarminClient(token_dir=token_dir)
        self._client.login(
            email=credentials["email"],
            password=credentials["password"],
        )

    def get_activities(self, start: datetime, end: datetime) -> list:
        """Aktivitäten abrufen; bei vorhandenen Tokens kein Passwort nötig."""
        if self._client is None:
            raise RuntimeError(
                "GarminConnector nicht verbunden – connect() zuerst aufrufen."
            )
        return self._client.get_week_activities(start, end)

    def disconnect(self) -> None:
        """Token-Dir des Users löschen und Client-Referenz freigeben."""
        token_dir = self._token_dir()
        path = Path(token_dir)
        if path.exists():
            shutil.rmtree(path)
        self._client = None
