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
