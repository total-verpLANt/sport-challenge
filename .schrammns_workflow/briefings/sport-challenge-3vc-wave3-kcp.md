# Briefing: I-05 – challenge_activities.py – Neue Sick-Routen (SickPeriod)

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-kcp

## Context

`challenge_activities.py` importiert bereits `SickPeriod` (Import umgestellt), nutzt aber
noch SickWeek-Logik intern. Es gibt drei Bereiche zu ändern:
1. `_sick_days_per_week()` Hilfsfunktion entfernen
2. `sick_week_submit()` komplett durch `sick_period_submit()` ersetzen
3. `delete_sick_week()` durch `delete_sick_period()` ersetzen
4. `my_week()` View: SickWeek-Lookup auf SickPeriod-Overlap umstellen

## File Ownership

**WRITE:** `app/routes/challenge_activities.py` (nur diese Datei)

## Was zu tun ist

**ZUERST:** Lese die gesamte Datei oder zumindest die relevanten Abschnitte:
- L198–220 (my_week sick_week loading)
- L222–337 (sick_week_submit und _sick_days_per_week)
- L549–567 (delete_sick_week)

### 1. `_sick_days_per_week()` entfernen (L222–230)

Diese Hilfsfunktion vollständig löschen – wird durch SickPeriod-Logik ersetzt.

### 2. `sick_week_submit()` durch `sick_period_submit()` ersetzen (L233–337)

Die gesamte Funktion ersetzen. Neue Funktion:

```python
@challenge_activities_bp.route("/sick-period", methods=["POST"])
@login_required
def sick_period_submit():
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))

    challenge = participation.challenge

    sick_from_raw = request.form.get("sick_from", "").strip()
    sick_to_raw = request.form.get("sick_to", "").strip()
    sick_period_id = request.form.get("sick_period_id", type=int)

    try:
        sick_from = date.fromisoformat(sick_from_raw)
        sick_to = date.fromisoformat(sick_to_raw)
    except ValueError:
        flash("Ungültige Datumsangabe.")
        return redirect(url_for("challenge_activities.log_form"))

    if sick_from > sick_to:
        flash("Das Von-Datum muss vor oder gleich dem Bis-Datum liegen.")
        return redirect(url_for("challenge_activities.log_form"))

    # Clampen auf Challenge-Grenzen
    clamped_start = max(sick_from, challenge.start_date)
    clamped_end = min(sick_to, challenge.end_date)

    if clamped_start > clamped_end:
        flash("Der Zeitraum liegt außerhalb der Challenge-Periode.")
        return redirect(url_for("challenge_activities.log_form"))

    # Overlap-Check: keine überlappenden Perioden (eigene ausschließen bei Update)
    overlap_query = db.select(SickPeriod).where(
        SickPeriod.user_id == current_user.id,
        SickPeriod.challenge_id == challenge.id,
        SickPeriod.start_date <= clamped_end,
        SickPeriod.end_date >= clamped_start,
    )
    if sick_period_id:
        overlap_query = overlap_query.where(SickPeriod.id != sick_period_id)

    if db.session.scalar(overlap_query) is not None:
        flash("Dieser Zeitraum überschneidet sich mit einer bestehenden Krankmeldung.")
        return redirect(url_for("challenge_activities.log_form"))

    if sick_period_id:
        period = db.session.get(SickPeriod, sick_period_id)
        if period is None or period.user_id != current_user.id:
            flash("Krankmeldung nicht gefunden.")
            return redirect(url_for("challenge_activities.log_form"))
        period.start_date = clamped_start
        period.end_date = clamped_end
        db.session.commit()
        flash(f"Krankmeldung aktualisiert: {clamped_start.strftime('%d.%m.%Y')} – {clamped_end.strftime('%d.%m.%Y')}.")
    else:
        db.session.add(SickPeriod(
            user_id=current_user.id,
            challenge_id=challenge.id,
            start_date=clamped_start,
            end_date=clamped_end,
        ))
        db.session.commit()
        flash(f"Krankmeldung eingetragen: {clamped_start.strftime('%d.%m.%Y')} – {clamped_end.strftime('%d.%m.%Y')}.")

    # Redirect: wenn aus my_week (offset im Form), dorthin zurück; sonst log_form
    offset = request.form.get("offset", type=int)
    if offset is not None:
        return redirect(url_for("challenge_activities.my_week", offset=offset))
    return redirect(url_for("challenge_activities.log_form"))
```

### 3. `delete_sick_week()` durch `delete_sick_period()` ersetzen (L549–567)

```python
@challenge_activities_bp.route("/sick-period/<int:sick_period_id>/delete", methods=["POST"])
@login_required
def delete_sick_period(sick_period_id: int):
    period = db.session.get(SickPeriod, sick_period_id)
    if period is None or (
        period.user_id != current_user.id and not current_user.is_admin
    ):
        abort(403)
    user_id = period.user_id
    challenge_id = period.challenge_id
    db.session.delete(period)
    db.session.commit()
    flash("Krankmeldung gelöscht.")
    if current_user.is_admin and current_user.id != user_id:
        return redirect(url_for("challenge_activities.user_activities",
                                 challenge_id=challenge_id, user_id=user_id))
    return redirect(url_for("challenge_activities.my_week"))
```

### 4. `my_week()` View – SickPeriod-Lookup (ca. L198–218)

Finde den Block der `sick_week` lädt:
```python
    sick_week = None
    if participation:
        sick_week = db.session.execute(
            db.select(SickWeek).where(
                SickWeek.user_id == current_user.id,
                SickWeek.challenge_id == participation.challenge_id,
                SickWeek.week_start == monday,
            )
        ).scalar_one_or_none()
```

Ersetzen durch:
```python
    sick_period = None
    sick_days_val = 0
    if participation:
        sick_period = db.session.execute(
            db.select(SickPeriod).where(
                SickPeriod.user_id == current_user.id,
                SickPeriod.challenge_id == participation.challenge_id,
                SickPeriod.start_date <= week_end,
                SickPeriod.end_date >= monday,
            )
        ).scalar_one_or_none()
        if sick_period is not None:
            eff_start = max(sick_period.start_date, monday)
            eff_end = min(sick_period.end_date, week_end)
            sick_days_val = min((eff_end - eff_start).days + 1, 7)
```

Und das Template-Keyword `sick_week=sick_week` durch `sick_period=sick_period, sick_days_val=sick_days_val` ersetzen.

**WICHTIG:** `week_end` muss in `my_week()` definiert sein. Prüfe ob es bereits existiert (aus `_get_week_bounds(offset)`) oder füge es hinzu: `week_end = monday + timedelta(days=6)`.

### 5. Bereinigung

Keine `SickWeek`-Referenzen in der Datei lassen. Prüfen:
```bash
grep -n "SickWeek\|sick_week\b\|sick_days_per_week\|/sick-week" app/routes/challenge_activities.py
```

**Ausnahme:** `sick_period` und `sick_days_val` als neue Variablennamen sind OK.

## Cross-Cutting Constraints

- Zukunftsdaten erlaubt (KEIN `if sick_to > today` Check!)
- Keine überlappenden Perioden: Overlap-Check vor Create/Update
- end_date immer NOT NULL
- `sick_period_id` im Form → Update; kein `sick_period_id` → Create
- `abort` muss importiert sein (`from flask import ..., abort`)

## Verification

```bash
grep -n "SickWeek\|sick_week\b" app/routes/challenge_activities.py  # muss leer sein
grep -n "sick_period\|SickPeriod\|sick_days_val" app/routes/challenge_activities.py  # soll Treffer zeigen
```

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/challenge_activities.py
SUMMARY: _sick_days_per_week() entfernt. sick_week_submit() durch sick_period_submit() (/sick-period) ersetzt mit Von/Bis, Clamping, Overlap-Prüfung, Create/Update via sick_period_id. delete_sick_week() durch delete_sick_period() (/sick-period/<id>/delete) ersetzt. my_week() auf SickPeriod-Overlap umgestellt (sick_period + sick_days_val). Keine SickWeek-Referenzen mehr.
RESULT_END
```
