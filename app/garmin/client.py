from __future__ import annotations

import shutil
import tempfile
from datetime import date

from garminconnect import Garmin


class GarminClient:
    def __init__(self) -> None:
        self._api: Garmin | None = None

    def login(self, email: str, password: str) -> str:
        """Erstlogin mit Credentials; gibt serialisierten Token-JSON-String zurück."""
        tmp = tempfile.mkdtemp(prefix="garmin_login_")
        try:
            self._api = Garmin(email=email, password=password)
            self._api.login(tmp)
            return self._api.client.dumps()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def reconnect(self, token_json: str) -> str:
        """Token-basierter Reconnect ohne Passwort; gibt ggf. refreshten Token-String zurück."""
        self._api = Garmin()
        self._api.login(tokenstore=token_json)
        return self._api.client.dumps()

    def get_week_activities(self, start: date, end: date) -> list[dict]:
        if self._api is None:
            raise RuntimeError("Nicht eingeloggt – login() oder reconnect() aufrufen.")
        return self._api.get_activities_by_date(
            start.isoformat(),
            end.isoformat(),
        )

    @staticmethod
    def format_duration(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def format_distance(meters: float) -> str:
        return f"{meters / 1000:.2f} km"
