"""Auth-Route Tests (I-24)

Abdeckung:
  1. test_register_creates_user         – POST /auth/register legt User in DB an
  2. test_login_with_valid_credentials  – POST /auth/login mit korrekten Daten → 302
  3. test_login_with_invalid_credentials– POST /auth/login mit falschen Daten → 200 + Fehlertext
  4. test_login_lockout_after_10_failures – 10 Fehlversuche → Konto gesperrt
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
# Test 4 – Lockout nach 10 Fehlversuchen
# ---------------------------------------------------------------------------

def test_login_lockout_after_10_failures(client, db):
    user = User(email="lockme@example.com", is_approved=True)
    user.set_password("richtiges_passwort")
    db.session.add(user)
    db.session.commit()

    payload = {"email": "lockme@example.com", "password": "falsch"}
    for _ in range(10):
        client.post("/auth/login", data=payload)

    # 11. Versuch – auch mit richtigem Passwort gesperrt
    resp = client.post(
        "/auth/login",
        data={"email": "lockme@example.com", "password": "richtiges_passwort"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "gesperrt" in resp.get_data(as_text=True)


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


# ---------------------------------------------------------------------------
# Test 7 – Registrierung lehnt ungültige E-Mail-Adresse ab
# ---------------------------------------------------------------------------

def test_register_rejects_invalid_email(client, db):
    resp = client.post("/auth/register", data={
        "email": "notanemail",
        "password": "TestPass123!",
    })
    assert resp.status_code == 200
    assert "Ungültige E-Mail-Adresse" in resp.data.decode()
    user = db.session.execute(
        db.select(User).filter_by(email="notanemail")
    ).scalar_one_or_none()
    assert user is None


# ---------------------------------------------------------------------------
# Test 8 – Registrierung lehnt XSS-Payload in E-Mail ab
# ---------------------------------------------------------------------------

def test_register_rejects_xss_email(client, db):
    resp = client.post("/auth/register", data={
        "email": "x');alert(1);//@evil.com",
        "password": "TestPass123!",
    })
    assert resp.status_code == 200
    assert "Ungültige E-Mail-Adresse" in resp.data.decode()
    count = db.session.execute(
        db.select(User)
    ).scalars().all()
    assert len(count) == 0


# ---------------------------------------------------------------------------
# Test 9 – Registrierung normalisiert E-Mail auf Kleinschreibung
# ---------------------------------------------------------------------------

def test_register_normalizes_email(client, db):
    # email_validator normalizes the domain to lowercase but preserves local part
    # "Test@Example.COM" → "Test@example.com"
    client.post("/auth/register", data={
        "email": "Test@Example.COM",
        "password": "TestPass123!",
    }, follow_redirects=True)
    user = db.session.execute(
        db.select(User).filter_by(email="Test@example.com")
    ).scalar_one_or_none()
    assert user is not None


# ---------------------------------------------------------------------------
# Test 10 – Registrierung akzeptiert E-Mail mit Plus-Adressierung
# ---------------------------------------------------------------------------

def test_register_accepts_valid_email_with_plus(client, db):
    client.post("/auth/register", data={
        "email": "user+tag@example.com",
        "password": "TestPass123!",
    }, follow_redirects=True)
    users = db.session.execute(
        db.select(User)
    ).scalars().all()
    assert len(users) == 1
    assert "user+tag@example.com" in users[0].email


# ---------------------------------------------------------------------------
# Test 11 – Registrierung lehnt zu kurzes Passwort ab
# ---------------------------------------------------------------------------

def test_register_rejects_short_password(client, db):
    resp = client.post("/auth/register", data={
        "email": "short@example.com",
        "password": "1234567",
    })
    assert resp.status_code == 200
    assert "mindestens 8 Zeichen" in resp.data.decode()
    user = db.session.execute(
        db.select(User).filter_by(email="short@example.com")
    ).scalar_one_or_none()
    assert user is None


# ---------------------------------------------------------------------------
# Test 12 – Registrierung akzeptiert Passwort mit genau 8 Zeichen
# ---------------------------------------------------------------------------

def test_register_accepts_password_with_8_chars(client, db):
    resp = client.post("/auth/register", data={
        "email": "exact8@example.com",
        "password": "12345678",
    }, follow_redirects=False)
    assert resp.status_code == 302
    user = db.session.execute(
        db.select(User).filter_by(email="exact8@example.com")
    ).scalar_one_or_none()
    assert user is not None
