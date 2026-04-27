"""Approval-Flow Tests (A-05)

Abdeckung:
  1. test_first_user_becomes_admin_and_approved
  2. test_second_user_created_unapproved_no_autologin
  3. test_unapproved_user_blocked_from_login
  4. test_pending_message_only_after_correct_credentials
  5. test_admin_can_view_pending_users
  6. test_admin_can_approve_user
  7. test_admin_can_reject_user
  8. test_non_admin_cannot_access_admin_panel
  9. test_unauthenticated_redirects_to_login_on_admin_route
"""

import pytest

from app.models.user import User


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def make_admin(db, email="admin@example.com", password="admin_pw"):
    user = User(email=email, role="admin", is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def make_pending(db, email="pending@example.com", password="pending_pw"):
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def login_as(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Test 1 – Erster registrierter User wird Admin + approved
# ---------------------------------------------------------------------------

def test_first_user_becomes_admin_and_approved(client, db):
    resp = client.post(
        "/auth/register",
        data={"email": "first@example.com", "password": "Sicher1!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # Erster User ohne Nickname → Redirect auf Settings für Nickname-Eingabe
    assert "/settings" in resp.headers["Location"]

    user = db.session.execute(
        db.select(User).filter_by(email="first@example.com")
    ).scalar_one_or_none()
    assert user is not None
    assert user.is_admin is True
    assert user.is_approved is True


# ---------------------------------------------------------------------------
# Test 2 – Zweiter User: is_approved=False, kein Auto-Login
# ---------------------------------------------------------------------------

def test_second_user_created_unapproved_no_autologin(client, db):
    make_admin(db)  # erster User existiert bereits

    resp = client.post(
        "/auth/register",
        data={"email": "second@example.com", "password": "Sicher2!"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]

    user = db.session.execute(
        db.select(User).filter_by(email="second@example.com")
    ).scalar_one_or_none()
    assert user is not None
    assert user.is_approved is False

    # Kein Zugriff auf geschützte Route (nicht eingeloggt)
    protected = client.get("/activities/week", follow_redirects=False)
    assert protected.status_code == 302


# ---------------------------------------------------------------------------
# Test 3 – Unapproved User mit korrektem Passwort → Pending-Meldung, kein Login
# ---------------------------------------------------------------------------

def test_unapproved_user_blocked_from_login(client, db):
    make_pending(db, password="richtiges_pw")

    resp = client.post(
        "/auth/login",
        data={"email": "pending@example.com", "password": "richtiges_pw"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Admin-Freigabe" in resp.get_data(as_text=True)

    # Session enthält keinen eingeloggten User
    protected = client.get("/activities/week", follow_redirects=False)
    assert protected.status_code == 302


# ---------------------------------------------------------------------------
# Test 4 – Pending-Meldung nur nach korrektem Passwort (kein Info-Leak)
# ---------------------------------------------------------------------------

def test_pending_message_only_after_correct_credentials(client, db):
    make_pending(db, password="richtiges_pw")

    # Falsches Passwort → generische Fehlermeldung
    resp_bad = client.post(
        "/auth/login",
        data={"email": "pending@example.com", "password": "falsches_pw"},
        follow_redirects=False,
    )
    body_bad = resp_bad.get_data(as_text=True)
    assert "Ungültige Anmeldedaten" in body_bad
    assert "Admin-Freigabe" not in body_bad

    # Korrektes Passwort → Pending-Meldung
    resp_good = client.post(
        "/auth/login",
        data={"email": "pending@example.com", "password": "richtiges_pw"},
        follow_redirects=False,
    )
    body_good = resp_good.get_data(as_text=True)
    assert "Admin-Freigabe" in body_good
    assert "Ungültige Anmeldedaten" not in body_good


# ---------------------------------------------------------------------------
# Test 5 – Admin sieht pending Users in /admin/users
# ---------------------------------------------------------------------------

def test_admin_can_view_pending_users(client, db):
    make_admin(db)
    make_pending(db, email="p1@example.com")
    make_pending(db, email="p2@example.com")

    login_as(client, "admin@example.com", "admin_pw")
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "p1@example.com" in html
    assert "p2@example.com" in html
    assert "Ausstehend" in html


# ---------------------------------------------------------------------------
# Test 6 – Admin kann User freischalten
# ---------------------------------------------------------------------------

def test_admin_can_approve_user(client, db):
    admin = make_admin(db)
    pending = make_pending(db)
    pending_id = pending.id

    login_as(client, "admin@example.com", "admin_pw")
    resp = client.post(f"/admin/users/{pending_id}/approve", follow_redirects=False)
    assert resp.status_code == 302

    db.session.expire_all()
    updated = db.session.get(User, pending_id)
    assert updated.is_approved is True
    assert updated.approved_at is not None
    assert updated.approved_by_id == admin.id


# ---------------------------------------------------------------------------
# Test 7 – Admin kann User ablehnen (→ gelöscht)
# ---------------------------------------------------------------------------

def test_admin_can_reject_user(client, db):
    make_admin(db)
    pending = make_pending(db)
    pending_id = pending.id

    login_as(client, "admin@example.com", "admin_pw")
    resp = client.post(f"/admin/users/{pending_id}/reject", follow_redirects=False)
    assert resp.status_code == 302

    db.session.expire_all()
    deleted = db.session.get(User, pending_id)
    assert deleted is None


# ---------------------------------------------------------------------------
# Test 8 – Nicht-Admin → 403 auf Admin-Routes
# ---------------------------------------------------------------------------

def test_non_admin_cannot_access_admin_panel(client, db):
    user = User(email="user@example.com", is_approved=True)
    user.set_password("user_pw")
    db.session.add(user)
    db.session.commit()

    login_as(client, "user@example.com", "user_pw")
    resp = client.get("/admin/users")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test 9 – Unauthenticated → 302 Redirect auf /auth/login
# ---------------------------------------------------------------------------

def test_unauthenticated_redirects_to_login_on_admin_route(client, db):
    resp = client.get("/admin/users", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
