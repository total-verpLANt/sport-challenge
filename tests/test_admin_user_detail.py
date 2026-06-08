from datetime import date
from app.models.user import User
from app.models.connector import ConnectorCredential
from app.models.activity import Activity
from app.models.challenge import Challenge


def _create_user(db, email, password="testpass123", is_admin=False, is_approved=True):
    user = User(email=email, is_approved=is_approved)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email, password="testpass123"):
    client.post("/auth/login", data={"email": email, "password": password})


def _create_and_login(client, db, email="admin@test.com", password="testpass123", is_admin=True):
    user = _create_user(db, email, password, is_admin)
    _login(client, email, password)
    return user


# ──────────────────────────────────────────────
# Detail-Seite
# ──────────────────────────────────────────────

def test_user_detail_shows_info(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    rv = client.get(f"/admin/users/{target.id}")
    assert rv.status_code == 200
    assert b"target@test.com" in rv.data


def test_user_detail_shows_connectors(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    cred = ConnectorCredential(user_id=target.id, provider_type="garmin", credentials={})
    db.session.add(cred)
    db.session.commit()
    rv = client.get(f"/admin/users/{target.id}")
    assert rv.status_code == 200
    assert b"garmin" in rv.data


def test_user_detail_requires_admin(client, db):
    _create_and_login(client, db, "user@test.com", is_admin=False)
    target = _create_user(db, "target@test.com")
    rv = client.get(f"/admin/users/{target.id}")
    assert rv.status_code == 403


# ──────────────────────────────────────────────
# Sperren / Entsperren
# ──────────────────────────────────────────────

def test_suspend_user(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    assert target.is_approved is True
    client.post(f"/admin/users/{target.id}/suspend", follow_redirects=True)
    db.session.refresh(target)
    assert target.is_approved is False


def test_suspend_blocks_self(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    rv = client.post(f"/admin/users/{admin.id}/suspend", follow_redirects=True)
    db.session.refresh(admin)
    assert admin.is_approved is True  # unverändert
    assert b"Eigenes Konto" in rv.data


def test_unsuspend_user(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com", is_approved=False)
    client.post(f"/admin/users/{target.id}/unsuspend", follow_redirects=True)
    db.session.refresh(target)
    assert target.is_approved is True


# ──────────────────────────────────────────────
# Passwort-Reset
# ──────────────────────────────────────────────

def test_reset_password_success(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com", password="oldpassword")
    client.post(
        f"/admin/users/{target.id}/reset-password",
        data={"new_password": "newpassword123"},
        follow_redirects=True,
    )
    db.session.refresh(target)
    assert target.check_password("newpassword123") is True
    assert target.check_password("oldpassword") is False


def test_reset_password_too_short(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com", password="oldpassword")
    rv = client.post(
        f"/admin/users/{target.id}/reset-password",
        data={"new_password": "short"},
        follow_redirects=True,
    )
    db.session.refresh(target)
    assert target.check_password("oldpassword") is True  # unverändert
    assert b"mindestens" in rv.data


# ──────────────────────────────────────────────
# User löschen
# ──────────────────────────────────────────────

def test_delete_user_cascade(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    cred = ConnectorCredential(user_id=target.id, provider_type="garmin", credentials={})
    db.session.add(cred)
    db.session.commit()
    target_id = target.id
    client.post(
        f"/admin/users/{target_id}/delete",
        data={"confirm_email": "target@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, target_id) is None
    assert ConnectorCredential.query.filter_by(user_id=target_id).count() == 0


def test_delete_user_requires_email_confirmation(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    target_id = target.id
    rv = client.post(
        f"/admin/users/{target_id}/delete",
        data={"confirm_email": "wrong@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, target_id) is not None  # User noch vorhanden
    assert b"stimmt nicht" in rv.data


def test_delete_user_blocks_self(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    rv = client.post(
        f"/admin/users/{admin.id}/delete",
        data={"confirm_email": "admin@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, admin.id) is not None
    assert b"Eigenes Konto" in rv.data


def test_delete_admin_user_succeeds_when_multiple_admins(client, db):
    # Last-Admin-Guard ist per Route strukturell nicht triggerbar (Löscher muss Admin sein,
    # also existieren immer ≥2 Admins). Guard bleibt als Defensiv-Code. Dieser Test
    # verifiziert stattdessen: Löschen eines anderen Admins gelingt wenn ≥2 Admins vorhanden.
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    second = _create_user(db, "second@test.com", is_admin=True)
    second_id = second.id
    client.post(
        f"/admin/users/{second_id}/delete",
        data={"confirm_email": "second@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, second_id) is None


def test_delete_user_blocks_if_has_challenges(client, db):
    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")
    challenge = Challenge(
        name="Test Challenge",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        created_by_id=target.id,
    )
    db.session.add(challenge)
    db.session.commit()
    target_id = target.id
    rv = client.post(
        f"/admin/users/{target_id}/delete",
        data={"confirm_email": "target@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, target_id) is not None
    assert b"Challenges erstellt" in rv.data


def test_delete_user_cascades_sick_period_likes(client, db):
    """User-Löschung entfernt Likes auf eigene UND Likes auf fremde Abwesenheiten."""
    from app.models.challenge import Challenge, ChallengeParticipation
    from app.models.sick_period import SickPeriod, SickPeriodLike

    admin = _create_and_login(client, db, "admin@test.com", is_admin=True)
    target = _create_user(db, "target@test.com")

    # Challenge vom Admin (target hat keine erstellt -> Löschung nicht blockiert)
    ch = Challenge(name="Cascade", start_date=date(2024, 1, 1),
                   end_date=date(2024, 12, 31), created_by_id=admin.id)
    db.session.add(ch)
    db.session.commit()
    db.session.add_all([
        ChallengeParticipation(user_id=admin.id, challenge_id=ch.id, weekly_goal=3, status="accepted"),
        ChallengeParticipation(user_id=target.id, challenge_id=ch.id, weekly_goal=3, status="accepted"),
    ])
    # target's eigene Abwesenheit + admin's Abwesenheit
    sp_target = SickPeriod(user_id=target.id, challenge_id=ch.id,
                           start_date=date(2024, 1, 1), end_date=date(2024, 1, 2))
    sp_admin = SickPeriod(user_id=admin.id, challenge_id=ch.id,
                          start_date=date(2024, 2, 1), end_date=date(2024, 2, 2))
    db.session.add_all([sp_target, sp_admin])
    db.session.commit()
    # Like auf target's Abwesenheit (von admin) + target's Like auf admin's Abwesenheit
    like_on_own = SickPeriodLike(sick_period_id=sp_target.id, user_id=admin.id)
    like_by_target = SickPeriodLike(sick_period_id=sp_admin.id, user_id=target.id)
    db.session.add_all([like_on_own, like_by_target])
    db.session.commit()
    own_id, by_target_id = like_on_own.id, like_by_target.id
    target_id = target.id

    client.post(
        f"/admin/users/{target_id}/delete",
        data={"confirm_email": "target@test.com"},
        follow_redirects=True,
    )
    assert db.session.get(User, target_id) is None
    # Like auf target's (gelöschte) Abwesenheit weg
    assert db.session.get(SickPeriodLike, own_id) is None
    # Like, den target auf admin's Abwesenheit gesetzt hatte, ebenfalls weg
    assert db.session.get(SickPeriodLike, by_target_id) is None
    # admin's Abwesenheit bleibt erhalten
    assert db.session.get(SickPeriod, sp_admin.id) is not None
