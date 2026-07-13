import hmac
from datetime import datetime, timezone
from hashlib import sha256

from flask import current_app
from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt:131072:8:1")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def auth_hash(self) -> str:
        """Session-/Remember-Token-Bindung an das aktuelle Passwort (siehe uat2).

        HMAC-SHA256 über den password_hash mit dem SECRET_KEY als Schlüssel
        (Django-`get_session_auth_hash`-Muster). Ändert sich das Passwort, ändert
        sich der password_hash und damit dieser Wert – bestehende Session- und
        Remember-Cookies (die ihn via get_id transportieren) werden dadurch beim
        nächsten Laden ungültig. So überlebt ein gestohlenes Cookie keinen
        Passwort-Reset des Opfers.
        """
        secret = current_app.config["SECRET_KEY"]
        if isinstance(secret, str):
            secret = secret.encode()
        return hmac.new(secret, self.password_hash.encode(), sha256).hexdigest()

    def get_id(self) -> str:
        """Flask-Login-Identität: '<id>|<auth_hash>' statt nur der User-ID.

        Der user_loader (app/__init__.py) prüft den auth_hash-Teil konstant-zeitig
        gegen den aktuellen Wert und weist abweichende (= veraltete) Tokens ab.
        """
        return f"{self.id}|{self.auth_hash()}"

    @property
    def display_name(self) -> str:
        return self.nickname or self.email.split("@")[0]

    @property
    def is_active(self) -> bool:
        return self.is_approved

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
