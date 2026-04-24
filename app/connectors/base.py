from abc import ABC, abstractmethod
from datetime import datetime


class BaseConnector(ABC):
    provider_type: str = ""
    display_name: str = ""
    credential_fields: list[str] = []

    @abstractmethod
    def connect(self, credentials: dict) -> None: ...

    @abstractmethod
    def get_activities(self, start: datetime, end: datetime) -> list: ...

    @abstractmethod
    def disconnect(self) -> None: ...
