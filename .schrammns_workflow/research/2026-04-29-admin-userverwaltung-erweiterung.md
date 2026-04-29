# Research: Admin-Userverwaltung Erweiterung

**Date:** 2026-04-29
**Scope:** Admin-Routen, User-Model, Templates, Test-Infrastruktur

## Executive Summary

- **Pending-State existiert bereits** – `is_approved=False` ist der einzige Mechanismus; `is_active` leitet sich direkt daraus ab. „Sperren" = `is_approved=False` setzen reicht aus.
- **User-Detail-Ansicht fehlt komplett** – es gibt nur eine Listenseite (`admin/users.html`), keine Detailseite. Alles Admin-Aktionen (Approve, Reject, Toggle-Admin) werden per POST direkt aus der Liste ausgelöst.
- **Passwort-Reset fehlt** – kein Flow, kein Token, kein Admin-Tool. Muss neu implementiert werden.
- **Löschen ist gefährlich ohne Cascade** – `ConnectorCredential`, `Activity`, `ChallengeParticipation`, `SickWeek`, `PenaltyOverride`, `BonusChallengeEntry` haben FK auf `users.id` ohne `ondelete="CASCADE"`. Ein `db.session.delete(user)` bei Usern mit Daten führt zu `IntegrityError`.
- **Empfehlung:** Sperren via `is_approved`-Toggle, Löschen nur mit explizitem Cascade oder manuellem Vorlöschen aller abhängiger Datensätze, User-Detail als neue Route `/admin/users/<id>`.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/admin.py` | Admin-Blueprint, alle Admin-Routen |
| `app/models/user.py` | User-Model mit allen Feldern und Properties |
| `app/models/connector.py` | ConnectorCredential – FK auf users.id, KEIN CASCADE |
| `app/models/activity.py` | Activity – FK auf users.id, KEIN CASCADE von User-Seite |
| `app/templates/admin/users.html` | Einziges Admin-Template (Listenseite) |
| `app/utils/decorators.py` | `admin_required` Decorator |
| `tests/test_admin.py` | 7 Tests für Toggle-Admin |
| `tests/test_auth.py` | 12 Tests für Register/Login/Lockout |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Flask-Login | - | Session-Management, `is_active` aus User-Model |
| SQLAlchemy | - | ORM, Relationship-Cascade muss manuell gesetzt werden |
| Flask-WTF / CSRF | - | CSRF-Schutz auf POST-Routen |
| Flask-Limiter | - | Rate-Limit auf Auth-Routen |
| Bootstrap 5.3.3 | 5.3.3 | UI-Framework für Templates |

---

## Findings

### 1. User-Model (app/models/user.py)

Alle Felder:

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primary Key |
| `email` | str(255) | unique, not null |
| `nickname` | str(30) | unique, nullable |
| `password_hash` | str(256) | scrypt N=131072 |
| `role` | str(32) | `"user"` oder `"admin"` |
| `created_at` | datetime(tz) | auto now(UTC) |
| `is_approved` | bool | default False – **Pending-Mechanismus** |
| `approved_at` | datetime(tz) | nullable |
| `approved_by_id` | int | FK → users.id, nullable |
| `failed_login_attempts` | int | default 0 – Brute-Force-Schutz |
| `locked_until` | datetime(tz) | nullable – Brute-Force-Lockout |

Properties:
- `display_name` → nickname oder E-Mail-Lokalteil
- `is_active` → **gibt `self.is_approved` zurück** (Flask-Login überschrieben!)
- `is_admin` → `role == "admin"`

### 2. Pending/Sperren-Mechanismus

`is_approved=False` ist der vollständige "Pending"- bzw. "Gesperrt"-State:
- Login-Route prüft `is_approved` vor `login_user()`: "Konto wartet auf Admin-Freigabe."
- Flask-Login `is_active` gibt `is_approved` zurück → automatisch ausgeloggt bei Sperre
- Kein separates `suspended`- oder `locked`-Feld nötig
- **Empfehlung:** Sperren = `is_approved=False`, Entsperren = `is_approved=True`
- `locked_until` ist Brute-Force-Lockout, nicht Admin-Sperre → nicht zweckentfremden

### 3. Bestehende Admin-Routen (app/routes/admin.py)

| URL | Methode | Funktion |
|-----|---------|----------|
| `/admin/users` | GET | Liste aller User |
| `/admin/users/<id>/approve` | POST | `is_approved=True` |
| `/admin/users/<id>/reject` | POST | `db.session.delete(user)` – nur sicher für Pending-User! |
| `/admin/users/<id>/toggle-admin` | POST | Role admin ↔ user |

Guards: Self-Edit blockiert, Last-Admin-Guard in toggle-admin.

### 4. Kein Cascade-Delete – kritisch!

`ConnectorCredential.user_id` → ForeignKey ohne `ondelete="CASCADE"`:
```python
# app/models/connector.py:31
user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
```

Gleiche Situation in:
- `Activity` (FK `users.id`)
- `ChallengeParticipation` (FK `users.id`)
- `SickWeek` (FK `users.id`)
- `PenaltyOverride` (FK `users.id`, `set_by_id`)
- `BonusChallengeEntry` (FK `users.id`)

**Konsequenz:** `reject_user()` in admin.py (Zeile 57: `db.session.delete(user)`) funktioniert nur für Pending-User (die noch keine Daten haben). Für approved User mit Aktivitäten/Challenges wäre das ein `IntegrityError`.

**Lösung für Löschen-Feature:** Explizites manuelles Löschen aller abhängiger Records in der richtigen Reihenfolge (kein Cascade auf DB-Ebene nötig – nur per ORM sicherstellen).

### 5. Integrations-Anzeige (ConnectorCredential)

```python
# app/models/connector.py – relevante Felder
provider_type  # z.B. "garmin", "strava"
user_id        # FK → users.id
credentials    # Fernet-verschlüsselt (JSON)
```

Für die Detailansicht: `ConnectorCredential.query.filter_by(user_id=user.id).all()` – gibt alle eingerichteten Integrationen zurück. Nur `provider_type` anzeigen, nie `credentials`.

### 6. Test-Infrastruktur

- `test_admin.py` hat 7 Tests für `toggle-admin`, eigene `_create_and_login`-Helper
- User in Tests: `User(email=email, is_approved=True)` + `set_password()` + direkter `role`-Zugriff
- Neue Tests müssen zum selben Pattern passen
- Kein Passwort-Reset-Test vorhanden → Feature neu anlegen

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| User-Model und Felder | 4 | Vollständig gelesen, alle Properties verstanden |
| Bestehende Admin-Routen | 4 | Alle Routen bekannt, Guards bekannt |
| Pending/Sperren-Mechanismus | 4 | `is_approved` = is_active, klar |
| Cascade-Delete-Problematik | 3 | FKs bekannt, Lösung skizziert |
| Template-Struktur | 2 | Nur ein Template existiert, Inhalt nicht gelesen |
| Test-Infrastruktur | 3 | Pattern bekannt, keine Unit-Tests für neue Features |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Exakter Inhalt `admin/users.html` | nice-to-have | Read template |
| Alle FKs die auf users.id zeigen vollständig inventarisiert? | must-fill | `grep -r "ForeignKey.*users.id"` |
| Wird `activity.challenge_id` beim User-Löschen zum Problem? | must-fill | Prüfe ob ON DELETE SET NULL nötig |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `is_active` gibt `is_approved` zurück | Yes | `app/models/user.py` (property) |
| `locked_until` ist Brute-Force, nicht Admin-Sperre | Yes | `app/routes/auth.py` Lockout-Logik |
| Reject-Flow bei bestehenden Usern = IntegrityError | Yes (logisch) | FKs ohne CASCADE in connector.py, activity.py |
| Nur Pending-User können sicher per reject_user() gelöscht werden | Yes | `db.session.delete(user)` ohne Cascade |
| Sperren via `is_approved=False` funktioniert ohne Modell-Änderung | Yes | `is_active` Property leitet sich darauf ab |

---

## Web Research – Best Practices

### User Suspension
- Flask-Login's `is_active`-Property ist der Standard-Mechanismus für Sperren – exakt das, was das Projekt bereits nutzt. Suspended User können sich nicht einloggen; bestehende Sessions werden beim nächsten Request invalidiert. ✅ Unsere Implementierung via `is_approved=False` ist idiomatisch.
- Quelle: [Flask-Login Docs](https://flask-login.readthedocs.io/), [WorkOS Flask Auth 2026](https://workos.com/blog/top-authentication-solutions-flask-2026)

### Admin Password Reset
- Direktes Admin-Password-Set (kein Token-Flow) ist für interne Admin-Panels ein valides Muster. Token-Flows sind für Self-Service (vergessenes Passwort) gedacht, nicht für Admin-Reset.
- Wichtig: Passwort-Mindestlänge validieren, CSRF schützen, nie gehashtes PW loggen.
- Quelle: [Flask Password Reset Tutorial](https://freelancefootprints.substack.com/p/yet-another-password-reset-tutorial)

### Hard Delete vs. Soft Delete
- **Hard Delete** (was wir implementieren): Vollständiges Entfernen aller User-Daten. Korrekt für DSGVO-„Recht auf Vergessenwerden". Tokens, Session-Daten und Auth-Hashes müssen tatsächlich gelöscht werden – Soft-Delete bei kompromittierten Credentials ist eine Sicherheitslücke.
- **Soft Delete** (deleted_at-Timestamp): Vorteil bei Audit-Trails und Undo-Funktionalität; Nachteil bei DSGVO-Compliance.
- **Empfehlung für dieses Projekt:** Hard Delete mit manuellem Cascade (kein GDPR-Problem, kein Soft-Delete-Overhead). Bestätigungsdialog im UI als Schutz vor Versehen.
- Quelle: [Soft vs Hard Delete – DEV Community](https://dev.to/akarshan/the-delete-button-dilemma-when-to-soft-delete-vs-hard-delete-3a0i), [Soft Delete Antipattern](https://www.cultured.systems/2024/04/24/Soft-delete/)

---

## Recommendations

### Neue Features implementieren in dieser Reihenfolge:

**1. User-Detail-Route** (`/admin/users/<int:user_id>`)
- Zeigt: email, nickname, role, is_approved, created_at, approved_at/by
- Zeigt: ConnectorCredential-Liste (nur provider_type, nie credentials)
- Template: `admin/user_detail.html` (neu)
- Kein Migrationsaufwand

**2. Sperren/Entsperren** (`POST /admin/users/<id>/suspend`, `/unsuspend`)
- Setzt `is_approved=False` (Sperren) oder `is_approved=True` (Entsperren)
- Self-Sperren blockieren
- Flask-Login wirft gesperrte User beim nächsten Request automatisch raus (is_active=False)
- Flash-Meldung: "Konto gesperrt." / "Konto entsperrt."
- Kein Migrationsaufwand

**3. Passwort-Reset durch Admin** (`POST /admin/users/<id>/reset-password`)
- Admin setzt neues Passwort direkt (kein Token, kein E-Mail-Flow)
- Form: Neues Passwort + Bestätigung (min. 8 Zeichen)
- Ruft `user.set_password(new_password)` auf
- Security: Nur auf Detail-Page, CSRF-Schutz, Passwort-Mindestlänge validieren
- Kein Migrationsaufwand

**4. User löschen** (`POST /admin/users/<id>/delete`)
- Komplexer wegen fehlender Cascade!
- Strategie: Manuelles Löschen in Reihenfolge:
  1. BonusChallengeEntry
  2. PenaltyOverride
  3. SickWeek
  4. ActivityMedia (via Activity-Cascade)
  5. Activity
  6. ChallengeParticipation
  7. ConnectorCredential
  8. User selbst
- **Kein Migrationsaufwand** (kein Schema-Change nötig wenn manuell gelöscht wird)
- Alternativ: CASCADE auf DB-Ebene via Migration (sauberer, aber riskanter)
- Bestätigungs-Dialog im UI (destruktiv!)
- Self-Delete und Last-Admin-Delete blockieren

### Security-Hinweise:
- Alle neuen Aktionen: CSRF-Schutz via Flask-WTF (POST-only)
- Passwort nie im Response zurückgeben oder loggen
- Admin-Aktionen auf eigene User (self-edit) immer blockieren
- Löschen nur wenn kein anderer Admin vorhanden → Last-Admin-Guard auch hier
