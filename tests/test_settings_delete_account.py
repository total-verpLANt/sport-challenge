"""Tests für Self-Service Account-Löschung (myv).

Abdeckung:
  1. test_delete_account_wrong_password      – falsches Passwort → Fehler, kein Löschen
  2. test_delete_account_success             – korrektes Passwort → User gelöscht, ausgeloggt
  3. test_delete_account_last_admin_blocked  – letzter Admin kann sich nicht selbst löschen
  4. test_delete_account_challenge_creator_blocked – User mit eigener Challenge wird blockiert
  5. test_delete_account_cascades_data       – abhängige Daten werden mitgelöscht
  6. test_delete_account_requires_login      – unauthentifizierter Zugriff → 401/302
"""

import pytest

from app.extensions import db as _db
from app.models.activity import Activity
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User


def _register_and_approve(client, db, email, password, role="user"):
    user = User(email=email, role=role, is_approved=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# 1. Falsches Passwort
# ---------------------------------------------------------------------------

def test_delete_account_wrong_password(client, db):
    _register_and_approve(client, db, "bob@example.com", "correcthorse")
    _login(client, "bob@example.com", "correcthorse")

    resp = client.post(
        "/settings/delete-account",
        data={"password": "wrongpassword"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Passwort ist falsch" in resp.get_data(as_text=True)
    assert db.session.execute(_db.select(User).filter_by(email="bob@example.com")).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 2. Erfolgreiche Löschung
# ---------------------------------------------------------------------------

def test_delete_account_success(client, db):
    _register_and_approve(client, db, "alice@example.com", "securepass1")
    _login(client, "alice@example.com", "securepass1")

    resp = client.post(
        "/settings/delete-account",
        data={"password": "securepass1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    # Sollte auf Login-Seite gelandet sein
    assert "login" in resp.request.path or b"login" in resp.data.lower() or "Konto wurde gel" in resp.get_data(as_text=True)
    assert db.session.execute(_db.select(User).filter_by(email="alice@example.com")).scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# 3. Letzter Admin kann sich nicht selbst löschen
# ---------------------------------------------------------------------------

def test_delete_account_last_admin_blocked(client, db):
    admin = _register_and_approve(client, db, "admin@example.com", "adminpass1", role="admin")
    _login(client, "admin@example.com", "adminpass1")

    resp = client.post(
        "/settings/delete-account",
        data={"password": "adminpass1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "letzter Admin" in resp.get_data(as_text=True)
    assert db.session.get(User, admin.id) is not None


# ---------------------------------------------------------------------------
# 4. User mit eigener Challenge wird blockiert
# ---------------------------------------------------------------------------

def test_delete_account_challenge_creator_blocked(client, db):
    from datetime import date
    creator = _register_and_approve(client, db, "creator@example.com", "creatorpass1")
    challenge = Challenge(
        name="Test Challenge",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        created_by_id=creator.id,
    )
    db.session.add(challenge)
    db.session.commit()

    _login(client, "creator@example.com", "creatorpass1")
    resp = client.post(
        "/settings/delete-account",
        data={"password": "creatorpass1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Challenge" in resp.get_data(as_text=True)
    assert db.session.get(User, creator.id) is not None


# ---------------------------------------------------------------------------
# 5. Cascade: Aktivitäten werden mitgelöscht
# ---------------------------------------------------------------------------

def test_delete_account_cascades_data(client, db):
    from datetime import date
    user = _register_and_approve(client, db, "cascade@example.com", "cascadepass1")

    # Admin für Challenge-Erstellung
    admin = _register_and_approve(client, db, "adm2@example.com", "adminpass2", role="admin")
    challenge = Challenge(
        name="Cascade Challenge",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.flush()

    participation = ChallengeParticipation(
        user_id=user.id, challenge_id=challenge.id, weekly_goal=3, status="accepted"
    )
    activity = Activity(
        user_id=user.id,
        challenge_id=challenge.id,
        activity_date=date(2026, 1, 5),
        duration_minutes=45,
        sport_type="running",
        source="manual",
    )
    db.session.add_all([participation, activity])
    db.session.commit()

    act_id = activity.id
    part_id = participation.id

    _login(client, "cascade@example.com", "cascadepass1")
    resp = client.post(
        "/settings/delete-account",
        data={"password": "cascadepass1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert db.session.execute(_db.select(User).filter_by(email="cascade@example.com")).scalar_one_or_none() is None
    assert db.session.get(Activity, act_id) is None
    assert db.session.get(ChallengeParticipation, part_id) is None


# ---------------------------------------------------------------------------
# 6. Unauthentifizierter Zugriff
# ---------------------------------------------------------------------------

def test_delete_account_requires_login(client, db):
    resp = client.post(
        "/settings/delete-account",
        data={"password": "anything"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 401)
