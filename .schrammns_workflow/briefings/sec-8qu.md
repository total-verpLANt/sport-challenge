# Briefing: SEC-F4 – OAuth-State mit 10-Minuten-Ablaufzeit

**Issue:** sport-challenge-8qu | Priorität P3
**Working Directory:** /Users/schrammn/Documents/VSCodium/sport-challenge

## Mission

Den OAuth-State in der Session mit einem Timestamp versehen, damit abgelaufene States (>10 Min) abgewiesen werden.

## Konkrete Änderungen

### `app/routes/strava_oauth.py`

**oauth_start() – State mit Timestamp speichern:**

Aktuell:
```python
    state = secrets.token_urlsafe(16)
    session["strava_oauth_state"] = state
```

Ersetzen durch:
```python
    import time
    state = secrets.token_urlsafe(16)
    session["strava_oauth_state"] = {"state": state, "ts": time.time()}
```

**oauth_callback() – State-Validierung mit Ablaufprüfung:**

Aktuell:
```python
    state = request.args.get("state", "")
    expected = session.pop("strava_oauth_state", None)
    if not expected or state != expected:
        flash("Ungültiger OAuth-State. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))
```

Ersetzen durch:
```python
    import time
    state = request.args.get("state", "")
    stored = session.pop("strava_oauth_state", None)
    if not stored or state != stored.get("state"):
        flash("Ungültiger OAuth-State. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))
    if time.time() - stored.get("ts", 0) > 600:
        flash("OAuth-Sitzung abgelaufen. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))
```

`import time` am Datei-Anfang ergänzen (nach `import secrets`).

## Acceptance Criteria

- [ ] `grep "ts.*time.time\|stored.get.*ts" app/routes/strava_oauth.py` → Treffer
- [ ] `.venv/bin/pytest -q --tb=no` → alle Tests grün
  - Hinweis: Der bestehende Test `test_oauth_callback_rejects_invalid_state` muss angepasst werden – `session["strava_oauth_state"]` ist jetzt ein Dict statt ein String. Passe den Test an: `sess["strava_oauth_state"] = {"state": "correct_state", "ts": time.time()}`
  - Der Test `test_oauth_callback_stores_credential_on_success` ebenfalls anpassen: `sess["strava_oauth_state"] = {"state": correct_state, "ts": time.time()}`

## File Ownership
- `app/routes/strava_oauth.py`
- `tests/test_strava.py` (2 Tests anpassen)

## Structured Result (PFLICHT)
```
RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/strava_oauth.py, tests/test_strava.py
SUMMARY: <1-2 Sätze>
BLOCKERS:
RESULT_END
```
