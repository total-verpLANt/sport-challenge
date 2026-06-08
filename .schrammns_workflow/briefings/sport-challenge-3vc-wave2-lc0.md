# Briefing: I-02 – penalty.py – Overlap-Berechnung statt SickWeek-Lookup

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-lc0

## Context

Das SickWeek-Modell wurde durch SickPeriod ersetzt (start_date, end_date, beide NOT NULL).
Das `penalty.py` importiert bereits `SickPeriod` (Import wurde in Wave 1 umgestellt), nutzt
aber noch `SickWeek`-Logik intern. Das muss jetzt auf SickPeriod umgebaut werden.

## File Ownership

**WRITE:** `app/services/penalty.py` (nur diese Datei)

## Was zu tun ist

### 1. Lese zuerst die aktuelle Datei

```bash
cat app/services/penalty.py
```

### 2. Ändere `calculate_weekly_penalty`

Ersetze den bisherigen `SickWeek`-Lookup durch eine neue interne Funktion.

**Neue interne Funktion** (vor `calculate_weekly_penalty` einfügen):

```python
def _sick_days_in_week(user_id: int, challenge_id: int, week_start: date) -> int:
    """Count sick days that fall within the given week from SickPeriod records."""
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

**Ändere `calculate_weekly_penalty`**: Ersetze den bisherigen Block:
```python
    # 1. Check SickWeek
    sick_week = db.session.execute(
        db.select(SickWeek).where(
            SickWeek.user_id == user_id,
            SickWeek.challenge_id == challenge_id,
            SickWeek.week_start == week_start,
        )
    ).scalar_one_or_none()
    if sick_week is not None:
        deductions = sick_week.sick_days // 2
        effective_goal = max(0, weekly_goal - deductions)
        if effective_goal <= 0:
            return 0.0
        fulfilled = count_fulfilled_days(user_id, challenge_id, week_start)
        missed = max(0, effective_goal - fulfilled)
        return missed * penalty_per_miss
```

durch:
```python
    # 1. Check SickPeriod overlap
    sick_days = _sick_days_in_week(user_id, challenge_id, week_start)
    if sick_days > 0:
        deductions = sick_days // 2
        effective_goal = max(0, weekly_goal - deductions)
        if effective_goal <= 0:
            return 0.0
        fulfilled = count_fulfilled_days(user_id, challenge_id, week_start)
        missed = max(0, effective_goal - fulfilled)
        return missed * penalty_per_miss
```

### 3. Entferne ungenutzte Imports

Stelle sicher, dass am Ende keine `SickWeek`-Referenz mehr in der Datei steht.
Der Import `from app.models.sick_period import SickPeriod` ist bereits vorhanden.

## Verification

```python
# Mentales Check: 
# sick_days=3 → deductions=1, effective_goal = max(0, weekly_goal - 1)
# sick_days=6 → deductions=3, effective_goal = max(0, weekly_goal - 3), bei goal=3 → 0 → return 0.0
# sick_days=0 → if-Block nicht betreten → Normal-Berechnung
```

Kein test-run nötig – Tests kommen in Wave 5 (I-08).

## Cross-Cutting Constraints

- Keine SickWeek-Referenzen dürfen übrig bleiben
- _sick_days_in_week ist eine interne Funktion (kein Export)
- Die Formel `sick_days // 2` bleibt unverändert

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/services/penalty.py
SUMMARY: _sick_days_in_week() Overlap-Funktion eingefügt, calculate_weekly_penalty auf SickPeriod umgestellt. Keine SickWeek-Referenzen mehr.
RESULT_END
```
