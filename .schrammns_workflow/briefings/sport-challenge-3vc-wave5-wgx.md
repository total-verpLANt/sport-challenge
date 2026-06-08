# Briefing: I-09 – Tests – test_challenge.py auf SickPeriod

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-wgx

## Context

Die Routen, Templates und Services sind vollständig auf SickPeriod umgestellt.
`test_challenge.py` hat noch ~7 sick-bezogene Tests die auf die alte `/sick-week`-URL
und SickWeek-Logik zeigen. Diese müssen angepasst werden.
Zwei dieser Tests (`test_sick_week_submit_von_bis_single_week`, `test_sick_week_submit_von_bis_two_weeks`)
waren bereits **VOR dem Umbau** failing – sie werden hier gefixt.

## File Ownership

**WRITE:** `tests/test_challenge.py`

## Was zu tun ist

**ZUERST:** Lese `tests/test_challenge.py` komplett (insbesondere die sick-Tests ab ca. L280).
Lese auch `tests/conftest.py` für Fixtures.

### Neue Route-URL

Alle sick-Tests posten jetzt an `/challenge-activities/sick-period` statt `/challenge-activities/sick-week`.

### Sick-Model

`SickWeek` → `SickPeriod` mit Feldern `start_date` (date), `end_date` (date).

### Anpassungen im Einzelnen

1. **Import:** `from app.models.sick_week import SickWeek` → `from app.models.sick_period import SickPeriod`

2. **test_sick_week_creation** → `test_sick_period_creation`:
   - URL: `/challenge-activities/sick-period`
   - Form-Daten: `sick_from=<iso-date>`, `sick_to=<iso-date>` (statt nichts – Legacy-Route gibt jetzt nur Redirect)
   - Assertion: `db.session.query(SickPeriod).count() == 1`
   - Prüfe `start_date` und `end_date` korrekt gesetzt

3. **test_duplicate_sick_week_rejected** → `test_overlapping_sick_period_rejected`:
   - Zweiter POST mit gleichem oder überlappendem Von/Bis
   - Assertion: `db.session.query(SickPeriod).count() == 1` (kein zweiter Eintrag)

4. **test_sick_week_submit_partial** → `test_sick_period_submit_partial`:
   - Form: `sick_from=monday.isoformat()`, `sick_to=(monday + timedelta(days=2)).isoformat()`
   - Assertion: 1 SickPeriod, `sick_period.start_date == monday`, `sick_period.end_date == monday + timedelta(days=2)`

5. **test_sick_week_submit_update** → `test_sick_period_update`:
   - Erstelle SickPeriod, dann POST mit `sick_period_id=<id>` und neuen Daten
   - Assertion: immer noch 1 SickPeriod, aber end_date geändert

6. **test_sick_week_submit_future_rejected** → `test_sick_period_future_allowed`:
   - Zukunftsdatum sollte JETZT ERLAUBT sein (das ist die Kern-Feature-Änderung!)
   - POST mit `sick_from=(today + timedelta(weeks=2)).isoformat()`, `sick_to=(today + timedelta(weeks=2, days=4)).isoformat()`
   - Assertion: `db.session.query(SickPeriod).count() == 1` (wurde gespeichert!)

7. **test_sick_week_submit_von_bis_single_week** → `test_sick_period_von_bis_single_week`:
   - POST mit Von/Bis innerhalb einer Woche
   - Assertion: 1 SickPeriod (kein Split mehr), `start_date` und `end_date` korrekt

8. **test_sick_week_submit_von_bis_two_weeks** → `test_sick_period_von_bis_two_weeks`:
   - POST mit Von/Bis über Wochengrenze
   - WICHTIG: Kein Split mehr! Jetzt wird **1** SickPeriod gespeichert (start_date bis end_date)
   - Assertion: `db.session.query(SickPeriod).count() == 1`
   - Assertion: `sick_period.start_date == sick_from`, `sick_period.end_date == sick_to`

### Neue Tests hinzufügen

```python
def test_sick_period_clamped_to_challenge_bounds(client, db):
    """Zeitraum außerhalb Challenge wird auf Challenge-Grenzen geclampt."""
    # Erstelle Challenge z.B. start=today, end=today+27
    # Sende sick_from = today - 7, sick_to = today + 3
    # Assertion: SickPeriod.start_date == challenge.start_date (geklampt)
    # Assertion: SickPeriod.end_date == today + 3
```

### Hilfsfunktionen in test_challenge.py

Schau dir an wie `_create_challenge_with_participation`, `_create_and_login` etc. definiert sind
und nutze sie für die Fixtures in den neuen Tests.

### Verification

```bash
set -a && source .env && set +a
.venv/bin/pytest tests/test_challenge.py -v --tb=short 2>&1 | tail -30
```

Alle Tests müssen grün sein – besonders die 2 bisher failing Tests.

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: tests/test_challenge.py
SUMMARY: 7 sick-Tests umbenannt und angepasst (neue URL /sick-period, SickPeriod-Felder, kein Split). test_sick_period_future_allowed: Zukunft jetzt ERLAUBT. 2 bisher failing Tests gefixt. 1 neuer Test (clamped_to_challenge_bounds). Alle Tests grün.
TESTS_PASSED: <N>/<total>
RESULT_END
```
