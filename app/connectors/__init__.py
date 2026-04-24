PROVIDER_REGISTRY: dict = {}


def register(cls):
    PROVIDER_REGISTRY[cls.provider_type] = cls
    return cls
