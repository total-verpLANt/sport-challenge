"""Tests für Challenge-Delete (Admin) mit vollständiger Cascade."""
import pytest
from datetime import date
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.activity import Activity
from app.models.sick_period import SickPeriod
from app.models.bonus import BonusChallenge, BonusChallengeEntry
from app.models.user import User


def _create_admin_and_login(client, db, email="chdel_admin@test.com"):
    """Admin erstellen und einloggen."""
    user = User(email=email, is_approved=True)
    user.role = "admin"
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "testpass123"})
    return user


def _create_user_and_login(client, db, email="chdel_user@test.com"):
    """User erstellen und einloggen."""
    user = User(email=email, is_approved=True)
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "testpass123"})
    return user


def test_admin_deletes_challenge_cascade(client, db):
    """Admin löscht Challenge – alle abhängigen Objekte werden entfernt."""
    admin = _create_admin_and_login(client, db)

    challenge = Challenge(
        name="Delete Me",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()

    # Participation anlegen
    participation = ChallengeParticipation(
        user_id=admin.id, challenge_id=challenge.id,
        weekly_goal=3, status="accepted",
    )
    db.session.add(participation)

    # Activity anlegen
    activity = Activity(
        user_id=admin.id, challenge_id=challenge.id,
        activity_date=date(2024, 1, 15), duration_minutes=30,
        sport_type="running", source="manual",
    )
    db.session.add(activity)

    # SickPeriod anlegen
    sw = SickPeriod(user_id=admin.id, challenge_id=challenge.id,
                    start_date=date(2024, 1, 1), end_date=date(2024, 1, 7))
    db.session.add(sw)

    # BonusChallenge + Entry anlegen
    bonus = BonusChallenge(challenge_id=challenge.id, scheduled_date=date(2024, 6, 1), description="Bonus")
    db.session.add(bonus)
    db.session.commit()
    entry = BonusChallengeEntry(user_id=admin.id, bonus_challenge_id=bonus.id, time_seconds=60)
    db.session.add(entry)
    db.session.commit()

    challenge_id = challenge.id
    participation_id = participation.id
    activity_id = activity.id
    sw_id = sw.id
    bonus_id = bonus.id
    entry_id = entry.id

    # public_id für Route holen
    public_id = str(challenge.public_id)

    resp = client.post(f"/challenges/{public_id}/delete", follow_redirects=False)
    assert resp.status_code == 302

    # Alles weg?
    assert db.session.get(Challenge, challenge_id) is None
    assert db.session.get(ChallengeParticipation, participation_id) is None
    assert db.session.get(Activity, activity_id) is None
    assert db.session.get(SickPeriod, sw_id) is None
    assert db.session.get(BonusChallenge, bonus_id) is None
    assert db.session.get(BonusChallengeEntry, entry_id) is None


def test_user_cannot_delete_challenge(client, db):
    """Normaler User kann Challenge nicht löschen."""
    admin = _create_admin_and_login(client, db, email="chdel_admin2@test.com")
    challenge = Challenge(
        name="Protected",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        created_by_id=admin.id,
    )
    db.session.add(challenge)
    db.session.commit()
    public_id = str(challenge.public_id)
    challenge_id = challenge.id

    client.post("/auth/logout")
    _create_user_and_login(client, db, email="chdel_user2@test.com")
    resp = client.post(f"/challenges/{public_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 403)
    assert db.session.get(Challenge, challenge_id) is not None
