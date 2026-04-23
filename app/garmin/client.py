from __future__ import annotations

import os
from datetime import date

from garminconnect import Garmin


class GarminClient:
    def __init__(self, token_dir: str) -> None:
        self._token_dir = token_dir
        self._api: Garmin | None = None

    def login(self, email: str, password: str) -> None:
        """Frisch mit Credentials einloggen; Tokens auf Disk speichern."""
        os.makedirs(self._token_dir, exist_ok=True)
        self._api = Garmin(email=email, password=password)
        self._api.login(self._token_dir)

    def reconnect(self, email: str) -> None:
        """Gespeicherte Tokens laden – kein Passwort nötig, solange Tokens gültig."""
        self._api = Garmin(email=email, password="")
        self._api.login(self._token_dir)

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
