# Briefing: SEC-F1/F2 – Generische Fehler-Flashes + sicheres Exception-Logging

**Issue:** sport-challenge-cxs | Priorität P1
**Working Directory:** /Users/schrammn/Documents/VSCodium/sport-challenge

## Mission

Rohe Exception-Strings aus Flash-Messages entfernen. Exceptions server-seitig loggen, User bekommt nur generische Meldungen.

## Konkrete Änderungen

### 1. `app/routes/strava_oauth.py` – oauth_callback absichern

**Aktuell (Zeilen 55–66):**
```python
    code = request.args.get("code", "")
    tmp = Client()
    token_response = tmp.exchange_code_for_token(
        client_id=current_app.config["STRAVA_CLIENT_ID"],
        client_secret=current_app.config["STRAVA_CLIENT_SECRET"],
        code=code,
    )
    credentials = {
        "access_token": token_response["access_token"],
        ...
    }
```

**Ersetzen durch:**
```python
    code = request.args.get("code", "")
    if not code:
        flash("Kein Autorisierungscode erhalten. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))

    try:
        tmp = Client()
        token_response = tmp.exchange_code_for_token(
            client_id=current_app.config["STRAVA_CLIENT_ID"],
            client_secret=current_app.config["STRAVA_CLIENT_SECRET"],
            code=code,
        )
        credentials = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response["refresh_token"],
            "expires_at": int(token_response["expires_at"]),
        }
    except Exception:
        current_app.logger.exception("Strava token exchange fehlgeschlagen")
        flash("Strava-Verbindung fehlgeschlagen. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))
```

Den Rest der Funktion (DB-Speicherung) in `try`-Block einschließen oder separat lassen – wichtig: `credentials` darf nicht im Exception-Scope sein.

### 2. `app/routes/connectors.py` – Zeile 104: f-String entfernen

**Aktuell:**
```python
    except Exception as exc:
        flash(f"Verbindung fehlgeschlagen: {exc}", "danger")
```

**Ersetzen durch:**
```python
    except Exception:
        from flask import current_app
        current_app.logger.exception("Connector connect() fehlgeschlagen für provider=%s user=%s", provider, current_user.id)
        flash("Verbindung fehlgeschlagen. Bitte Zugangsdaten prüfen.", "danger")
```

### 3. `app/routes/activities.py` – Zeile 78: str(exc) entfernen

**Aktuell:**
```python
    except Exception as exc:
        error = str(exc)
```

**Ersetzen durch:**
```python
    except Exception:
        from flask import current_app
        current_app.logger.exception("Aktivitäten konnten nicht geladen werden für provider=%s user=%s", provider_type, current_user.id)
        error = "Aktivitäten konnten nicht geladen werden. Bitte versuche es später erneut."
```

## Acceptance Criteria

- [ ] `grep -n 'flash.*{exc}\|flash.*str(exc)\|error = str(exc)' app/routes/` → keine Treffer
- [ ] `grep -n 'logger.exception' app/routes/strava_oauth.py app/routes/connectors.py app/routes/activities.py` → 3 Treffer
- [ ] Datei `app/routes/strava_oauth.py`: `if not code:` Guard vorhanden
- [ ] `.venv/bin/pytest -q --tb=no` → alle Tests grün

## File Ownership
- `app/routes/strava_oauth.py`
- `app/routes/connectors.py`
- `app/routes/activities.py`

## Structured Result (PFLICHT)
```
RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/strava_oauth.py, app/routes/connectors.py, app/routes/activities.py
SUMMARY: <1-2 Sätze>
BLOCKERS:
RESULT_END
```
