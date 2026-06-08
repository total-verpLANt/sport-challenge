# Briefing: I-03 – weekly_summary.py – Pre-Fetch auf SickPeriod

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-83m

## Context

Das SickWeek-Modell wurde durch SickPeriod ersetzt (start_date, end_date, beide NOT NULL).
`weekly_summary.py` importiert bereits `SickPeriod`, nutzt aber noch `SickWeek`-Logik.
Das Dashboard verwendet `wd.is_sick` (bool) und `wd.sick_days` (int 0-7) – diese Signatur
MUSS erhalten bleiben.

## File Ownership

**WRITE:** `app/services/weekly_summary.py` (nur diese Datei)

## Was zu tun ist

### 1. Lese zuerst die aktuelle Datei komplett

```bash
cat app/services/weekly_summary.py
```

### 2. Ersetze den SickWeek-Pre-Fetch-Block (ca. L60-67)

**Aktueller Code (zu ersetzen):**
```python
    # 3. Pre-fetch all SickWeeks for this challenge in one query
    sick_weeks_rows = db.session.execute(
        db.select(SickWeek).where(SickWeek.challenge_id == challenge.id)
    ).scalars().all()
    # Index: (user_id, week_start) -> sick_days
    sick_index: dict[tuple[int, date], int] = {
        (sw.user_id, sw.week_start): sw.sick_days for sw in sick_weeks_rows
    }
```

**Neuer Code:**
```python
    # 3. Pre-fetch all SickPeriods for this challenge in one query
    from collections import defaultdict
    all_sick_periods = db.session.scalars(
        db.select(SickPeriod).where(SickPeriod.challenge_id == challenge.id)
    ).all()
    # Group by user_id for O(1) lookup per user
    sick_by_user: dict[int, list] = defaultdict(list)
    for sp in all_sick_periods:
        sick_by_user[sp.user_id].append(sp)
```

### 3. Füge lokale Hilfsfunktion ein (vor `get_challenge_summary`)

```python
def _sick_days_from_periods(periods: list, week_start: date) -> int:
    """Count sick days overlapping with the given week."""
    week_end = week_start + timedelta(days=6)
    total = 0
    for p in periods:
        if p.start_date <= week_end and p.end_date >= week_start:
            eff_start = max(p.start_date, week_start)
            eff_end = min(p.end_date, week_end)
            total += (eff_end - eff_start).days + 1
    return min(total, 7)
```

### 4. Ersetze die Nutzung des sick_index (ca. L78-79)

**Aktueller Code (zu ersetzen):**
```python
            sick_days_val = sick_index.get((user.id, week_start))
            is_sick = sick_days_val is not None
```

**Neuer Code:**
```python
            sick_days_val = _sick_days_from_periods(sick_by_user[user.id], week_start)
            is_sick = sick_days_val > 0
```

**WICHTIG:** `sick_days_val` ist jetzt immer ein `int` (0-7), nicht mehr `int | None`.
Prüfe alle weiteren Verwendungen von `sick_days_val` in der Datei – falls irgendwo
`if sick_days_val is not None` steht, auf `if sick_days_val > 0` ändern.
Die Ausgabe im weeks_data-Dict muss `sick_days_val` weiterhin als int enthalten
(0 wenn nicht krank, 1-7 wenn krank).

### 5. Entferne SickWeek-Referenzen

Stelle sicher, dass keine `SickWeek`-Referenz mehr in der Datei steht.

## Cross-Cutting Constraints

- `wd.is_sick` und `wd.sick_days` im Dashboard-Output erhalten bleiben (int-Wert, nicht None)
- Kein N+1: ein Bulk-Fetch für alle Perioden der Challenge
- Keine SickWeek-Referenzen dürfen übrig bleiben
- `from collections import defaultdict` am Anfang der Funktion oder als Top-Level-Import

## Verification

Mental check:
- User hat SickPeriod(start_date=Mo, end_date=So) für eine Woche → sick_days_val = 7
- User hat keine Periode → sick_days_val = 0 → is_sick = False
- User hat Periode die teilweise in die Woche reicht (z.B. Fr-Di) → Overlap korrekt berechnet

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/services/weekly_summary.py
SUMMARY: _sick_days_from_periods() Hilfsfunktion eingefügt. sick_index-Dict durch SickPeriod-Bulk-Fetch + defaultdict ersetzt. sick_days_val ist jetzt immer int (0-7). is_sick = sick_days_val > 0. Dashboard-Signatur erhalten.
RESULT_END
```
