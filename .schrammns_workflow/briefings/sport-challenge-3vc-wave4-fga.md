# Briefing: I-08 – Tests – test_penalty.py auf SickPeriod

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-fga

## Context

`penalty.py` nutzt jetzt SickPeriod-Overlap-Berechnung. Die Tests in test_penalty.py
verwenden noch `SickWeek`-Fixtures. Diese müssen auf `SickPeriod` umgestellt werden.

## File Ownership

**WRITE:** `tests/test_penalty.py`

## Was zu tun ist

**ZUERST:** Lese `tests/test_penalty.py` komplett und `tests/conftest.py`.

### Änderungen

1. **Import ersetzen:**
   - `from app.models.sick_week import SickWeek` → `from app.models.sick_period import SickPeriod`

2. **test_sick_week_no_penalty** (ca. L141) umbenennen und anpassen:
   - Neuer Name: `test_sick_period_no_penalty`
   - `SickWeek(week_start=week_start)` → `SickPeriod(start_date=week_start, end_date=week_start + timedelta(days=6))`
   - Testet: volle Woche krank → penalty = 0.0

3. **test_sick_days_deduction_table** (parametriert, ca. L247–279) anpassen:
   - Das `sick_days`-Parameterwert bleibt als Anzahl Tage
   - `SickWeek(week_start=week_start, sick_days=sick_days)` →
     `SickPeriod(start_date=week_start, end_date=week_start + timedelta(days=sick_days - 1))`
   - Logik: 1 Tag krank = Montag bis Montag, 3 Tage = Mo-Mi, 7 Tage = Mo-So

4. **test_partial_sick_week_goal_met** (ca. L282) umbenennen und anpassen:
   - Neuer Name: `test_partial_sick_period_goal_met`
   - `SickWeek(week_start=week_start, sick_days=2)` → `SickPeriod(start_date=week_start, end_date=week_start + timedelta(days=1))`

5. **Neue Tests hinzufügen:**

```python
def test_sick_period_spanning_two_weeks(db, app):
    """Period crossing week boundary only counts overlap days per week."""
    with app.app_context():
        challenge = _make_challenge(db)
        user, participation = _make_participant(db, challenge)
        week_start = challenge.start_date - timedelta(days=challenge.start_date.weekday())

        # Period: Friday of week1 to Tuesday of week2 (Fri-Mon-Tue = 2 days in week2)
        friday = week_start + timedelta(days=4)
        tuesday_next = week_start + timedelta(days=8)
        period = SickPeriod(
            user_id=user.id,
            challenge_id=challenge.id,
            start_date=friday,
            end_date=tuesday_next,
        )
        db.session.add(period)
        db.session.commit()

        # Week1: only Fri+Sat+Sun = 3 sick days → deduction = 1
        sick_in_week1 = _sick_days_in_week(user.id, challenge.id, week_start)
        assert sick_in_week1 == 3

        # Week2 (next Monday):
        next_monday = week_start + timedelta(weeks=1)
        sick_in_week2 = _sick_days_in_week(user.id, challenge.id, next_monday)
        assert sick_in_week2 == 2  # Mon+Tue


def test_sick_period_future_no_effect_on_penalty(db, app):
    """A future SickPeriod does not reduce penalty for past weeks."""
    with app.app_context():
        challenge = _make_challenge(db)
        user, participation = _make_participant(db, challenge)
        week_start = challenge.start_date - timedelta(days=challenge.start_date.weekday())

        # Future period (5 weeks from now)
        future_start = date.today() + timedelta(weeks=5)
        future_end = future_start + timedelta(days=6)
        period = SickPeriod(
            user_id=user.id,
            challenge_id=challenge.id,
            start_date=future_start,
            end_date=future_end,
        )
        db.session.add(period)
        db.session.commit()

        # Past week penalty should be unaffected
        penalty = calculate_weekly_penalty(
            user_id=user.id,
            challenge_id=challenge.id,
            week_start=week_start,
            weekly_goal=3,
            penalty_per_miss=5.0,
        )
        assert penalty == 15.0  # 3 missed * 5.0, no sick deduction
```

Füge `from app.services.penalty import _sick_days_in_week` zum Import hinzu (für den Spanning-Test).

### Verification

```bash
set -a && source .env && set +a
.venv/bin/pytest tests/test_penalty.py -v 2>&1 | tail -20
```

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: tests/test_penalty.py
SUMMARY: SickWeek-Fixtures auf SickPeriod(start_date, end_date) umgestellt. 3 Tests umbenannt+angepasst. 2 neue Tests: spanning_two_weeks, future_no_effect. Alle Tests grün.
RESULT_END
```
