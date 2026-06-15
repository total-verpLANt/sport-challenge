# Plan: SickWeek → SickPeriod (Von-Bis-Krankmeldungen)

**Datum:** 2026-05-04
**Research:** `.schrammns_workflow/research/2026-05-04-sickweek-umbau-sick-period.md`
**Ziel:** Wochenbasiertes `SickWeek`-Modell durch datumsbasiertes `SickPeriod`-Modell ersetzen. User können Krankzeiträume per Von/Bis eintragen (inkl. Zukunft) und durch Anpassen des Enddatums kürzen.

---

## Design-Entscheidungen

| Thema | Entscheidung | Abgelehnte Alternative | Begründung |
|---|---|---|---|
| end_date nullable | Nein – immer Pflichtfeld | NULL = "noch krank" | Käpt'n: User gibt immer Von + Bis an |
| Überlappende Perioden | Nicht erlaubt; Route-Validierung | DB UniqueConstraint | Kein einfacher DB-Constraint für Datum-Overlap; Validierung in Route |
| Kürzen / "Gesund melden" | Formular pre-filled mit bestehendem Eintrag → Update via sick_period_id | Separater "Gesund-melden"-Button | Einheitliche UI, weniger Routen |
| Legacy-Route `challenges.sick` | Durch Redirect auf log_form ersetzen | Komplett löschen (404-Risiko) | Abwärtskompatibilität der URL erhalten |
| URL-Pfade | `/sick-period` und `/sick-period/<id>/delete` | Alten `/sick-week`-Pfad behalten | Semantische Klarheit; Tests werden sowieso angepasst |

---

## Baseline Audit

| Metrik | Wert | Verifikation |
|---|---|---|
| Betroffene Dateien (total) | 11 Py + 4 HTML | `grep -rn "SickWeek\|sick_week" app/ tests/ -l` |
| LOC betroffener Py-Dateien | 1783 LOC | `wc -l` |
| Tests in betroffenen Suites | 55 Tests | `grep -c "def test_"` (10+17+26+2) |
| Aktuell scheiternde Tests | 2 (test_von_bis_*) | `pytest --tb=no -q` |
| Passing Tests | 59/61 | Baseline vor Umbau |

---

## Files to Modify

| File | Change |
|---|---|
| **NEW** `app/models/sick_period.py` | Neues SickPeriod-Model |
| `app/models/sick_week.py` | **DELETE** nach Migration |
| `app/__init__.py` | Import: SickWeek → SickPeriod (L87) |
| **NEW** `migrations/versions/XXXX_replace_sick_weeks_with_sick_periods.py` | Tabelle erstellen, Daten migrieren, alte Tabelle droppen |
| `app/services/penalty.py` | `_sick_days_in_week()` Overlap-Funktion statt SickWeek-Lookup |
| `app/services/weekly_summary.py` | Pre-Fetch auf SickPeriod umstellen |
| `app/routes/challenges.py` | Legacy sick-Route (Redirect), Cascade-Delete (L426) |
| `app/routes/admin.py` | Cascade-Delete (L193) |
| `app/routes/challenge_activities.py` | `sick_period_submit`, `delete_sick_period`, `my_week`; `_sick_days_per_week` entfernen |
| `app/templates/activities/log.html` | `max`-Attribute entfernen, Form-Action auf `/sick-period` |
| `app/templates/activities/my_week.html` | Von SickWeek-Feldern auf SickPeriod-Felder umstellen |
| `app/templates/challenges/detail.html` | Legacy-Button anpassen (Redirect-Hinweis oder entfernen) |
| `tests/test_penalty.py` | SickWeek-Fixtures → SickPeriod |
| `tests/test_challenge.py` | ~7 sick-Tests adaptieren + ~3 neue Tests |
| `tests/test_activities_log.py` | Delete-Tests auf `delete_sick_period` |
| `tests/test_challenge_delete.py` | Cascade auf SickPeriod |

---

## Implementation Detail

### Neues Model `app/models/sick_period.py`

```python
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.extensions import db

class SickPeriod(db.Model):
    __tablename__ = "sick_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
```

Kein UniqueConstraint – Overlap-Prüfung in der Route.

### Migration (SQLite render_as_batch)

Schritte:
1. `op.create_table("sick_periods", ...)` – alle Felder wie oben
2. Data-Migration: `INSERT INTO sick_periods SELECT id, user_id, challenge_id, week_start AS start_date, (week_start + sick_days - 1 Tage) AS end_date, created_at FROM sick_weeks`
3. `op.drop_table("sick_weeks")`

Downgrade: Tabellen invertiert (sick_periods → sick_weeks mit `sick_days = (end_date - start_date).days + 1`, geclampt auf 7).

**ACHTUNG:** `render_as_batch=True` muss in `env.py` aktiv sein (ist bereits seit Commit 21c5cfd).

### `app/services/penalty.py` – Neue Overlap-Funktion

```python
from app.models.sick_period import SickPeriod

def _sick_days_in_week(user_id: int, challenge_id: int, week_start: date) -> int:
    week_end = week_start + timedelta(days=6)
    periods = db.session.scalars(
        db.select(SickPeriod).where(
            SickPeriod.user_id == user_id,
            SickPeriod.challenge_id == challenge_id,
            SickPeriod.start_date <= week_end,
            SickPeriod.end_date >= week_start,
        )
    ).all()
    total = 0
    for p in periods:
        eff_start = max(p.start_date, week_start)
        eff_end = min(p.end_date, week_end)
        total += (eff_end - eff_start).days + 1
    return min(total, 7)
```

In `calculate_weekly_penalty`: bisherigen `SickWeek`-Lookup ersetzen durch:
```python
sick_days = _sick_days_in_week(user_id, challenge_id, week_start)
if sick_days > 0:
    deductions = sick_days // 2
    effective_goal = max(0, weekly_goal - deductions)
    ...
```

### `app/services/weekly_summary.py` – Pre-Fetch Umbau

```python
from collections import defaultdict
from app.models.sick_period import SickPeriod

# Bulk-fetch aller SickPeriods für Challenge
all_sick_periods = db.session.scalars(
    db.select(SickPeriod).where(SickPeriod.challenge_id == challenge.id)
).all()
# Gruppiert nach user_id
sick_by_user: dict[int, list[SickPeriod]] = defaultdict(list)
for sp in all_sick_periods:
    sick_by_user[sp.user_id].append(sp)

# Helper (lokal):
def _sick_days_from_periods(periods, week_start):
    week_end = week_start + timedelta(days=6)
    total = 0
    for p in periods:
        if p.start_date <= week_end and p.end_date >= week_start:
            eff_start = max(p.start_date, week_start)
            eff_end = min(p.end_date, week_end)
            total += (eff_end - eff_start).days + 1
    return min(total, 7)

# Pro Woche/Teilnehmer:
sick_days_val = _sick_days_from_periods(sick_by_user[user.id], week_start)
is_sick = sick_days_val > 0
```

`weeks_data[week_start]["sick_days"]` liefert weiterhin den Ganzzahl-Wert → Dashboard-Templates unverändert.

### `app/routes/challenge_activities.py` – Route-Umbau

**Entfernen:**
- `_sick_days_per_week()` (L222–230)
- komplette `sick_week_submit()` (L233–337)
- `delete_sick_week()` (L549–567)

**Neu anlegen:**

```python
@challenge_activities_bp.route("/sick-period", methods=["POST"])
@login_required
def sick_period_submit():
    participation = _active_participation()
    ...
    sick_from = date.fromisoformat(request.form["sick_from"])
    sick_to = date.fromisoformat(request.form["sick_to"])
    sick_period_id = request.form.get("sick_period_id", type=int)

    # Validierungen:
    # 1. start <= end
    # 2. Zeitraum liegt (zumindest teilweise) im Challenge-Zeitraum
    # 3. Kein Overlap mit anderen Perioden desselben Users/Challenge
    #    (bei Update: eigene Periode ausschließen)

    # Clampen auf Challenge-Grenzen:
    clamped_start = max(sick_from, challenge.start_date)
    clamped_end = min(sick_to, challenge.end_date)

    # Overlap-Check:
    overlap_query = db.select(SickPeriod).where(
        SickPeriod.user_id == current_user.id,
        SickPeriod.challenge_id == challenge.id,
        SickPeriod.start_date <= clamped_end,
        SickPeriod.end_date >= clamped_start,
    )
    if sick_period_id:
        overlap_query = overlap_query.where(SickPeriod.id != sick_period_id)
    if db.session.scalar(overlap_query):
        flash("Dieser Zeitraum überschneidet sich mit einer bestehenden Krankmeldung.")
        return redirect(...)

    if sick_period_id:
        period = db.session.get(SickPeriod, sick_period_id)
        # Owner-Check
        period.start_date = clamped_start
        period.end_date = clamped_end
    else:
        db.session.add(SickPeriod(user_id=..., challenge_id=...,
                                   start_date=clamped_start, end_date=clamped_end))
    db.session.commit()
```

```python
@challenge_activities_bp.route("/sick-period/<int:sick_period_id>/delete", methods=["POST"])
@login_required
def delete_sick_period(sick_period_id: int):
    period = db.session.get(SickPeriod, sick_period_id)
    if period is None or (period.user_id != current_user.id and not current_user.is_admin):
        abort(403)
    db.session.delete(period)
    db.session.commit()
    ...
```

**`my_week`-View:** SickWeek-Lookup ersetzen durch SickPeriod-Overlap mit aktueller Woche:
```python
sick_period = db.session.execute(
    db.select(SickPeriod).where(
        SickPeriod.user_id == current_user.id,
        SickPeriod.challenge_id == participation.challenge_id,
        SickPeriod.start_date <= week_end,
        SickPeriod.end_date >= monday,
    )
).scalar_one_or_none()
```
Template-Variable heißt weiterhin `sick_week` → `sick_period` (Template wird in Issue 7 angepasst).

### `app/routes/challenges.py`

Legacy `sick`-Route (L361–403): Inhalt ersetzen durch Redirect auf `challenge_activities.log_form`:
```python
@challenges_bp.route("/<string:public_id>/sick", methods=["POST"])
@login_required
def sick(public_id):
    return redirect(url_for("challenge_activities.log_form"))
```

Cascade-Delete (L426): `SickWeek.query` → `SickPeriod.query`

### `app/routes/admin.py`

L193: `SickWeek.query.filter_by(user_id=user.id).delete()` → `SickPeriod.query.filter_by(user_id=user.id).delete()`

### Templates

**`log.html`** (L84–90): `max="{{ today }}"` auf beiden Date-Inputs entfernen; Form-Action auf `/sick-period`.

**`my_week.html`** (L35–101):
- `sick_week.sick_days` → `sick_days_val` (lokal berechnet im Template via Macro oder aus Route übergeben)
- Statt 1–7-Dropdown: Von/Bis-Datumsfelder (pre-filled mit `sick_period.start_date` / `sick_period.end_date`)
- Hidden field `sick_period_id` wenn Bearbeitung
- Delete-Button: `delete_sick_period` URL
- Offset-Restriction `offset <= 0` entfernen (auch zukünftige Wochen zeigen Krankmeldungen)

**`detail.html`** (L78–81): Legacy-Button Text aktualisieren → "Krankmeldung eintragen" + Redirect-Hinweis (oder ganz entfernen und durch Link ersetzen).

---

## Issues

### Wave 1

#### I-01: SickPeriod-Model + Migration
- **Typ:** task | **Priorität:** 1 | **Größe:** M
- **Risiko:** `irreversible / external / requires-human`
- **Was:** Neues `app/models/sick_period.py` anlegen (Felder: id, user_id FK, challenge_id FK, start_date Date NOT NULL, end_date Date NOT NULL, created_at). Alembic-Migration: create sick_periods, Datenmigration aus sick_weeks (end_date = week_start + timedelta(days=sick_days-1)), drop sick_weeks. `app/__init__.py` L87 import anpassen.
- **Acceptance:**
  - `flask db upgrade` läuft fehlerfrei durch
  - `sick_periods`-Tabelle existiert in DB
  - `sick_weeks`-Tabelle ist gelöscht
  - Bestehende Daten sind migriert (start_date = alte week_start, end_date = week_start + sick_days - 1)
  - `flask db downgrade` funktioniert (smoke-test)
- **Verification:** `FLASK_APP=run.py flask db upgrade && sqlite3 instance/app.db ".tables"` (kein sick_weeks, sick_periods vorhanden)

---

### Wave 2 (parallel nach I-01)

#### I-02: penalty.py – Overlap-Berechnung
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:** `SickWeek`-Import entfernen. Neue interne Funktion `_sick_days_in_week(user_id, challenge_id, week_start) -> int` (SQL-Overlap-Query, Python-Summierung, min 7). `calculate_weekly_penalty` nutzt diese Funktion statt SickWeek-Lookup.
- **Acceptance:**
  - Keine `SickWeek`-Referenzen mehr in penalty.py
  - Penalty für 3 Krankentage in einer 7-Tage-Woche = 1 Abzug (3 // 2 = 1)
  - Penalty für 0 Krankentage = unverändert
  - Krankmeldung die nur teilweise in eine Woche fällt: nur Überschneidung zählt

#### I-03: weekly_summary.py – Pre-Fetch auf SickPeriod
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:** `SickWeek`-Import und `sick_index`-Dict (L61–67) ersetzen durch SickPeriod-Bulk-Fetch + `defaultdict(list)` gruppiert nach user_id. Lokale Hilfsfunktion `_sick_days_from_periods(periods, week_start) -> int`. `sick_days_val` und `is_sick` weiterhin korrekt befüllen. Dashboard-Templates verwenden `wd.is_sick` und `wd.sick_days` – Signatur muss erhalten bleiben.
- **Acceptance:**
  - `wd.is_sick` ist True genau dann, wenn ein SickPeriod die jeweilige Woche schneidet
  - `wd.sick_days` enthält Anzahl Krankentage in der Woche (0–7)
  - Keine N+1-Queries (ein Bulk-Fetch für alle Perioden der Challenge)

---

### Wave 3 (parallel nach I-02 + I-03)

#### I-04: challenges.py + admin.py – Legacy-Route + Cascade-Deletes
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / system / autonomous-ok`
- **Was:**
  - `challenges.py:sick()` (L361–403): Body durch Redirect auf `challenge_activities.log_form` ersetzen (URL-Backward-Compat)
  - `challenges.py:delete_challenge()` (L426): `SickWeek.query` → `SickPeriod.query`
  - `admin.py:L193`: `SickWeek.query.filter_by(user_id=user.id).delete()` → `SickPeriod.query.filter_by(user_id=user.id).delete()`
  - Imports in beiden Dateien anpassen
- **Acceptance:**
  - POST auf `/<public_id>/sick` redirectet auf log_form (302)
  - Challenge löschen via Admin löscht auch zugehörige SickPeriods
  - User löschen via Admin löscht auch SickPeriods des Users

#### I-05: challenge_activities.py – Neue Sick-Routen
- **Typ:** task | **Priorität:** 1 | **Größe:** M
- **Risiko:** `reversible / system / autonomous-ok`
- **Was:**
  - `_sick_days_per_week()` entfernen
  - `sick_week_submit()` entfernen
  - `delete_sick_week()` entfernen
  - Neu: `sick_period_submit()` POST `/sick-period` – Von/Bis aus Form, optional `sick_period_id` für Update, Clamping auf Challenge-Grenzen, Overlap-Prüfung, Create/Update SickPeriod
  - Neu: `delete_sick_period(sick_period_id)` POST `/sick-period/<id>/delete` – Owner-oder-Admin-Check
  - `my_week()`: SickWeek-Lookup (L200–204) auf SickPeriod-Overlap umstellen; Template-Variable umbenennen: `sick_week` → `sick_period`
- **Acceptance:**
  - POST `/sick-period` mit gültigem Von/Bis erzeugt SickPeriod-Eintrag
  - POST mit `sick_period_id` updated bestehenden Eintrag
  - Zukunftsdaten werden akzeptiert (kein `sick_to > today`-Fehler)
  - Überlappender Zeitraum → Flash-Fehler, kein neuer Eintrag
  - DELETE via `/sick-period/<id>/delete` löscht Eintrag (Owner oder Admin)
  - Andere User können fremde Einträge nicht löschen (403)

---

### Wave 4 (parallel nach I-05)

#### I-06: log.html + detail.html – Zukunft erlauben
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:**
  - `log.html:L84–90`: `max="{{ today }}"` von beiden Date-Inputs entfernen; Form-Action-URL auf `url_for('challenge_activities.sick_period_submit')` → `/sick-period`
  - `detail.html:L78–81`: Button-Text oder Verlinkung aktualisieren (statt direktem POST jetzt Link zur log_form mit Tab "Krankmeldung")
- **Acceptance:**
  - Date-Picker in log.html erlaubt Zukunftsdaten
  - Form postet an `/sick-period`
  - Kein JS/Validierungsfehler bei Zukunftsdatum

#### I-07: my_week.html – SickPeriod-Anzeige
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:**
  - Template-Variable heißt jetzt `sick_period` (statt `sick_week`)
  - Effektives Ziel: `sick_days_val` aus Route übergeben (int, 0–7); `eff_goal = weekly_goal - sick_days_val // 2`
  - Statt 1–7 Dropdown: Von/Bis-Datumseingabe, pre-filled mit `sick_period.start_date` / `.end_date`
  - Hidden field `sick_period_id={{ sick_period.id }}` für Update
  - Form-Action auf `/sick-period`
  - Delete-Button: `url_for('challenge_activities.delete_sick_period', sick_period_id=sick_period.id)`
  - Offset-Bedingung `offset <= 0` am Krankmeldungs-Card entfernen (Zukunftswochen können auch Krankmeldungen haben)
  - Route `my_week()` muss `sick_days_val` (int) ans Template übergeben
- **Acceptance:**
  - Woche mit aktiver Krankmeldung zeigt Von/Bis der Periode (pre-filled)
  - Formular kann Periode durch Ändern des End-Datums kürzen
  - Delete-Button löscht Periode
  - Zukunftswochen zeigen Krankmeldungs-Card wenn Periode reinreicht

---

### Wave 5 (parallel nach I-04 + I-05 + I-06 + I-07)

#### I-08: Tests – test_penalty.py
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:** Alle `SickWeek(...)`-Fixtures auf `SickPeriod(start_date=..., end_date=...)` umstellen. `sick_days`-Parametrierung: in `test_sick_days_deduction_table` wird `sick_days` als Integer zum Berechnen von start/end_date verwendet (z.B. sick_days=3 → start_date=monday, end_date=monday+2).
- **Named Tests (adaptiert):**
  - `test_sick_week_no_penalty` → `test_sick_period_no_penalty`: SickPeriod mit end_date = week_end
  - `test_sick_days_deduction_table` (parametriert): SickPeriod mit Länge = sick_days
  - `test_partial_sick_week_goal_met` → `test_partial_sick_period_goal_met`
- **Neue Tests:**
  - `test_sick_period_spanning_two_weeks`: Periode über Wochengrenze → korrekte Overlap-Berechnung pro Woche
  - `test_sick_period_future_no_penalty`: Zukünftige Periode hat keine Auswirkung auf aktuelle Strafe
- **Acceptance:** `pytest tests/test_penalty.py -v` → alle Tests grün

#### I-09: Tests – test_challenge.py
- **Typ:** task | **Priorität:** 1 | **Größe:** M
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:** ~7 bestehende sick-Tests adaptieren (neue Route-URL `/sick-period`, SickPeriod-Felder, kein Splitting in mehrere Zeilen mehr). Die zwei bereits failing Tests (von_bis_*) werden hier gefixt.
- **Named Tests (adaptiert):**
  - `test_sick_week_creation` → `test_sick_period_creation`: POST `/sick-period`, prüft 1 SickPeriod-Eintrag
  - `test_duplicate_sick_week_rejected` → `test_overlapping_sick_period_rejected`: gleicher Zeitraum ergibt Flash-Fehler, kein zweiter Eintrag
  - `test_sick_week_submit_partial` → `test_sick_period_submit_partial`: Von/Bis innerhalb einer Woche → 1 SickPeriod (kein Split)
  - `test_sick_week_submit_update` → `test_sick_period_update`: Update via `sick_period_id` ändert end_date
  - `test_sick_week_submit_future_rejected` → `test_sick_period_future_allowed`: Zukunftsdaten werden jetzt akzeptiert
  - `test_sick_week_submit_von_bis_single_week` → `test_sick_period_von_bis_single_week`: 1 Eintrag, korrekte Daten
  - `test_sick_week_submit_von_bis_two_weeks` → `test_sick_period_von_bis_two_weeks`: KEIN Split – 1 SickPeriod über Wochengrenze
- **Neue Tests:**
  - `test_sick_period_clamped_to_challenge_bounds`: Eingabe außerhalb Challenge-Zeitraum wird geclampt
  - `test_sick_period_delete_own`
- **Acceptance:** `pytest tests/test_challenge.py -v -k "sick"` → alle Tests grün (inkl. der 2 bisher failing)

#### I-10: Tests – test_activities_log.py + test_challenge_delete.py
- **Typ:** task | **Priorität:** 1 | **Größe:** S
- **Risiko:** `reversible / local / autonomous-ok`
- **Was:**
  - `test_activities_log.py`: Delete-Tests auf neue URL `/sick-period/<id>/delete` + `SickPeriod`-Fixture
  - `test_challenge_delete.py`: Cascade-Prüfung auf SickPeriod statt SickWeek
- **Named Tests (adaptiert):**
  - `test_delete_sick_week_own` → `test_delete_sick_period_own`
  - `test_delete_sick_week_other_user_rejected` → `test_delete_sick_period_other_user_rejected`
  - `test_admin_deletes_sick_week_of_other_user` → `test_admin_deletes_sick_period_of_other_user`
  - `test_admin_deletes_challenge_cascade` (L60–89): prüft `SickPeriod` statt `SickWeek`
- **Acceptance:** `pytest tests/test_activities_log.py tests/test_challenge_delete.py -v` → alle Tests grün

---

## Wave-Struktur

```
Wave 1:  [I-01: Model + Migration]
           ↓
Wave 2:  [I-02: penalty.py] [I-03: weekly_summary.py]   (parallel)
           ↓
Wave 3:  [I-04: challenges+admin] [I-05: challenge_activities]  (parallel)
           ↓
Wave 4:  [I-06: log.html+detail.html] [I-07: my_week.html]   (parallel)
           ↓
Wave 5:  [I-08: test_penalty] [I-09: test_challenge] [I-10: test_activities+delete]  (parallel)
```

**Kritischer Pfad:** I-01 → I-02/I-03 → I-05 → I-07 → I-09

---

## Boundaries

**Always:**
- `render_as_batch=True` bei jeder SQLite-Migration
- `end_date` ist immer NOT NULL (Käpt'n: User gibt immer Von/Bis an)
- Keine überlappenden Perioden pro (user_id, challenge_id): Route-Validierung pflicht
- `SickPeriod.end_date` wird auf `challenge.end_date` geclampt, `start_date` auf `challenge.start_date`
- Legacy-URL `POST /<public_id>/sick` bleibt erhalten (Redirect) – kein 404
- `wd.is_sick` und `wd.sick_days` im Dashboard-Output müssen erhalten bleiben (Dashboard-Templates nicht anfassen)
- Kein `sick_to > today`-Check mehr – Zukunftsdaten erlaubt
- `SECRET_KEY` aus `.env` laden (`set -a && source .env && set +a`) für Tests und flask-Befehle

**Never:**
- `sick_week.py` in neuem Code importieren (nach Migration gelöscht)
- `sick_days`-Integer-Feld neu anlegen (war wochenbasiert; in SickPeriod nicht vorhanden)
- DB-Migrations ohne Backup-Hinweis an Käpt'n bei `irreversible / external`

**Ask First:** –

---

## Rollback-Strategie

- **Git-Checkpoint:** vor Wave 1 `git stash` oder Feature-Branch
- **Wave 1 (Migration):** `flask db downgrade -1` stellt `sick_weeks` wieder her; Datenmigration ist verlustlos reversibel
- **Wave 2–5:** rein reversible Code-Änderungen; `git revert` oder `git checkout -- <file>`
- **Prod-Deployment:** nach `git push` auf stonbgsport01: `git pull && docker compose pull && docker compose up -d`

---

## Invalidierungsrisiken

| Annahme | Risiko | Betroffene Issues |
|---|---|---|
| `render_as_batch=True` in env.py aktiv | Niedrig – Commit 21c5cfd bestätigt | I-01 |
| Dashboard-Templates nutzen nur `wd.is_sick` und `wd.sick_days` | Niedrig – verifiziert per grep | I-03 |
| Keine weiteren SickWeek-Importe außerhalb der 11 bekannten Dateien | Niedrig – `grep -rn SickWeek app/` vollständig | I-01 |
| `challenges.sick`-URL wird nicht von Tests direkt geprüft (nur als Redirect) | Mittel – Test I-09 muss ggf. angepasst werden | I-04, I-09 |
