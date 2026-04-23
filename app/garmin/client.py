from __future__ import annotations

import os
from datetime import date

from garminconnect import Garmin, GarminConnectAuthenticationError


class GarminClient:
    def __init__(self, email: str, password: str, token_dir: str) -> None:
        self._email = email
        self._password = password
        self._token_dir = token_dir
        self._api: Garmin | None = None

    def connect(self) -> None:
        """Token-Reuse versuchen; bei Fehler Fresh-Login durchführen."""
        self._api = Garmin(email=self._email, password=self._password)
        try:
            self._api.login(self._token_dir)
        except Exception:
            os.makedirs(self._token_dir, exist_ok=True)
            self._api.login()

    def get_week_activities(self, start: date, end: date) -> list[dict]:
        if self._api is None:
            self.connect()
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
