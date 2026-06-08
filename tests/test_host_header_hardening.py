"""Tests für die Host-Header-Härtung (Issue haf).

Deckt ab:
- Externe Links (Passwort-Reset) entstehen aus PUBLIC_BASE_URL und nicht aus
  einem vom Angreifer gespooften Host-Header.
- TRUSTED_HOSTS lässt Flask fremde Host-Header mit HTTP 400 abweisen.
- Ohne PUBLIC_BASE_URL bleibt der lokale Dev-Fallback (Request-Host) funktionsfähig.
"""

from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.utils.urls import external_url_for


class _BaseTestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-for-host-hardening"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAILGUN_API_KEY = ""
    MAILGUN_DOMAIN = ""
    MAILGUN_SENDER = ""


class PublicBaseUrlConfig(_BaseTestConfig):
    # Kanonische Basis gesetzt, aber bewusst KEINE Host-Validierung, damit der
    # gespoofte Host die View erreicht und wir beweisen können, dass die URL
    # trotzdem sauber aus PUBLIC_BASE_URL entsteht.
    PUBLIC_BASE_URL = "https://canonical.example.com"


class TrustedHostsConfig(_BaseTestConfig):
    TRUSTED_HOSTS = ["trusted.example.com"]


def _make_client_with_user(config_class):
    app = create_app(config_class)
    with app.app_context():
        _db.create_all()
        user = User(email="victim@example.com")
        user.set_password("oldpassword123")
        user.is_approved = True
        _db.session.add(user)
        _db.session.commit()
        yield app, app.test_client()
        _db.drop_all()


@pytest.fixture()
def public_base_client():
    yield from _make_client_with_user(PublicBaseUrlConfig)


@pytest.fixture()
def trusted_hosts_client():
    yield from _make_client_with_user(TrustedHostsConfig)


class TestPublicBaseUrl:
    def test_reset_link_uses_public_base_url_not_spoofed_host(self, public_base_client):
        """Reset-Link muss aus PUBLIC_BASE_URL kommen, selbst bei gespooftem Host."""
        _app, client = public_base_client
        with patch("app.routes.auth.get_mailer") as mock_get_mailer:
            mock_mailer = mock_get_mailer.return_value
            client.post(
                "/auth/forgot-password",
                data={"email": "victim@example.com"},
                headers={"Host": "evil.attacker.example"},
                follow_redirects=True,
            )

        mock_mailer.send.assert_called_once()
        mail_text = mock_mailer.send.call_args.kwargs["text"]
        assert "https://canonical.example.com" in mail_text
        assert "evil.attacker.example" not in mail_text


class TestTrustedHosts:
    def test_spoofed_host_is_rejected(self, trusted_hosts_client):
        """Fremder Host-Header wird mit HTTP 400 abgewiesen."""
        _app, client = trusted_hosts_client
        resp = client.get(
            "/auth/login", headers={"Host": "evil.attacker.example"}
        )
        assert resp.status_code == 400

    def test_trusted_host_passes(self, trusted_hosts_client):
        """Erlaubter Host wird normal verarbeitet."""
        _app, client = trusted_hosts_client
        resp = client.get("/auth/login", headers={"Host": "trusted.example.com"})
        assert resp.status_code == 200


class TestExternalUrlForFallback:
    def test_falls_back_to_request_host_without_public_base_url(self):
        """Ohne PUBLIC_BASE_URL nutzt der Helper den Request-Host (lokale Dev)."""
        app = create_app(_BaseTestConfig)
        with app.test_request_context(base_url="http://localhost:5000"):
            url = external_url_for("auth.login")
        assert url.startswith("http://localhost:5000/")

    def test_uses_public_base_url_when_configured(self):
        """Mit PUBLIC_BASE_URL ignoriert der Helper den Request-Host vollständig."""
        app = create_app(PublicBaseUrlConfig)
        with app.test_request_context(base_url="http://localhost:5000"):
            url = external_url_for("auth.login")
        assert url.startswith("https://canonical.example.com/")
