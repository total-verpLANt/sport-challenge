from abc import ABC, abstractmethod
from datetime import datetime


class BaseConnector(ABC):
    provider_type: str = ""
    display_name: str = ""
    credential_fields: list[str] = []
    oauth_flow: bool = False

    @abstractmethod
    def connect(self, credentials: dict) -> None: ...

    @abstractmethod
    def get_activities(self, start: datetime, end: datetime) -> list: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    def get_token_updates(self) -> dict:
        """Gibt Token-Keys zurück, die nach connect() in credentials gespeichert werden.
        Default: leeres Dict (kein Token-Update nötig, z.B. Garmin nach Reconnect ohne Refresh)."""
        return {}
