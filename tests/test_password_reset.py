"""Tests für den Passwort-vergessen-Flow (forgot_password + reset_password)."""

from unittest.mock import patch

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import User
from app.services.mailer import MailgunError


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-for-password-reset"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAILGUN_API_KEY = ""
    MAILGUN_DOMAIN = ""
    MAILGUN_SENDER = ""


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        # Test-User anlegen (manuell approved, da kein Register-Flow)
        user = User(email="test@example.com")
        user.set_password("oldpassword123")
        user.is_approved = True
        _db.session.add(user)
        _db.session.commit()
        yield app.test_client()
        _db.drop_all()


class TestForgotPasswordRoute:
    def test_get_renders_form(self, client):
        resp = client.get("/auth/forgot-password")
        assert resp.status_code == 200
        assert b"Passwort vergessen" in resp.data

    def test_post_unknown_email_shows_same_message(self, client):
        """Timing-sicheres Verhalten: gleiche Antwort ob E-Mail bekannt oder nicht."""
        resp = client.post(
            "/auth/forgot-password",
            data={"email": "nobody@example.com"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Reset-Link" in resp.data

    def test_post_known_email_calls_mailer(self, client):
        with patch("app.routes.auth.get_mailer") as mock_get_mailer:
            mock_mailer = mock_get_mailer.return_value
            resp = client.post(
                "/auth/forgot-password",
                data={"email": "test@example.com"},
                follow_redirects=True,
            )
        assert resp.status_code == 200
        mock_mailer.send.assert_called_once()
        call_kwargs = mock_mailer.send.call_args.kwargs
        assert call_kwargs["to"] == "test@example.com"
        assert "Passwort" in call_kwargs["subject"]

    def test_post_mailer_error_still_shows_success_message(self, client):
        """MailgunError darf die Seite nicht crashen."""
        with patch("app.routes.auth.get_mailer") as mock_get_mailer:
            mock_get_mailer.return_value.send.side_effect = MailgunError("Netzwerkfehler")
            resp = client.post(
                "/auth/forgot-password",
                data={"email": "test@example.com"},
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert b"Reset-Link" in resp.data

    def test_post_invalid_email_format_shows_same_message(self, client):
        resp = client.post(
            "/auth/forgot-password",
            data={"email": "kein-at-zeichen"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Reset-Link" in resp.data


class TestResetPasswordRoute:
    def _get_valid_token(self, app):
        """Erstellt ein gültiges Reset-Token für test@example.com."""
        from itsdangerous import URLSafeTimedSerializer

        with app.app_context():
            user = _db.session.execute(
                _db.select(User).filter_by(email="test@example.com")
            ).scalar_one()
            s = URLSafeTimedSerializer(app.config["SECRET_KEY"])
            return s.dumps(user.id, salt="password-reset")

    def test_get_with_valid_token_renders_form(self, client):
        from app import create_app

        app = create_app(TestConfig)
        with app.app_context():
            _db.create_all()
            user = User(email="test@example.com")
            user.set_password("oldpassword123")
            user.is_approved = True
            _db.session.add(user)
            _db.session.commit()
            token = self._get_valid_token(app)
            test_client = app.test_client()
            resp = test_client.get(f"/auth/reset-password/{token}")
        assert resp.status_code == 200
        assert b"Neues Passwort" in resp.data

    def test_invalid_token_redirects_with_error(self, client):
        resp = client.get("/auth/reset-password/ungueltig-token", follow_redirects=True)
        assert resp.status_code == 200
        assert b"Passwort vergessen" in resp.data

    def test_post_valid_token_changes_password(self, client):
        from app import create_app

        app = create_app(TestConfig)
        with app.app_context():
            _db.create_all()
            user = User(email="test@example.com")
            user.set_password("oldpassword123")
            user.is_approved = True
            _db.session.add(user)
            _db.session.commit()

            token = self._get_valid_token(app)
            test_client = app.test_client()
            resp = test_client.post(
                f"/auth/reset-password/{token}",
                data={"password": "neupass456", "password2": "neupass456"},
                follow_redirects=True,
            )
            assert resp.status_code == 200
            assert b"erfolgreich" in resp.data

            updated = _db.session.execute(
                _db.select(User).filter_by(email="test@example.com")
            ).scalar_one()
            assert updated.check_password("neupass456")
            assert not updated.check_password("oldpassword123")

    def test_post_password_mismatch_shows_error(self, client):
        from app import create_app

        app = create_app(TestConfig)
        with app.app_context():
            _db.create_all()
            user = User(email="test@example.com")
            user.set_password("oldpassword123")
            user.is_approved = True
            _db.session.add(user)
            _db.session.commit()

            token = self._get_valid_token(app)
            test_client = app.test_client()
            resp = test_client.post(
                f"/auth/reset-password/{token}",
                data={"password": "neupass456", "password2": "anderspass"},
            )
        assert resp.status_code == 200
        assert b"stimmen nicht" in resp.data

    def test_post_password_too_short_shows_error(self, client):
        from app import create_app

        app = create_app(TestConfig)
        with app.app_context():
            _db.create_all()
            user = User(email="test@example.com")
            user.set_password("oldpassword123")
            user.is_approved = True
            _db.session.add(user)
            _db.session.commit()

            token = self._get_valid_token(app)
            test_client = app.test_client()
            resp = test_client.post(
                f"/auth/reset-password/{token}",
                data={"password": "kurz", "password2": "kurz"},
            )
        assert resp.status_code == 200
        assert b"Zeichen" in resp.data
