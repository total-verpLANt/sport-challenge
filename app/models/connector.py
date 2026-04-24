import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.utils.crypto import FernetField


class _JsonFernetField(FernetField):
    """Transparente JSON-Serialisierung on top of FernetField."""

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return super().process_bind_param(json.dumps(value), dialect)

    def process_result_value(self, value, dialect):
        raw = super().process_result_value(value, dialect)
        if raw is None:
            return None
        return json.loads(raw)


class ConnectorCredential(db.Model):
    __tablename__ = "connector_credentials"
    __table_args__ = (UniqueConstraint("user_id", "provider_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    credentials: Mapped[dict] = mapped_column(_JsonFernetField(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
