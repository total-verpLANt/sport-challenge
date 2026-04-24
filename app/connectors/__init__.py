PROVIDER_REGISTRY: dict = {}


def register(cls):
    PROVIDER_REGISTRY[cls.provider_type] = cls
    return cls


# Connector-Module importieren, damit @register greift
from app.connectors import garmin  # noqa: E402, F401
