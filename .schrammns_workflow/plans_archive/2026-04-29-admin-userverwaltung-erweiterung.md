# Plan: Admin-Userverwaltung Erweiterung

**Date:** 2026-04-29
**Goal:** Admin kann User-Details einsehen, Passwort zurücksetzen, Konto sperren/entsperren und User löschen
**Research:** `.schrammns_workflow/research/2026-04-29-admin-userverwaltung-erweiterung.md`
**Status:** planned

---

## Baseline Audit

| Metric | Wert | Verifiziert mit |
|--------|------|----------------|
| Admin-Routen (vorher) | 4 (users, approve, reject, toggle-admin) | `wc -l app/routes/admin.py` = 90 |
| Admin-Templates | 1 (`admin/users.html`) | `ls app/templates/admin/` |
| Tests (gesamt) | 104 collected | `pytest --collect-only -q` |
| Tests test_admin.py | 7 passed | `pytest tests/test_admin.py -q` |
| FKs auf users.id | 9 Stellen in 6 Modellen | `grep -rn "ForeignKey.*users.id" app/models/` |

### FK-Inventar (relevant für Delete-Cascade)

| Modell | Feld | NOT NULL | Behandlung bei Delete |
|--------|------|----------|-----------------------|
| `User` | `approved_by_id` | False | kein Problem (nullable) |
| `BonusChallengeEntry` | `user_id` | True | DELETE WHERE user_id = id |
| `PenaltyOverride` | `user_id` | True | DELETE WHERE user_id = id |
| `PenaltyOverride` | `set_by_id` | True | DELETE WHERE set_by_id = id |
| `SickWeek` | `user_id` | True | DELETE WHERE user_id = id |
| `Activity` | `user_id` | True | DELETE WHERE user_id = id (ActivityMedia CASCADE folgt) |
| `ChallengeParticipation` | `user_id` | True | DELETE WHERE user_id = id |
| `ConnectorCredential` | `user_id` | True | DELETE WHERE user_id = id |
| `Challenge` | `created_by_id` | True | **BLOCK** – User hat Challenges erstellt → Löschung verweigern |

---

## Boundaries

**Always:**
- `admin_required` Decorator auf allen neuen Admin-Routen
- CSRF via `{{ csrf_token() }}` hidden Input in allen POST-Forms (globale CSRFProtect)
- Self-Edit blockieren (user_id == current_user.id → abort(403) oder flash + redirect)
- Last-Admin-Guard beim Löschen (letzter Admin darf nicht gelöscht werden)
- Passwort-Mindestlänge: 8 Zeichen (analog `_MIN_PASSWORD_LENGTH` in auth.py)
- Löschen blockieren wenn `Challenge.created_by_id = user.id` EXISTS
- Sperren = `is_approved = False` (kein neues Feld, `is_active` Property greift automatisch)
- Alle Felder in Tests ohne CSRF (CSRF in TestConfig deaktiviert via conftest.py Fixture)
- Passwords nie loggen

**Never:**
- DB-Migration erstellen (kein neues Feld nötig)
- Soft Delete (Hard Delete mit manuellem Cascade)
- Token-Flow für Admin-Passwort-Reset (Admin setzt direkt)
- ConnectorCredential.credentials im Template anzeigen

---

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/admin.py` | 5 neue Routen: detail, suspend, unsuspend, reset-password, delete |
| `app/templates/admin/users.html` | Link „Details" für jeden User-Eintrag hinzufügen |
| `app/templates/admin/user_detail.html` | **NEU** – Detailseite mit allen Aktions-Formularen |
| `tests/test_admin_user_detail.py` | **NEU** – Tests für alle 5 neuen Routen |
| `CHANGELOG.md` | Eintrag unter `[Unreleased]` |
| `app/version.py` | Patch-Version erhöhen (0.7.2 → 0.7.3) |

---

## Implementation Specs

### Issue 1: User-Detailseite

**Neue Route in `app/routes/admin.py`:**
```python
@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    connectors = ConnectorCredential.query.filter_by(user_id=user.id).all()
    has_challenges = Challenge.query.filter_by(created_by_id=user.id).first() is not None
    return render_template(
        "admin/user_detail.html",
        user=user,
        connectors=connectors,
        has_challenges=has_challenges,
    )
```

**Imports ergänzen:**
```python
from app.models.connector import ConnectorCredential
from app.models.challenge import Challenge
```

**Template `admin/user_detail.html` (NEU):**
- Extends `base.html`, Block `content`
- Zeigt: `user.email`, `user.nickname` (oder „–"), `user.role`, `user.is_approved`, `user.created_at`, `user.approved_at`, `user.approved_by_id`
- Zeigt: Liste `connectors` mit `connector.provider_type` (kein `credentials`!)
- Buttons: Sperren/Entsperren (POST, je nach `user.is_approved`), Passwort-Reset (POST-Form mit Eingabefeldern), Löschen (POST, nur wenn `not has_challenges`, sonst deaktiviert mit Tooltip)
- Alle POST-Formulare: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- Link zurück zu `/admin/users`

**Änderung in `admin/users.html`:**
- Für jeden User-Eintrag in der Tabelle: Button/Link `Details` → `url_for('admin.user_detail', user_id=user.id)`

### Issue 2: Sperren/Entsperren

**Neue Routen in `app/routes/admin.py`:**
```python
@admin_bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@admin_required
def suspend_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Eigenes Konto kann nicht gesperrt werden.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.is_approved = False
    db.session.commit()
    flash(f"Konto {user.display_name} gesperrt.", "warning")
    return redirect(url_for("admin.user_detail", user_id=user_id))

@admin_bp.route("/users/<int:user_id>/unsuspend", methods=["POST"])
@admin_required
def unsuspend_user(user_id):
    user = db.get_or_404(User, user_id)
    user.is_approved = True
    db.session.commit()
    flash(f"Konto {user.display_name} entsperrt.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))
```

### Issue 3: Admin-Passwort-Reset

**Neue Route in `app/routes/admin.py`:**
```python
_MIN_PASSWORD_LENGTH = 8  # bereits in auth.py, hier lokal definieren oder aus auth.py importieren

@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    new_password = request.form.get("new_password", "")
    if len(new_password) < _MIN_PASSWORD_LENGTH:
        flash(f"Passwort muss mindestens {_MIN_PASSWORD_LENGTH} Zeichen lang sein.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.set_password(new_password)
    db.session.commit()
    flash(f"Passwort für {user.display_name} zurückgesetzt.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))
```

**Imports ergänzen:** `from flask import request` (falls noch nicht vorhanden)

**Template-Ergänzung in `user_detail.html`:**
- Formular mit `<input type="password" name="new_password">` + `<input type="password" name="confirm_password">` (Bestätigung kann serverseitig validiert werden oder nur clientseitig mit HTML5 `pattern`/`required`)
- POST an `url_for('admin.reset_password', user_id=user.id)`

### Issue 4: User löschen mit Cascade

**Neue Route in `app/routes/admin.py`:**
```python
@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    
    # Self-Delete blockieren
    if user.id == current_user.id:
        flash("Eigenes Konto kann nicht gelöscht werden.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    
    # Last-Admin-Guard
    if user.is_admin:
        admin_count = db.session.scalar(
            db.select(func.count()).select_from(User).where(User.role == "admin")
        )
        if admin_count <= 1:
            flash("Letzter Admin kann nicht gelöscht werden.", "danger")
            return redirect(url_for("admin.user_detail", user_id=user_id))
    
    # Block wenn User Challenges erstellt hat
    if Challenge.query.filter_by(created_by_id=user.id).first():
        flash("User hat Challenges erstellt – bitte zuerst Challenges löschen oder übertragen.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    
    # Cascade-Löschen in Reihenfolge (FK-Abhängigkeiten beachten)
    BonusChallengeEntry.query.filter_by(user_id=user.id).delete()
    PenaltyOverride.query.filter(
        (PenaltyOverride.user_id == user.id) | (PenaltyOverride.set_by_id == user.id)
    ).delete()
    SickWeek.query.filter_by(user_id=user.id).delete()
    # Activity löschen → ActivityMedia cascades automatisch (SQLAlchemy cascade="all, delete-orphan")
    Activity.query.filter_by(user_id=user.id).delete()
    ChallengeParticipation.query.filter_by(user_id=user.id).delete()
    ConnectorCredential.query.filter_by(user_id=user.id).delete()
    
    display = user.display_name
    db.session.delete(user)
    db.session.commit()
    flash(f"Konto {display} gelöscht.", "success")
    return redirect(url_for("admin.users"))
```

**Imports ergänzen:**
```python
from app.models.bonus import BonusChallengeEntry
from app.models.penalty import PenaltyOverride
from app.models.sick_week import SickWeek
from app.models.activity import Activity
from app.models.challenge import ChallengeParticipation
```

**Template in `user_detail.html` – Zweistufige Bestätigung via Bootstrap-Modal:**

Der Delete-Button öffnet **kein** direktes Form, sondern ein Bootstrap-Modal (`data-bs-toggle="modal"`). Im Modal:
- Roter Warntext mit `user.email` (damit der Admin weiß, wen er löscht)
- Eingabefeld `<input type="text" name="confirm_email">` mit Placeholder „E-Mail eingeben zur Bestätigung"
- Nur wenn JS clientseitig E-Mail-Eingabe = user.email stimmt → Submit-Button aktiviert
- **Serverseitig** (Defense in depth): Route prüft `request.form.get("confirm_email") == user.email`, sonst flash danger + redirect ohne Löschen

```python
# Zusätzliche Guard in delete_user():
if request.form.get("confirm_email", "").strip() != user.email:
    flash("E-Mail-Bestätigung stimmt nicht überein.", "danger")
    return redirect(url_for("admin.user_detail", user_id=user_id))
```

Delete-Button nur sichtbar wenn `not has_challenges`.
POST an `url_for('admin.delete_user', user_id=user.id)`.

### Issue 5: Tests

**Neue Datei `tests/test_admin_user_detail.py`** – Pattern analog `test_admin.py`:

```python
def _create_and_login(client, db, email, password, is_admin=False):
    user = User(email=email, is_approved=True)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user
```

**Test-Funktionen:**
- `test_user_detail_shows_info(client, db)` – GET /admin/users/<id> zeigt email + role
- `test_user_detail_shows_connectors(client, db)` – ConnectorCredential.provider_type sichtbar
- `test_user_detail_requires_admin(client, db)` – Nicht-Admin → 403
- `test_suspend_user(client, db)` – POST suspend setzt is_approved=False
- `test_suspend_blocks_self(client, db)` – Selbst sperren → flash danger, kein DB-Change
- `test_unsuspend_user(client, db)` – POST unsuspend setzt is_approved=True
- `test_reset_password_success(client, db)` – Neues Passwort, Login mit neuem PW möglich
- `test_reset_password_too_short(client, db)` – < 8 Zeichen → flash danger, PW unverändert
- `test_delete_user_cascade(client, db)` – User mit Activities/Credentials wird gelöscht, DB sauber
- `test_delete_user_requires_email_confirmation(client, db)` – falsche E-Mail → flash danger, User bleibt erhalten
- `test_delete_user_blocks_self(client, db)` – Selbst löschen → flash danger
- `test_delete_user_blocks_last_admin(client, db)` – Letzter Admin → flash danger
- `test_delete_user_blocks_if_has_challenges(client, db)` – User hat Challenge erstellt → flash danger

---

## Issues & Waves

### Wave 1

#### I-01: User-Detailseite (Route + Template)
- **Typ:** feature | **Größe:** M | **Priorität:** 2
- **Risiko:** reversible / local / autonomous-ok
- **Dateien:** `app/routes/admin.py`, `app/templates/admin/users.html`, `app/templates/admin/user_detail.html` (NEU)
- **Akzeptanzkriterien:**
  - GET `/admin/users/<id>` zeigt email, nickname, role, is_approved, connectors (nur provider_type)
  - Link „Details" in users.html führt zur Detailseite
  - Template hat Platzhalter-Buttons für alle geplanten Aktionen (noch nicht funktional)
  - Nicht-Admin → 403, Nicht-eingeloggt → Login-Redirect

### Wave 2

#### I-02: Sperren/Entsperren (POST suspend/unsuspend)
- **Abhängigkeit:** I-01
- **Typ:** feature | **Größe:** S | **Priorität:** 2
- **Risiko:** reversible / local / autonomous-ok
- **Dateien:** `app/routes/admin.py`, `app/templates/admin/user_detail.html`
- **Akzeptanzkriterien:**
  - POST `/admin/users/<id>/suspend` setzt `is_approved=False`
  - POST `/admin/users/<id>/unsuspend` setzt `is_approved=True`
  - Gesperrter User kann sich nicht mehr einloggen (Flask-Login `is_active=False`)
  - Selbst-Sperren → flash danger, keine DB-Änderung
  - Button im Template: „Sperren" wenn `user.is_approved`, „Entsperren" wenn `not user.is_approved`

#### I-03: Admin-Passwort-Reset
- **Abhängigkeit:** I-02
- **Typ:** feature | **Größe:** S | **Priorität:** 2
- **Risiko:** reversible / local / autonomous-ok
- **Dateien:** `app/routes/admin.py`, `app/templates/admin/user_detail.html`
- **Akzeptanzkriterien:**
  - POST `/admin/users/<id>/reset-password` ruft `user.set_password(new_password)` auf
  - Mindestlänge 8 Zeichen validiert, sonst flash danger + redirect
  - Template zeigt Passwort-Formular (type=password, min-length=8)
  - Login mit neuem Passwort möglich, Login mit altem Passwort schlägt fehl

#### I-04: User löschen mit Cascade
- **Abhängigkeit:** I-03
- **Typ:** feature | **Größe:** M | **Priorität:** 2
- **Risiko:** irreversible / system / requires-approval (destruktiv!)
- **Dateien:** `app/routes/admin.py`, `app/templates/admin/user_detail.html`
- **Akzeptanzkriterien:**
  - POST `/admin/users/<id>/delete` löscht alle abhängigen Records in Reihenfolge
  - Self-Delete → flash danger, kein DB-Change
  - Last-Admin-Delete → flash danger, kein DB-Change
  - User mit erstellten Challenges → flash danger, kein DB-Change
  - Nach Löschen: User + alle abhängigen Records aus DB verschwunden
  - Redirect auf `/admin/users`

### Wave 3

#### I-05: Tests
- **Abhängigkeit:** I-04
- **Typ:** task | **Größe:** M | **Priorität:** 2
- **Risiko:** reversible / local / autonomous-ok
- **Dateien:** `tests/test_admin_user_detail.py` (NEU)
- **Akzeptanzkriterien:**
  - 12 Test-Funktionen (siehe Implementation Specs)
  - `pytest tests/test_admin_user_detail.py -v` → alle grün
  - `pytest tests/` → min. 116 Tests (104 + 12), alle grün

#### I-06: Version bump + CHANGELOG
- **Abhängigkeit:** I-05
- **Typ:** task | **Größe:** S | **Priorität:** 3
- **Risiko:** reversible / local / autonomous-ok
- **Dateien:** `app/version.py`, `CHANGELOG.md`
- **Akzeptanzkriterien:**
  - `app/version.py`: `__version__ = "0.7.3"`
  - `CHANGELOG.md`: Eintrag unter `[Unreleased]` mit allen 4 Features

---

## Wave Summary

| Wave | Issues | Parallel? |
|------|--------|-----------|
| 1 | I-01 | – |
| 2 | I-02, I-03, I-04 | Nein (gleiche Dateien admin.py + user_detail.html → seriell) |
| 3 | I-05, I-06 | Ja |

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Grund |
|-------------|---------|-----------|-------|
| Sperren-Mechanismus | `is_approved=False` | Neues `is_suspended`-Feld | Kein Schema-Change, `is_active` Property greift automatisch |
| Delete-Strategie | Hard Delete manuell | CASCADE Migration / Soft Delete | DSGVO-konform, kein Migrationsrisiko |
| User hat Challenges erstellt | Löschung blockieren | Challenges löschen oder created_by_id auf NULL | Sicherster Weg, keine Datenverlust-Gefahr |
| PW-Reset durch Admin | Direktes Set | Token/E-Mail-Flow | Admin-Panel-Kontext, kein Self-Service nötig |
| PW-Reset Bestätigung | Server-Validierung + HTML min | Nur client-side | Defense in depth |

---

## Rollback

**Git-Checkpoint:** `git stash` vor Implementierungsstart
**Wave 1-2:** Vollständig reversibel – keine DB-Änderungen, nur neue Routen + Templates
**Wave 3:** Tests + Version-Bump reversibel
**Gesamtrollback:** `git revert` auf den Feature-Commit reicht

---

## Verification Commands

```bash
# Baseline (vor Start)
set -a && source .env && set +a
.venv/bin/pytest tests/test_admin.py -v  # 7 Tests grün

# Nach Issue I-01
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/admin/users/1  # 302 (redirect zu Login, da kein Auth)

# Nach Issue I-05
.venv/bin/pytest tests/test_admin_user_detail.py -v  # 12 Tests grün
.venv/bin/pytest tests/ -q  # >= 116 Tests, alle grün
```
