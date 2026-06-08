# Briefing: I-10 – Tests – test_activities_log.py + test_challenge_delete.py

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-pv6

## File Ownership

**WRITE:** `tests/test_activities_log.py`
**WRITE:** `tests/test_challenge_delete.py`

## Was zu tun ist

**ZUERST:** Lese beide Testdateien komplett.

### test_activities_log.py – Delete-Tests anpassen (ca. L553–614)

1. **Import:** `from app.models.sick_week import SickWeek` → `from app.models.sick_period import SickPeriod`

2. **Fixtures in den 3 Delete-Tests** von `SickWeek(...)` auf `SickPeriod(start_date=..., end_date=...)` umstellen:
   - `test_delete_sick_week_own` → `test_delete_sick_period_own`
   - `test_delete_sick_week_other_user_rejected` → `test_delete_sick_period_other_user_rejected`
   - `test_admin_deletes_sick_week_of_other_user` → `test_admin_deletes_sick_period_of_other_user`

3. **URL in den Tests** von `/challenge-activities/sick-week/<id>/delete` auf `/challenge-activities/sick-period/<id>/delete` ändern.

4. **Fixture-Erstellung:** Typischer alter Code:
   ```python
   sw = SickWeek(user_id=user.id, challenge_id=challenge.id, week_start=date.today() - timedelta(days=7), sick_days=3)
   ```
   Neuer Code:
   ```python
   sp = SickPeriod(user_id=user.id, challenge_id=challenge.id,
                   start_date=date.today() - timedelta(days=7),
                   end_date=date.today() - timedelta(days=5))
   ```

### test_challenge_delete.py – Cascade-Prüfung anpassen (ca. L60–89)

1. **Import:** `from app.models.sick_week import SickWeek` → `from app.models.sick_period import SickPeriod`

2. **Fixture-Erstellung** (ca. L70–75): `SickWeek(...)` → `SickPeriod(start_date=..., end_date=...)`

3. **Prüfung nach Delete** (ca. L85–89): 
   ```python
   assert db.session.get(SickWeek, sw_id) is None
   ```
   →
   ```python
   assert db.session.get(SickPeriod, sp_id) is None
   ```

### Verification

```bash
set -a && source .env && set +a
.venv/bin/pytest tests/test_activities_log.py tests/test_challenge_delete.py -v 2>&1 | tail -20
```

Alle Tests müssen grün sein.

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: tests/test_activities_log.py, tests/test_challenge_delete.py
SUMMARY: SickWeek-Fixtures auf SickPeriod umgestellt. Delete-URLs auf /sick-period/<id>/delete. Testfunktionen umbenannt. Alle Tests grün.
RESULT_END
```
