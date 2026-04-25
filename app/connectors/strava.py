from __future__ import annotations

import time
from datetime import datetime

from stravalib.client import Client

from app.connectors import register
from app.connectors.base import BaseConnector


@register
class StravaConnector(BaseConnector):
    """Per-User-isolierter Strava-Connector via OAuth2.

    Tokens (access_token, refresh_token, expires_at) werden Fernet-verschlüsselt
    in ConnectorCredential.credentials gespeichert.
    """

    provider_type = "strava"
    display_name = "Strava"
    credential_fields = []  # kein Passwort-Formular – OAuth2 Flow
    oauth_flow = True

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._client: Client | None = None
        self._token_data: dict = {}  # gefüllt nach Token-Refresh

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def connect(self, credentials: dict) -> None:
        """Initialisiert stravalib-Client; refresht Token wenn abgelaufen."""
        access_token = credentials["access_token"]
        refresh_token = credentials["refresh_token"]
        expires_at = int(credentials["expires_at"])

        if time.time() > expires_at:
            from flask import current_app

            client_id = current_app.config["STRAVA_CLIENT_ID"]
            client_secret = current_app.config["STRAVA_CLIENT_SECRET"]
            tmp = Client()
            token_response = tmp.refresh_access_token(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
            access_token = token_response["access_token"]
            refresh_token = token_response["refresh_token"]
            expires_at = int(token_response["expires_at"])
            self._token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            }
        else:
            self._token_data = {}  # kein Update nötig

        self._client = Client(access_token=access_token)

    def get_token_updates(self) -> dict:
        """Gibt aktualisierte Token-Keys zurück (leer wenn kein Refresh nötig)."""
        return self._token_data

    def get_activities(self, start: datetime, end: datetime) -> list:
        if self._client is None:
            raise RuntimeError(
                "StravaConnector nicht verbunden – connect() zuerst aufrufen."
            )
        raw = list(self._client.get_activities(after=start, before=end, limit=100))
        return [_to_activity_dict(a) for a in raw]

    def disconnect(self) -> None:
        self._client = None
        self._token_data = {}


def _to_activity_dict(a) -> dict:
    """Konvertiert stravalib-Aktivität in das interne Dict-Format."""
    return {
        "startTimeLocal": str(a.start_date_local) if a.start_date_local else "",
        "activityName": a.name or "–",
        "activityType": {"typeKey": str(a.type).lower() if a.type else "–"},
        "duration": float(a.elapsed_time.total_seconds()) if a.elapsed_time else 0.0,
        "distance": float(a.distance) if a.distance else None,
        "averageHR": a.average_heartrate,
        "calories": a.calories,
    }
