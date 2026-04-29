"""Tests für BonusChallenge-Delete (Admin)."""
import pytest
from app.models.bonus import BonusChallenge, BonusChallengeEntry
from app.models.user import User
from datetime import date


def _create_admin_and_login(client, db, email="admin@test.com"):
    """Erstellt einen Admin-User und loggt ihn ein."""
    user = User(email=email, is_approved=True)
    user.role = "admin"
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "testpass123"})
    return user


def _create_user_and_login(client, db, email="user@test.com"):
    """Erstellt einen normalen User und loggt ihn ein."""
    user = User(email=email, is_approved=True)
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "testpass123"})
    return user


def _create_challenge(db, created_by_id):
    """Erstellt eine minimale Challenge."""
    from app.models.challenge import Challenge
    challenge = Challenge(
        name="Test Challenge",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        created_by_id=created_by_id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def test_admin_deletes_bonus_challenge(client, db):
    """Admin löscht BonusChallenge – Cascade zu BonusChallengeEntry."""
    admin = _create_admin_and_login(client, db)
    challenge = _create_challenge(db, admin.id)

    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date(2024, 6, 1),
        description="Testbonus",
    )
    db.session.add(bonus)
    db.session.commit()

    # Entry anlegen
    entry = BonusChallengeEntry(
        user_id=admin.id,
        bonus_challenge_id=bonus.id,
        time_seconds=120,
    )
    db.session.add(entry)
    db.session.commit()
    bonus_id = bonus.id
    entry_id = entry.id

    resp = client.post(f"/bonus/{bonus_id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(BonusChallenge, bonus_id) is None
    assert db.session.get(BonusChallengeEntry, entry_id) is None


def test_user_cannot_delete_bonus_challenge(client, db):
    """Normaler User kann BonusChallenge nicht löschen."""
    admin = _create_admin_and_login(client, db, email="bonus_admin2@test.com")
    challenge = _create_challenge(db, admin.id)
    bonus = BonusChallenge(
        challenge_id=challenge.id,
        scheduled_date=date(2024, 6, 1),
        description="Protected Bonus",
    )
    db.session.add(bonus)
    db.session.commit()
    bonus_id = bonus.id

    # Als normaler User einloggen (explizit ausloggen – Flask-Login ersetzt Session sonst nicht)
    client.post("/auth/logout")
    _create_user_and_login(client, db, email="bonus_user@test.com")

    resp = client.post(f"/bonus/{bonus_id}/delete", follow_redirects=False)
    # admin_required → 403 oder Redirect zu Login
    assert resp.status_code in (302, 403)
    # BonusChallenge noch vorhanden
    assert db.session.get(BonusChallenge, bonus_id) is not None


def test_delete_bonus_challenge_404_on_missing(client, db):
    """Ungültige bonus_id → 404."""
    _create_admin_and_login(client, db, email="bonus_admin3@test.com")
    resp = client.post("/bonus/99999/delete", follow_redirects=False)
    assert resp.status_code == 404
