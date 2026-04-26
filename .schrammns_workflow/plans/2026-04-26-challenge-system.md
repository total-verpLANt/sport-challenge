# Plan: Challenge-System für Sport Challenge

**Date:** 2026-04-26
**Goal:** Implementierung des vollständigen Challenge-Systems mit Dashboard, Aktivitäts-Tracking, Strafberechnung, Bonus-Challenges und Responsive Design
**Research:** `.schrammns_workflow/research/2026-04-26-challenge-system-bestandsaufnahme.md`

## Baseline Audit

| Metric | Value | Verification |
|--------|-------|-------------|
| Python-Dateien (app/) | 17 | `find ./app -name "*.py" \| wc -l` = 17 |
| HTML-Templates | 7 | `find . -name "*.html" -not -path "./.venv/*" \| wc -l` = 7 |
| Total Python LOC | 2051 | `wc -l` across all .py files |
| Tests | 41 passing | `SECRET_KEY=test pytest -v` = 41 passed |
| TODO/FIXME/HACK | 0 | `grep -rc "TODO\|FIXME" . --exclude-dir=.venv` = 0 |
| Git status | clean (main) | `git status` = clean |
| Upload infrastructure | none | `grep -r "multipart\|request.files\|upload" app/` = 0 |

## Design Decisions

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| Screenshot-Speicherung | Lokal `app/static/uploads/` | S3/Cloud | Einfach, kleine Nutzerzahl, vom Kapitän bestätigt |
| Formular-Pattern | Raw HTML + CSRF | WTForms | Konsistenz mit bestehendem Code |
| Strafberechnung | Automatisch via Python-Logik | DB-Trigger | Testbar, transparent, Admin-Override möglich |
| Dashboard-Layout | Bootstrap Table + responsive wrapper | JS-Framework (React/Vue) | Kein Build-Tooling, CDN-only Pattern beibehalten |
| Aktivitäts-Import | User wählt aus Connector-Liste | Vollautomatisch | Vom Kapitän gewünscht: bewusste Auswahl |
| Upload-Limit | 5 MB, JPEG/PNG/WebP | Unbegrenzt | Sicherheit: Speicherplatz + Payload-Schutz |

## Boundaries

**Always:**
- Alle neuen Templates erben von `base.html` und nutzen `{% block content %}`
- Alle POST-Formulare enthalten `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- Alle neuen Routes nutzen `@login_required` oder `@admin_required`
- Responsive Design: Bootstrap Grid, `table-responsive` Wrapper, touch-freundliche Inputs
- File-Upload: UUID-Dateinamen, Typ-Validierung server-seitig, Größenlimit 5 MB
- Migrationen: `batch_alter_table` für SQLite-Kompatibilität
- Tests: Jedes neue Model und jede Route bekommt Tests in `tests/`

**Never:**
- Niemals Dateinamen vom Client übernehmen (Path-Traversal-Schutz)
- Niemals Strafen ohne Berücksichtigung von Krankheits-Wochen berechnen
- Niemals Upload-Dateien außerhalb von `app/static/uploads/` speichern
- Niemals hardcodierte Beträge (5€, 25€) — als Challenge-Konfiguration speichern

**Ask First:**
- (resolved) Screenshot-Speicherung: lokal gewählt

## Files to Modify

| File | Change |
|------|--------|
| `app/models/challenge.py` | **NEW** — Challenge, ChallengeParticipation Models |
| `app/models/activity.py` | **NEW** — Activity Model (manuelle + importierte Einträge) |
| `app/models/sick_week.py` | **NEW** — SickWeek Model |
| `app/models/bonus.py` | **NEW** — BonusChallenge, BonusChallengeEntry Models |
| `app/models/penalty.py` | **NEW** — PenaltyOverride Model |
| `app/routes/challenges.py` | **NEW** — Challenge-CRUD (Admin), Einladungen, Annahme/Bailout |
| `app/routes/challenge_activities.py` | **NEW** — Manuelle Aktivitäts-Eingabe, Connector-Import, Screenshot-Upload |
| `app/routes/dashboard.py` | **NEW** — Dashboard/Leaderboard-Startseite |
| `app/routes/bonus.py` | **NEW** — Bonus-Challenge-Verwaltung + Zeiteingabe |
| `app/services/__init__.py` | **NEW** — (leer) |
| `app/services/penalty.py` | **NEW** — Strafberechnungs-Logik |
| `app/services/weekly_summary.py` | **NEW** — Wochen-Aggregation für Dashboard |
| `app/utils/uploads.py` | **NEW** — Upload-Handling: Validierung, UUID-Benennung, Speicherung |
| `app/templates/challenges/index.html` | **NEW** — Challenge-Übersicht |
| `app/templates/challenges/create.html` | **NEW** — Challenge anlegen (Admin) |
| `app/templates/challenges/detail.html` | **NEW** — Challenge-Detail mit Einladungen |
| `app/templates/challenges/invite.html` | **NEW** — Einladungs-Ansicht für User |
| `app/templates/activities/log.html` | **NEW** — Manuelle Aktivitäts-Eingabe |
| `app/templates/activities/import.html` | **NEW** — Connector-Import-Auswahl |
| `app/templates/dashboard/index.html` | **NEW** — Leaderboard/Wochenübersicht |
| `app/templates/bonus/index.html` | **NEW** — Bonus-Challenge-Übersicht + Rangliste |
| `app/templates/bonus/entry.html` | **NEW** — Bonus-Zeiteingabe |
| `app/__init__.py` | Neue Blueprints registrieren, Root-Route auf Dashboard ändern, Upload-Config |
| `app/templates/base.html` | Navbar-Links erweitern (Dashboard, Challenge) |
| `config.py` | `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH` hinzufügen |
| `migrations/versions/` | **NEW** — Migration für alle neuen Tabellen |
| `tests/test_challenge.py` | **NEW** — Challenge-Model + Route-Tests |
| `tests/test_activities_log.py` | **NEW** — Aktivitäts-Eingabe + Upload-Tests |
| `tests/test_penalty.py` | **NEW** — Strafberechnungs-Tests |
| `tests/test_dashboard.py` | **NEW** — Dashboard-Route-Tests |
| `tests/test_bonus.py` | **NEW** — Bonus-Challenge-Tests |

## Implementation

### Wave 1: Datenmodell + Upload-Infrastruktur (keine Abhängigkeiten)

#### Issue 1.1: Challenge + Participation Models
**Size:** M
**Risk:** `irreversible / system / requires-approval` (DB-Migration)

Erstelle `app/models/challenge.py`:

```python
class Challenge(db.Model):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    penalty_per_miss: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    bailout_fee: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    
    participations = db.relationship("ChallengeParticipation", back_populates="challenge")

class ChallengeParticipation(db.Model):
    __tablename__ = "challenge_participations"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    weekly_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 2 oder 3
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
        # invited, accepted, bailed_out
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    accepted_at: Mapped[datetime | None] = mapped_column(...)
    bailed_out_at: Mapped[datetime | None] = mapped_column(...)
    
    challenge = db.relationship("Challenge", back_populates="participations")
    user = db.relationship("User")
```

**Acceptance:** `SECRET_KEY=test pytest -v` passes, `flask db upgrade` succeeds, Models importierbar.

#### Issue 1.2: Activity Model
**Size:** M
**Risk:** `irreversible / system / requires-approval` (DB-Migration)

Erstelle `app/models/activity.py`:

```python
class Activity(db.Model):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
        # manual, garmin, strava
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

**Acceptance:** Model importierbar, Migration erstellt, Test für Roundtrip (Create/Query) besteht.

#### Issue 1.3: SickWeek + PenaltyOverride Models
**Size:** S
**Risk:** `irreversible / system / requires-approval` (DB-Migration)

Erstelle `app/models/sick_week.py`:

```python
class SickWeek(db.Model):
    __tablename__ = "sick_weeks"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "week_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)  # Montag der Woche
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

Erstelle `app/models/penalty.py`:

```python
class PenaltyOverride(db.Model):
    __tablename__ = "penalty_overrides"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", "week_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    override_amount: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    set_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

**Acceptance:** Models importierbar, Migration erstellt, UniqueConstraints greifen (Test).

#### Issue 1.4: BonusChallenge + BonusChallengeEntry Models
**Size:** S
**Risk:** `irreversible / system / requires-approval` (DB-Migration)

Erstelle `app/models/bonus.py`:

```python
class BonusChallenge(db.Model):
    __tablename__ = "bonus_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="50 Squat Jumps")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)

class BonusChallengeEntry(db.Model):
    __tablename__ = "bonus_challenge_entries"
    __table_args__ = (UniqueConstraint("user_id", "bonus_challenge_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bonus_challenge_id: Mapped[int] = mapped_column(ForeignKey("bonus_challenges.id"), nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

**Acceptance:** Models importierbar, Roundtrip-Test, UniqueConstraint-Test.

#### Issue 1.5: Upload-Utility + Config
**Size:** S
**Risk:** `reversible / local / autonomous-ok`

Erstelle `app/utils/uploads.py`:

```python
import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file) -> str | None:
    """Speichert Upload mit UUID-Dateiname. Gibt relativen Pfad zurück oder None bei Fehler."""
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    file.save(filepath)
    return f"uploads/{filename}"

def delete_upload(relative_path: str) -> None:
    """Löscht eine Upload-Datei."""
    if not relative_path:
        return
    filepath = Path(current_app.static_folder) / relative_path
    if filepath.exists():
        filepath.unlink()
```

Erweitere `config.py`:

```python
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
```

**Acceptance:** `save_upload()` Test mit Fake-FileStorage, `allowed_file()` mit validen/invaliden Extensions, `delete_upload()` Test.

#### Issue 1.6: Alembic-Migration für alle neuen Models
**Size:** S
**Risk:** `irreversible / external / requires-approval`

Erstelle eine einzelne Alembic-Migration für alle 7 neuen Tabellen (challenges, challenge_participations, activities, sick_weeks, penalty_overrides, bonus_challenges, bonus_challenge_entries).

Alle neuen Models müssen in `app/__init__.py` importiert werden (noqa-Imports für Alembic autogenerate).

**Acceptance:** `flask db upgrade` erfolgreich, `flask db downgrade` möglich, alle Tabellen existieren in SQLite.

### Wave 2: Strafberechnung + Challenge-Verwaltung (hängt von Wave 1 ab)

#### Issue 2.1: Strafberechnungs-Service
**Size:** M
**Risk:** `reversible / local / autonomous-ok`

Erstelle `app/services/penalty.py`:

```python
def get_week_mondays(start_date: date, end_date: date) -> list[date]:
    """Gibt alle Montage im Challenge-Zeitraum zurück."""

def count_fulfilled_days(user_id: int, challenge_id: int, week_start: date) -> int:
    """Zählt Tage mit >=30 Min Gesamtdauer in einer Woche."""
    # SELECT activity_date, SUM(duration_minutes)
    # FROM activities WHERE user_id=... AND challenge_id=...
    # AND activity_date BETWEEN week_start AND week_start+6
    # GROUP BY activity_date
    # HAVING SUM(duration_minutes) >= 30

def calculate_weekly_penalty(user_id: int, challenge_id: int, week_start: date, weekly_goal: int) -> float:
    """Berechnet Strafe für eine Woche. Berücksichtigt SickWeek + PenaltyOverride."""
    # 1. Prüfe SickWeek → 0€
    # 2. Prüfe PenaltyOverride → override_amount
    # 3. fulfilled = count_fulfilled_days(...)
    # 4. missed = max(0, weekly_goal - fulfilled)
    # 5. return missed * challenge.penalty_per_miss

def calculate_total_penalty(user_id: int, challenge_id: int) -> float:
    """Summiert alle Wochen-Strafen. Für Bailout: + bailout_fee."""
```

**Acceptance:** Tests für:
- `test_no_penalty_when_goal_met` (3/3 Tage → 0€)
- `test_penalty_for_missed_days` (1/3 Tage → 10€)
- `test_max_penalty_capped` (0/3 Tage → 15€)
- `test_sick_week_no_penalty`
- `test_penalty_override_applied`
- `test_two_per_week_goal` (2x-Ziel: 0/2 → 10€)
- `test_bailout_includes_fee` (Strafen + 25€)

#### Issue 2.2: Challenge-Routes (Admin-CRUD + Einladungen)
**Size:** L
**Risk:** `reversible / system / requires-approval`

Erstelle `app/routes/challenges.py` mit `challenges_bp` (url_prefix="/challenges"):

- `GET /challenges/` — Aktive Challenge anzeigen (oder "keine Challenge" wenn keine aktiv)
- `GET /challenges/create` — Challenge-Erstellformular (Admin)
- `POST /challenges/create` — Challenge speichern (Name, Start, Ende, penalty_per_miss, bailout_fee)
- `GET /challenges/<id>` — Challenge-Detail (Teilnehmer, Status)
- `POST /challenges/<id>/invite` — User einladen (Admin, wählt aus approved Users)
- `POST /challenges/<id>/accept` — Einladung annehmen (setzt weekly_goal)
- `POST /challenges/<id>/decline` — Einladung ablehnen
- `POST /challenges/<id>/bailout` — Aus Challenge austreten
- `POST /challenges/<id>/sick` — Krankheitsmeldung für aktuelle Woche

Registriere Blueprint in `app/__init__.py`.

**Acceptance:** Admin kann Challenge erstellen, User einladen, User kann annehmen/ablehnen, Bailout funktioniert, Krankheitsmeldung wird gespeichert. Tests für alle Routes.

#### Issue 2.3: Challenge-Templates (Admin + User)
**Size:** M
**Risk:** `reversible / local / autonomous-ok`

Erstelle Templates:
- `challenges/index.html` — Aktive Challenge-Übersicht, Pending-Einladungen
- `challenges/create.html` — Erstellformular mit Datepickern
- `challenges/detail.html` — Teilnehmer-Tabelle, Einlade-Button (Admin), Accept/Decline/Bailout/Sick (User)
- `challenges/invite.html` — Einladungs-Ansicht mit Ziel-Wahl (2x/3x)

Alle responsive: Bootstrap Grid, touch-freundliche Inputs, mobile-optimierte Tabellen.

**Acceptance:** Alle Templates rendern fehlerfrei, responsiv auf 375px Viewport.

### Wave 3: Aktivitäts-Eingabe + Import (hängt von Wave 2 ab)

#### Issue 3.1: Manuelle Aktivitäts-Eingabe + Screenshot-Upload
**Size:** L
**Risk:** `reversible / system / autonomous-ok`

Erstelle `app/routes/challenge_activities.py` mit `challenge_activities_bp` (url_prefix="/challenge-activities"):

- `GET /challenge-activities/log` — Eingabe-Formular (Datum, Dauer, Sportart, Screenshot)
- `POST /challenge-activities/log` — Aktivität speichern (mit Upload-Handling)
- `GET /challenge-activities/my` — Meine Aktivitäten dieser Woche (mit Tages-Summen + 30-Min-Hinweis)
- `POST /challenge-activities/<id>/delete` — Eigene Aktivität löschen (+ Screenshot löschen)

Formular: `enctype="multipart/form-data"`, `accept="image/*"` für Kamera auf Mobile.
Upload via `save_upload()` aus `app/utils/uploads.py`.

Erstelle Templates:
- `activities/log.html` — Eingabe-Formular, responsiv
- `activities/my_week.html` — Wochenübersicht eigene Aktivitäten, Tages-Summen, 30-Min-Warnung

Registriere Blueprint in `app/__init__.py`.

**Acceptance:**
- Manuelle Eingabe speichert Activity in DB
- Screenshot wird hochgeladen und Pfad gespeichert
- Dateien >5MB werden abgelehnt
- Nur JPEG/PNG/WebP erlaubt
- Tages-Summe wird korrekt berechnet
- 30-Min-Hinweis erscheint bei Unterschreitung
- Löschen entfernt Activity + Screenshot

#### Issue 3.2: Connector-Import (Garmin/Strava → Challenge-Activity)
**Size:** M
**Risk:** `reversible / system / autonomous-ok`

Erweitere `app/routes/challenge_activities.py`:

- `GET /challenge-activities/import` — Connector-Aktivitäten der aktuellen Woche laden und anzeigen
- `POST /challenge-activities/import` — Ausgewählte Aktivitäten als Activity-Einträge speichern

Flow:
1. Route nutzt bestehenden Connector-Code (`PROVIDER_REGISTRY`, `connect()`, `get_activities()`)
2. Zeigt Aktivitäten als Checkbox-Liste (Name, Datum, Dauer)
3. User wählt aus, welche importiert werden
4. Erstellt Activity-Einträge mit `source="garmin"/"strava"` und `external_id`
5. Prüft Duplikate via `external_id` (kein doppelter Import)

Erstelle Template:
- `activities/import.html` — Checkbox-Liste der Connector-Aktivitäten, responsiv

**Acceptance:**
- Garmin/Strava-Aktivitäten werden angezeigt
- Import erstellt Activity-Einträge mit korrekter Quelle
- Doppel-Import wird verhindert (external_id Check)

### Wave 4: Dashboard + Bonus-Challenges (hängt von Wave 3 ab)

#### Issue 4.1: Weekly-Summary-Service
**Size:** M
**Risk:** `reversible / local / autonomous-ok`

Erstelle `app/services/weekly_summary.py`:

```python
def get_challenge_summary(challenge_id: int) -> dict:
    """Aggregiert für alle Teilnehmer über alle Wochen:
    {
        "weeks": [date, date, ...],  # Montage
        "participants": [
            {
                "user": User,
                "weekly_goal": int,
                "status": str,
                "weeks": {
                    date: {"fulfilled_days": int, "is_sick": bool, "penalty": float},
                    ...
                },
                "total_penalty": float,
                "display_label": "3+" oder Zahl,
            },
            ...
        ]
    }
    """
```

Nutzt `penalty.count_fulfilled_days()` und `penalty.calculate_weekly_penalty()`.

**Acceptance:** Tests mit verschiedenen Szenarien (volle Woche, teilweise, krank, Bailout).

#### Issue 4.2: Dashboard-Route + Template
**Size:** L
**Risk:** `reversible / system / autonomous-ok`

Erstelle `app/routes/dashboard.py` mit `dashboard_bp` (url_prefix="/dashboard"):

- `GET /dashboard/` — Leaderboard mit Wochenübersicht

Erstelle `app/templates/dashboard/index.html`:
- Tabelle: Zeilen = Teilnehmer, Spalten = Wochen
- Zellen: Anzahl erfüllter Tage, "3+" bei Übererfüllung, Krankheits-Icon
- Strafstand pro Teilnehmer (Summe + aktuell)
- Responsive: horizontales Scrollen auf Mobile (`table-responsive`)
- Bailout-User ausgegraut mit Gesamtstrafe + 25€

Ändere Root-Route in `app/__init__.py`:
```python
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))
```

Aktualisiere Navbar in `base.html`: Dashboard-Link als Hauptlink.

**Acceptance:**
- Dashboard zeigt alle Teilnehmer mit Wochen-Daten
- "3+" wird bei Übererfüllung angezeigt
- Strafstand ist korrekt
- Krankheitswochen sind markiert
- Bailout-User sind sichtbar mit Gesamtkosten
- Responsive auf 375px Viewport

#### Issue 4.3: Bonus-Challenge-Routes + Templates
**Size:** M
**Risk:** `reversible / system / autonomous-ok`

Erstelle `app/routes/bonus.py` mit `bonus_bp` (url_prefix="/bonus"):

- `GET /bonus/` — Übersicht aller Bonus-Challenges mit Ranglisten
- `POST /bonus/<id>/entry` — Zeit eintragen (Sekunden)
- Admin-Routes:
  - `GET /bonus/create` — Bonus-Challenge erstellen
  - `POST /bonus/create` — Speichern (Datum, Beschreibung, Challenge-Zuordnung)

Erstelle Templates:
- `bonus/index.html` — Alle Bonus-Challenges, Rangliste pro Challenge (sortiert nach Zeit aufsteigend)
- `bonus/entry.html` — Zeiteingabe-Formular

Registriere Blueprint in `app/__init__.py`.

**Acceptance:**
- Admin kann Bonus-Challenge erstellen
- User kann Zeit eintragen (nur einmal pro Bonus-Challenge)
- Rangliste zeigt alle Zeiten sortiert
- Responsive Design

### Wave 5: Integration + Navbar + Tests (hängt von Wave 4 ab)

#### Issue 5.1: Navbar-Update + Navigation
**Size:** S
**Risk:** `reversible / local / autonomous-ok`

Aktualisiere `app/templates/base.html`:
- Brand-Link → Dashboard statt Activities
- Neue Nav-Links: "Dashboard", "Meine Aktivitäten", "Bonus"
- Settings-Dropdown: "Challenge" (Admin), bestehende Connectors + Admin Links
- Pending-Einladungs-Badge (Notification-Zähler)

**Acceptance:** Alle Links funktionieren, Navigation ist logisch, responsive Navbar funktioniert.

#### Issue 5.2: Integrations-Tests + E2E-Smoke
**Size:** M
**Risk:** `reversible / local / autonomous-ok`

Erstelle umfassende Tests:

`tests/test_challenge.py`:
- `test_admin_can_create_challenge`
- `test_non_admin_cannot_create_challenge`
- `test_invite_user_to_challenge`
- `test_accept_invitation`
- `test_decline_invitation`
- `test_bailout_from_challenge`
- `test_sick_week_creation`
- `test_duplicate_sick_week_rejected`

`tests/test_activities_log.py`:
- `test_log_manual_activity`
- `test_log_activity_with_screenshot`
- `test_reject_oversized_upload`
- `test_reject_invalid_file_type`
- `test_delete_activity_removes_screenshot`
- `test_daily_summary_above_30min`
- `test_daily_summary_below_30min_shows_warning`

`tests/test_penalty.py`:
- `test_no_penalty_when_goal_met`
- `test_penalty_for_missed_days`
- `test_max_penalty_capped`
- `test_sick_week_no_penalty`
- `test_penalty_override`
- `test_two_per_week_goal`
- `test_bailout_total_includes_fee`

`tests/test_dashboard.py`:
- `test_dashboard_shows_participants`
- `test_dashboard_shows_overachievement`
- `test_dashboard_requires_login`

`tests/test_bonus.py`:
- `test_create_bonus_challenge`
- `test_submit_entry`
- `test_duplicate_entry_rejected`
- `test_ranking_sorted_by_time`

**Acceptance:** Alle Tests bestehen, keine Regression in bestehenden 41 Tests.

## Waves Summary

| Wave | Issues | Parallel? | Approx. Files |
|------|--------|-----------|---------------|
| **1** | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 | 1.1-1.5 parallel, 1.6 after | 8 new + 2 modified |
| **2** | 2.1, 2.2, 2.3 | 2.1 parallel with 2.2+2.3 | 5 new + 1 modified |
| **3** | 3.1, 3.2 | sequential (shared route file) | 3 new + 1 modified |
| **4** | 4.1, 4.2, 4.3 | 4.1 first, then 4.2+4.3 parallel | 5 new + 2 modified |
| **5** | 5.1, 5.2 | parallel | 1 modified + 5 new test files |

**Total: 16 Issues in 5 Waves**

## Invalidation Risks

| Assumption | Risk | Affected Issues |
|------------|------|-----------------|
| SQLite bleibt als DB | Gering — aber SUM/GROUP BY Performance bei vielen Aktivitäten testen | 2.1, 4.1 |
| Bootstrap CDN verfügbar | Minimal — CDN-Ausfall betrifft gesamte App | Alle Templates |
| SECRET_KEY bleibt stabil | Fernet-Mismatch bei Wechsel (bekanntes Problem) | Nur ConnectorCredentials, nicht neue Models |
| Nur eine aktive Challenge | Vereinfacht Logik erheblich — spätere Erweiterung möglich | 2.2, 4.2 |

## Rollback Strategy

- **Git Checkpoint:** Vor Wave 1 einen Tag `pre-challenge-system` setzen
- **Per-Wave:** Jede Wave hat eigene Migration; `flask db downgrade` pro Wave möglich
- **Per-Issue:** Atomare Commits ermöglichen gezieltes `git revert`
- **Upload-Dateien:** `app/static/uploads/` kann komplett gelöscht werden (keine Referenzen außerhalb der DB)
