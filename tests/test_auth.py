"""Auth-Route Tests (I-24)

Abdeckung:
  1. test_register_creates_user         – POST /auth/register legt User in DB an
  2. test_login_with_valid_credentials  – POST /auth/login mit korrekten Daten → 302
  3. test_login_with_invalid_credentials– POST /auth/login mit falschen Daten → 200 + Fehlertext
  4. test_login_rate_limited            – 6 Login-Versuche → 429 beim 6. Versuch
  5. test_logout_get_returns_405        – GET /auth/logout → 405
  6. test_csrf_missing_returns_400      – POST /auth/login ohne CSRF-Token → 400
"""

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import User


# ---------------------------------------------------------------------------
# Hilfs-Fixture: App mit aktiviertem Rate-Limiting (für Test 4)
# ---------------------------------------------------------------------------

class RateLimitConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    # Kein Default-Limit – nur die expliziten Route-Limits greifen
    RATELIMIT_DEFAULT = None


class CsrfConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    RATELIMIT_ENABLED = False


@pytest.fixture()
def rate_limit_client():
    """Test-Client mit aktiviertem Flask-Limiter (isoliert, In-Memory)."""
    app = create_app(RateLimitConfig)
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.drop_all()


@pytest.fixture()
def csrf_client():
    """Test-Client mit aktiviertem WTF_CSRF_ENABLED=True."""
    app = create_app(CsrfConfig)
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.drop_all()


# ---------------------------------------------------------------------------
# Test 1 – Register legt User in DB an
# ---------------------------------------------------------------------------

def test_register_creates_user(client, db):
    resp = client.post(
        "/auth/register",
        data={"email": "neuer@example.com", "password": "sicheresPasswort1!"},
        follow_redirects=False,
    )
    # Erfolgreiche Registrierung → Redirect (302)
    assert resp.status_code == 302

    user = db.session.execute(
        db.select(User).filter_by(email="neuer@example.com")
    ).scalar_one_or_none()
    assert user is not None
    assert user.email == "neuer@example.com"
    # Passwort darf nie im Klartext gespeichert sein
    assert user.password_hash != "sicheresPasswort1!"


# ---------------------------------------------------------------------------
# Test 2 – Login mit korrekten Credentials
# ---------------------------------------------------------------------------

def test_login_with_valid_credentials(client, db):
    # Vorbereitung: freigeschalteter User
    user = User(email="valid@example.com", is_approved=True)
    user.set_password("richtiges_passwort")
    db.session.add(user)
    db.session.commit()

    resp = client.post(
        "/auth/login",
        data={"email": "valid@example.com", "password": "richtiges_passwort"},
        follow_redirects=False,
    )
    # Login erfolgreich → Redirect
    assert resp.status_code == 302
    assert "/activities" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# Test 3 – Login mit falschen Credentials
# ---------------------------------------------------------------------------

def test_login_with_invalid_credentials(client, db):
    # Kein User angelegt → muss fehlschlagen
    resp = client.post(
        "/auth/login",
        data={"email": "unbekannt@example.com", "password": "falsch"},
        follow_redirects=False,
    )
    # Kein Redirect – Formular wird erneut gerendert
    assert resp.status_code == 200
    assert "Ungültige Anmeldedaten" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Test 4 – Login Rate-Limiting (429 beim 6. Versuch)
# ---------------------------------------------------------------------------

def test_login_rate_limited(rate_limit_client):
    payload = {"email": "spam@example.com", "password": "falsch"}
    last_response = None
    for _ in range(6):
        last_response = rate_limit_client.post("/auth/login", data=payload)
    assert last_response.status_code == 429


# ---------------------------------------------------------------------------
# Test 5 – GET /auth/logout ist nicht erlaubt → 405
# ---------------------------------------------------------------------------

def test_logout_get_returns_405(client, db):
    resp = client.get("/auth/logout")
    assert resp.status_code == 405


# ---------------------------------------------------------------------------
# Test 6 – POST /auth/login ohne CSRF-Token → 400
# ---------------------------------------------------------------------------

def test_csrf_missing_returns_400(csrf_client):
    # Kein CSRF-Token im POST → Flask-WTF soll 400 zurückgeben
    resp = csrf_client.post(
        "/auth/login",
        data={"email": "irgendwer@example.com", "password": "egal"},
    )
    assert resp.status_code == 400
