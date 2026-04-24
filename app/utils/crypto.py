import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import String, TypeDecorator


def derive_fernet_key(secret_key: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"sport-challenge-v1",
        info=b"connector-credentials",
    )
    raw = hkdf.derive(secret_key.encode())
    return base64.urlsafe_b64encode(raw)


class FernetField(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, secret_key: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet: Fernet | None = (
            Fernet(derive_fernet_key(secret_key)) if secret_key else None
        )

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            from flask import current_app
            self._fernet = Fernet(derive_fernet_key(current_app.config["SECRET_KEY"]))
        return self._fernet

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self._get_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._get_fernet().decrypt(value.encode()).decode()
