# Plan: Vollständige Lösch-Funktionalität

**Date:** 2026-04-30
**Status:** Approved
**Research:** `.schrammns_workflow/research/2026-04-30-loeschfunktionalitaet-aktivitaeten-krankmeldungen-challenges.md`

## Goal

Benutzer können eigene Aktivitäten und Krankmeldungen löschen. Admins können das bei allen Nutzern. Admins können Challenges und Bonus-Challenges löschen. Bestehender Filesystem-Leak in `delete_user()` wird behoben.

## Baseline Metrics

| Metric | Value | Command |
|--------|-------|---------|
| Test-Dateien | 14 | `find tests/ -name "*.py" \| wc -l` |
| Gesamt-Tests | 135 | `grep -r "def test_" tests/ \| wc -l` |
| Dateien zu ändern | 8 | (siehe unten) |
| Git-Status | sauber | `git status` |

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/admin.py` | Activity-Bulk-Delete → Iteration mit `delete_media_files()` (Zeile 188) |
| `app/routes/challenge_activities.py` | SickWeek-Delete-Route (User + Admin) + Activity-Delete Admin-Override |
| `app/routes/bonus.py` | BonusChallenge-Delete-Route (Admin) |
| `app/routes/challenges.py` | Challenge-Delete-Route (Admin) mit vollständiger Cascade |
| `app/templates/activities/my_week.html` | SickWeek-Lösch-Button |
| `app/templates/activities/user_activities.html` | Admin-Delete-Buttons für Aktivitäten + Krankmeldungen |
| `app/templates/bonus/index.html` | Admin-Lösch-Button pro BonusChallenge |
| `app/templates/challenges/detail.html` | Admin-Lösch-Button für gesamte Challenge |
| `tests/test_activities_log.py` | Tests für SickWeek-Delete + Activity Admin-Override |
| `tests/test_bonus.py` | **NEW** – Tests für BonusChallenge-Delete |
| `tests/test_challenges.py` oder `test_challenge_delete.py` | **NEW** – Tests für Challenge-Delete Cascade |
| `tests/test_admin_user_detail.py` | Erweiterung: FS-Leak-Fix verifizieren |
| `CHANGELOG.md` | Neue Einträge für Version 0.8.0 |
| `app/version.py` | 0.7.x → 0.8.0 (minor bump, neue Features) |

## Implementation Detail

### I-01: Bugfix – Filesystem-Leak in delete_user()

**Datei:** `app/routes/admin.py:188`

**Problem:** Bulk-Delete via `Activity.query.filter_by(user_id=user.id).delete()` löst ORM-Cascades nicht aus → ActivityMedia-Dateien bleiben auf dem Filesystem.

**Fix:**
```python
# VORHER (Zeile 188):
Activity.query.filter_by(user_id=user.id).delete()

# NACHHER:
for _act in Activity.query.filter_by(user_id=user.id).all():
    delete_media_files(_act.media)
    if _act.screenshot_path:
        delete_upload(_act.screenshot_path)
    db.session.delete(_act)
```

Import sicherstellen: `from app.utils.uploads import delete_media_files, delete_upload` – beide sind bereits in `challenge_activities.py` importiert, in `admin.py` noch nicht. Prüfen und ggf. ergänzen.

### I-02: SickWeek-Delete (User + Admin-Override) + Activity Admin-Override

**Datei:** `app/routes/challenge_activities.py`

#### a) SickWeek-Delete-Route (neu, am Dateiende)

```python
@challenge_activities_bp.route("/sick-week/<int:sick_week_id>/delete", methods=["POST"])
@login_required
def delete_sick_week(sick_week_id: int):
    sick_week = db.session.get(SickWeek, sick_week_id)
    if sick_week is None or (
        sick_week.user_id != current_user.id and not current_user.is_admin
    ):
        flash("Krankmeldung nicht gefunden.", "warning")
        return redirect(url_for("challenge_activities.my_week"))
    db.session.delete(sick_week)
    db.session.commit()
    flash("Krankmeldung wurde gelöscht.", "success")
    # Admin-Redirect: zurück zur User-Aktivitätenseite
    if current_user.is_admin and sick_week.user_id != current_user.id:
        return redirect(url_for("challenge_activities.user_activities",
                                user_id=sick_week.user_id,
                                challenge_id=sick_week.challenge_id))
    return redirect(url_for("challenge_activities.my_week"))
```

Import: `SickWeek` ist wahrscheinlich noch nicht importiert – ergänzen: `from app.models.sick_week import SickWeek`

#### b) Activity-Delete Admin-Override (bestehende Route, Zeile 524-527)

Guard erweitern von:
```python
if activity is None or activity.user_id != current_user.id:
```
zu:
```python
if activity is None or (
    activity.user_id != current_user.id and not current_user.is_admin
):
```

#### c) Templates

**`my_week.html`:** Nach dem bestehenden `{% if activity.source == "manual" %}` Delete-Button (Zeile 154) Krankmeldungs-Abschnitt suchen und dort Lösch-Button ergänzen. SickWeek-Einträge werden in `my_week.html` angezeigt (aktuell ohne Löschbutton) – jeweils ein:
```html
<form method="post"
      action="{{ url_for('challenge_activities.delete_sick_week', sick_week_id=sw.id) }}"
      data-confirm="Krankmeldung für diese Woche wirklich löschen?"
      class="d-inline">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-outline-danger btn-sm">Krankmeldung löschen</button>
</form>
```

**`user_activities.html`:** Admin-only Aktivitäten-Delete-Button und Krankmeldungs-Delete-Button ergänzen. Für jede Activity:
```html
{% if current_user.is_admin %}
<form method="post"
      action="{{ url_for('challenge_activities.delete_activity', activity_id=activity.id) }}"
      data-confirm="Aktivität von {{ target_user.display_name }} wirklich löschen?"
      class="d-inline">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-outline-danger btn-sm">Löschen</button>
</form>
{% endif %}
```

Für Krankmeldungen (falls in `user_activities.html` angezeigt – prüfen ob separate Route nötig oder Sick-Weeks in dieser Template-Variable enthalten sind):
```html
{% if current_user.is_admin %}
<form method="post"
      action="{{ url_for('challenge_activities.delete_sick_week', sick_week_id=sw.id) }}"
      ...>...</form>
{% endif %}
```

### I-03: BonusChallenge-Delete (Admin)

**Datei:** `app/routes/bonus.py`

Neue Route nach `create_post()`:
```python
@bonus_bp.route("/<int:bonus_id>/delete", methods=["POST"])
@admin_required
def delete_bonus_challenge(bonus_id: int):
    bonus = db.session.get(BonusChallenge, bonus_id)
    if bonus is None:
        abort(404)
    # Cascade: Entries zuerst
    BonusChallengeEntry.query.filter_by(bonus_challenge_id=bonus.id).delete()
    db.session.delete(bonus)
    db.session.commit()
    flash("Bonus-Challenge wurde gelöscht.", "success")
    return redirect(url_for("bonus.index"))
```

**Template `bonus/index.html`:** Admin-only Lösch-Button pro BonusChallenge-Card:
```html
{% if current_user.is_admin %}
<form method="post"
      action="{{ url_for('bonus.delete_bonus_challenge', bonus_id=bc.id) }}"
      data-confirm="Bonus-Challenge '{{ bc.description[:30] }}' wirklich löschen? Alle Einträge werden entfernt."
      class="d-inline">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-outline-danger btn-sm">Löschen</button>
</form>
{% endif %}
```

### I-04: Challenge-Delete (Admin)

**Datei:** `app/routes/challenges.py`

Neue Route (nach `sick()`):
```python
@challenges_bp.route("/<string:public_id>/delete", methods=["POST"])
@admin_required
def delete_challenge(public_id: str):
    challenge = _get_challenge_by_public_id(public_id)
    
    # Cascade-Reihenfolge (FK-Abhängigkeiten, KEINE DB-Cascades konfiguriert):
    # 1. BonusChallengeEntry (via BonusChallenge)
    bonus_ids = [bc.id for bc in BonusChallenge.query.filter_by(challenge_id=challenge.id).all()]
    if bonus_ids:
        BonusChallengeEntry.query.filter(
            BonusChallengeEntry.bonus_challenge_id.in_(bonus_ids)
        ).delete(synchronize_session="fetch")
    # 2. BonusChallenge
    BonusChallenge.query.filter_by(challenge_id=challenge.id).delete()
    # 3. PenaltyOverride
    PenaltyOverride.query.filter_by(challenge_id=challenge.id).delete()
    # 4. SickWeek
    SickWeek.query.filter_by(challenge_id=challenge.id).delete()
    # 5. Activity + Dateisystem-Cleanup (ORM-Iteration wegen ActivityMedia-Files!)
    for _act in Activity.query.filter_by(challenge_id=challenge.id).all():
        delete_media_files(_act.media)
        if _act.screenshot_path:
            delete_upload(_act.screenshot_path)
        db.session.delete(_act)
    # 6. ChallengeParticipation
    ChallengeParticipation.query.filter_by(challenge_id=challenge.id).delete()
    # 7. Challenge selbst
    db.session.delete(challenge)
    db.session.commit()
    flash(f"Challenge '{challenge.name}' wurde gelöscht.", "success")
    return redirect(url_for("challenges.index"))
```

Imports in `challenges.py` ergänzen:
- `from app.models.bonus import BonusChallenge, BonusChallengeEntry`
- `from app.models.penalty import PenaltyOverride`
- `from app.models.sick_week import SickWeek`
- `from app.models.activity import Activity`
- `from app.utils.uploads import delete_media_files, delete_upload`

**Template `challenges/detail.html`:** Admin-only Lösch-Button (am Ende der Seite, nach Participations-Tabelle):
```html
{% if current_user.is_admin %}
<div class="mt-4">
  <form method="post"
        action="{{ url_for('challenges.delete_challenge', public_id=challenge.public_id) }}"
        data-confirm="Challenge '{{ challenge.name }}' wirklich löschen? Alle Aktivitäten, Krankmeldungen, Bonus-Challenges und Teilnahmen werden entfernt. Diese Aktion kann nicht rückgängig gemacht werden."
        class="d-inline">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit" class="btn btn-danger">Challenge löschen</button>
  </form>
</div>
{% endif %}
```

### I-05: Tests

**Neue Test-Funktionen in `tests/test_activities_log.py`:**
- `test_delete_sick_week_own`: User löscht eigene Krankmeldung → 302, SickWeek gone
- `test_delete_sick_week_other_user_rejected`: User B versucht User A's Krankmeldung zu löschen → 302, SickWeek still exists
- `test_admin_deletes_sick_week_of_other_user`: Admin löscht fremde Krankmeldung → 302, SickWeek gone
- `test_admin_deletes_others_activity`: Admin löscht fremde Aktivität → 302, Activity gone
- `test_user_cannot_delete_others_activity_still_blocked`: normaler User kann fremde Activity nicht löschen (bestehender Test deckt das bereits ab – nur verifizieren dass Admin-Override ihn nicht bricht)

**Neue Datei `tests/test_bonus_delete.py`:**
- `test_admin_deletes_bonus_challenge`: Admin löscht BonusChallenge → 302, BonusChallenge gone, BonusChallengeEntry gone
- `test_user_cannot_delete_bonus_challenge`: normaler User → 403 oder Redirect
- `test_delete_bonus_challenge_404_on_missing`: ungültige ID → 404

**Neue Datei `tests/test_challenge_delete.py`:**
- `test_admin_deletes_challenge_cascade`: Admin löscht Challenge → 302, Challenge + ChallengeParticipation + Activity + SickWeek + BonusChallenge + BonusChallengeEntry alle gone
- `test_user_cannot_delete_challenge`: normaler User → 403
- `test_challenge_delete_cleans_up_media_files`: Activity mit ActivityMedia → nach Delete kein Eintrag mehr in DB (Datei-Cleanup via Mock oder tmp-Verzeichnis)

### I-06: CHANGELOG + version.py

**`app/version.py`:** `0.7.x` → `0.8.0` (minor: neue Lösch-Features)

**`CHANGELOG.md`:** Unter `[Unreleased]` bzw. neue `[0.8.0]` Sektion:
```markdown
## [0.8.0] - 2026-04-30
### Added
- Benutzer können eigene Krankmeldungen löschen (mit Bestätigungs-Dialog)
- Admin kann Krankmeldungen aller Nutzer löschen
- Admin kann Aktivitäten aller Nutzer löschen
- Admin kann Bonus-Challenges inkl. aller Einträge löschen
- Admin kann Challenges inkl. aller Aktivitäten, Krankmeldungen und Bonus-Challenges löschen
### Fixed
- Filesystem-Leak beim Löschen eines Nutzers (ActivityMedia-Dateien blieben auf dem Server)
```

## Waves

### Wave 1 (parallel)

| Issue | Dateien | Abhängigkeiten |
|-------|---------|----------------|
| I-01 FS-Leak Fix | admin.py | keine |
| I-02 SickWeek + Activity Admin | challenge_activities.py, my_week.html, user_activities.html | keine |
| I-03 BonusChallenge-Delete | bonus.py, bonus/index.html | keine |
| I-04 Challenge-Delete | challenges.py, challenges/detail.html | keine |

Alle vier berühren unterschiedliche Dateien → vollständig parallelisierbar.

### Wave 2

| Issue | Dateien | Abhängigkeiten |
|-------|---------|----------------|
| I-05 Tests | test_activities_log.py, test_bonus_delete.py, test_challenge_delete.py, test_admin_user_detail.py | I-01, I-02, I-03, I-04 |

### Wave 3

| Issue | Dateien | Abhängigkeiten |
|-------|---------|----------------|
| I-06 CHANGELOG + version | CHANGELOG.md, app/version.py | I-05 |

## Boundaries

**Always:**
- Admin-Override Guards: `activity.user_id != current_user.id and not current_user.is_admin` – nie nur `current_user.is_admin` alleine
- Dateisystem-Cleanup vor DB-Delete (nie umgekehrt)
- ORM-Iteration statt Bulk-Delete wenn Dateien involviert sind (kein `Activity.query.filter_by(...).delete()`)
- `data-confirm` bei allen Lösch-Buttons
- CSRF-Token in allen Lösch-Formularen
- Flash-Message nach jedem Delete (success/warning)
- Cascade-Reihenfolge bei Challenge-Delete: BonusChallengeEntry → BonusChallenge → PenaltyOverride → SickWeek → Activity → ChallengeParticipation → Challenge

**Never:**
- Bulk-`.delete()` wenn ORM-Cascades oder Dateisystem-Cleanup nötig
- Lösch-Routen mit GET-Methode
- Challenge-Delete ohne Admin-Guard

**Ask First:** (alle Entscheidungen durch Kapitän getroffen)
- SickWeek-Delete durch User: ✅ Ja, ohne Guard (Kapitän: kein Betrugs-Risiko durch offene Wochenzählung)
- Challenge-Delete ohne Participation-Guard: ✅ Ja (Kapitän: Admin trägt Verantwortung)

## Design Decisions

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| SickWeek User-Delete Guard | Owner-Check only | Zeitraum-Check (Woche nicht in Zukunft) | Kapitän: Delete öffnet Wochenzählung neu, kein Betrug möglich |
| Challenge-Delete Guard | Immer erlaubt (Admin) | Guard wenn aktive Participations | Kapitän: Admin trägt Verantwortung |
| SickWeek Admin-Route | Admin-Override in User-Route | Separate Admin-Route in admin.py | Einheitliche Route, guard-Logik zentralisiert |
| Activity Bulk-Delete Fix | ORM-Iteration + delete_media_files() | synchronize_session="fetch" + manueller FS-Cleanup | Klarer, wartbarer Code |

## Rollback

```bash
git stash      # Lokale Änderungen sichern
git checkout . # Einzelne Dateien zurücksetzen
```

Per-Issue: Jeder Commit ist atomar – einfaches `git revert <sha>`.

## Verification

```bash
# Alle Tests laufen durch
.venv/bin/pytest -v

# Spezifisch neue Tests
.venv/bin/pytest tests/test_activities_log.py -v -k "sick_week or admin_delete"
.venv/bin/pytest tests/test_bonus_delete.py -v
.venv/bin/pytest tests/test_challenge_delete.py -v

# Ziel: ≥ 150 Tests (135 + ~15 neue)
```

## Invalidation Risks

| Assumption | Risk | Affected |
|------------|------|---------|
| SickWeek ist in my_week.html überhaupt sichtbar | Falls nicht → Template muss Anzeige + Lösch-Button gleichzeitig ergänzen | I-02 |
| `user_activities.html` zeigt Sick-Weeks an | Falls nicht → separates Admin-View oder Route nötig | I-02 |
| `delete_media_files()` ist in admin.py importierbar | Falls nicht importiert → ImportError | I-01 |
| BonusChallengeEntry.bonus_challenge_id ist FK ohne CASCADE | Verifiziert aus Research | I-03, I-04 |
