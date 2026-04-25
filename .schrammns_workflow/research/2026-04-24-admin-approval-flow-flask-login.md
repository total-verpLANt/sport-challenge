# Research: Admin-Approval-Flow für Flask-Login

**Date:** 2026-04-24
**Scope:** app/models/user.py, app/routes/auth.py, app/utils/decorators.py, app/extensions.py, app/__init__.py, tests/, migrations/versions/

---

## Executive Summary

- Das aktuelle Auth-System hat **kein Approval-Gate**: Register → sofort `login_user()`. Kein erster-Admin-Bootstrap.
- Flask-Login's `UserMixin.is_active` gibt hardcoded `True` zurück. **Override auf `self.is_approved`** ist der korrekte, dokumentierte Weg zum Blockieren inaktiver User – zusätzlich zur manuellen Prüfung im View.
- **Empfohlene Strategie:** `is_approved` bool-Feld (nicht State-Machine), erster User wird automatisch Admin+approved (Immich-Muster), Login zeigt "pending" nur nach korrekter Password-Prüfung.
- 5 atomare Issues decken alles ab: Model+Migration → Register-Logik → Login-Logik → Admin-Blueprint → Tests.
- **Risiko:** Migration ist irreversibel; bestehende User müssen via Alembic-`op.execute()` auf `is_approved=True` gesetzt werden.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/models/user.py` | User-Model (UserMixin, scrypt, is_admin-Property) |
| `app/routes/auth.py` | Login/Register/Logout-Routes |
| `app/utils/decorators.py` | `admin_required` Decorator (exists, unused) |
| `app/extensions.py` | LoginManager (login_view gesetzt, kein unauthorized_handler) |
| `app/__init__.py` | App-Factory, user_loader |
| `tests/conftest.py` | Fixtures: app (session), db (function), client (function) |
| `tests/test_auth.py` | 6 Tests (register, login, rate-limit, CSRF) |
| `migrations/versions/3e27b32f8e92_users_table.py` | users-Tabelle Schema |

---

## Technology Stack

| Library | Version | Role |
|---------|---------|------|
| Flask-Login | current | Session-Management, `@login_required`, `UserMixin` |
| Flask-SQLAlchemy | current | ORM, Mapped-Columns |
| Flask-Migrate (Alembic) | current | DB-Migrationen |
| Flask-WTF | current | CSRF-Schutz |
| Flask-Limiter | current | Rate-Limiting auf Routes |

---

## Findings

### F-01: User-Model – fehlende Felder

**File:** `app/models/user.py:1-33`

Aktuell vorhandene Spalten:
- `id`, `email`, `password_hash`, `role` (default `"user"`), `created_at`

Fehlend für Approval-Flow:
- `is_approved: bool` (default `False`) – Gate für Login
- `approved_at: datetime | None` – Audit-Timestamp
- `approved_by_id: int | None` – FK auf approving admin (optional, aber sauber)

**Flask-Login `is_active`:** `UserMixin` gibt hardcoded `True` zurück (`app/models/user.py:11`). Override via Property `is_active → self.is_approved` bewirkt, dass `login_user()` für unapproved User automatisch False zurückgibt (defense-in-depth). Zusätzliche manuelle Prüfung im View nötig für die spezifische Fehlermeldung.

### F-02: Register-Route – kein Gate, kein Immich-Bootstrap

**File:** `app/routes/auth.py:34-59`

Zeile 53-58: Neuer User wird erstellt und sofort per `login_user(user)` eingeloggt. 

Keine Prüfung ob DB leer ist (→ erster User). Immich-Muster: `if db.session.execute(db.select(func.count()).select_from(User)).scalar() == 0` → setze `role="admin"`, `is_approved=True`.

Zweite+ User: `is_approved=False`, **kein** `login_user()`, Redirect auf Login mit Flash-Meldung "Registrierung erfolgreich – warte auf Admin-Freigabe."

### F-03: Login-Route – kein Pending-Check

**File:** `app/routes/auth.py:10-31`

Zeile 26: `if user and user.check_password(password): login_user(user)` – keine Approval-Prüfung.

Korrekter Flow (kein Info-Leak):
1. `user = db.session.execute(...)` – User laden
2. `if user and user.check_password(password):` – Credentials prüfen
3.   `if not user.is_approved:` → Fehlermeldung "pending", **kein** `login_user()`
4.   `else:` → `login_user(user)`, Redirect
5. `else:` → "Ungültige Anmeldedaten." (unverändert)

Dieser Flow verrät Approval-Status **nur nach korrektem Passwort** – kein Email-Enumeration-Leak.

### F-04: Kein Admin-Blueprint

**File:** `app/routes/` – kein `admin.py`

`@admin_required` Decorator existiert (`app/utils/decorators.py:7-13`), wird aber nirgendwo verwendet. Neuer Blueprint `admin_bp` mit:
- `GET /admin/users` – Liste aller User nach Status (pending / approved)
- `POST /admin/users/<int:user_id>/approve` – CSRF-geschützt, sets `is_approved=True`, `approved_at=now()`
- `POST /admin/users/<int:user_id>/reject` – CSRF-geschützt, löscht User (oder setzt rejected-Status)

### F-05: Test-Lücken

**File:** `tests/test_auth.py` – 6 Tests, alle ohne Approval-Logik

Fehlende Test-Cases (9):
1. Erster User → admin + approved, Redirect auf Activities
2. Zweiter User → is_approved=False, kein Auto-Login, Redirect auf Login mit Meldung
3. Unapproved User + korrektes PW → "pending"-Meldung, Session leer
4. Unapproved User + falsches PW → "Ungültige Anmeldedaten" (nicht "pending")
5. Admin kann pending Users auflisten (GET /admin/users, Status 200)
6. Admin kann User approvieren (POST /admin/users/<id>/approve)
7. Admin kann User ablehnen/löschen (POST /admin/users/<id>/reject)
8. Non-Admin → 403 auf /admin/users
9. Unauthenticated → 302 Redirect auf /auth/login für /admin/users

### F-06: Migration-Strategie

**Existing migrations:** `3e27b32f8e92_users_table.py`, `897dbbcea723_connector_credentials.py`

Neue Migration (A-01) muss:
1. Spalten `is_approved`, `approved_at`, `approved_by_id` hinzufügen
2. **Backfill:** Bestehende User auf `is_approved=True` setzen (sonst werden alle bestehenden User gesperrt)
3. Alembic `downgrade()` implementieren (Spalten wieder entfernen)

Backfill-Syntax:
```python
op.execute("UPDATE users SET is_approved = 1 WHERE is_approved IS NULL")
```

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| User-Model Struktur | 4 | Alle Felder und Properties gelesen, Migrations-Historie bekannt |
| Login/Register Flow | 4 | Zeile für Zeile nachvollzogen, Approval-Lücken exakt identifiziert |
| Flask-Login is_active | 3 | Dokumentation + UserMixin-Verhalten bekannt; login_user() prüft is_active |
| Admin-Blueprint (fehlt) | 2 | Pattern aus decorators.py bekannt; Route-Design klar, kein Code vorhanden |
| Test-Fixtures | 4 | conftest.py vollständig gelesen, Fixture-Scope und Cleanup verstanden |
| Migration-Backfill | 3 | Pattern aus vorhandenen Migrations bekannt; Backfill-SQL definiert |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Admin-Benachrichtigung bei Registrierung | nice-to-have | Flask-Mail / externe E-Mail-Lösung evaluieren |
| User-Benachrichtigung bei Approve/Reject | nice-to-have | Wie oben |
| Rejected-State vs. Delete | nice-to-have | Entscheidung: einfach löschen (MVP) oder `approval_status`-Feld mit "rejected" |
| Navbar-Badge "N pending users" für Admin | nice-to-have | Context-Processor oder Jinja-Macro |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `UserMixin.is_active` gibt hardcoded True zurück | Yes | Flask-Login Docs + Context7 Query |
| `login_user()` prüft `is_active` vor Session-Erstellung | Yes | Flask-Login Docs (login_user refuses if is_active=False) |
| CSRF ist für alle POST-Requests aktiv | Yes | `app/extensions.py:18` + `conftest.py` WTF_CSRF_ENABLED=False für Tests |
| Bestehende User haben keine `is_approved`-Spalte | Yes | `migrations/versions/3e27b32f8e92_users_table.py` gelesen |
| `@admin_required` schützt auch ohne separate Prüfung | Yes | `app/utils/decorators.py:7-13` – stacked mit `login_required` |
| Rate-Limiting auf Admin-Routes nicht nötig (MVP) | No | Annahme – Admin-Aktionen sind niedrigfrequent |

---

## Recommendations

### Issue A-01: User-Model + Migration
- Neue Spalten: `is_approved BOOLEAN NOT NULL DEFAULT 0`, `approved_at DATETIME`, `approved_by_id INTEGER FK`
- `is_active` Property überschreiben → `return self.is_approved` (defense-in-depth)
- Migration-Backfill: `UPDATE users SET is_approved = 1` für alle bestehenden User
- Betroffene Dateien: `app/models/user.py`, neue Migrations-Datei

### Issue A-02: Register-Route anpassen
- Ersten User detektieren via `COUNT(*)` Query
- Erster User: `role="admin"`, `is_approved=True`, `login_user()`, Redirect
- Weitere User: `is_approved=False`, kein `login_user()`, Flash + Redirect auf Login
- Betroffene Datei: `app/routes/auth.py`

### Issue A-03: Login-Route anpassen
- Nach Password-Check: `if not user.is_approved` → Fehlermeldung (nur nach korrektem PW)
- Kein `login_user()` für unapproved User
- Betroffene Datei: `app/routes/auth.py`

### Issue A-04: Admin-Blueprint
- Neue Datei: `app/routes/admin.py` + Blueprint-Registrierung in `app/__init__.py`
- Routes: GET `/admin/users`, POST `/admin/users/<id>/approve`, POST `/admin/users/<id>/reject`
- Templates: `app/templates/admin/users.html`
- Schutz via `@admin_required`

### Issue A-05: Tests
- 9 neue Test-Functions in `tests/test_auth.py` (oder neues `tests/test_approval.py`)
- Fixture-Erweiterung: Helper um Admin-User + pending User schnell zu erzeugen
