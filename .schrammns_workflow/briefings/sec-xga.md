# Briefing: SEC-F10 – Strava-Provider ausblenden wenn CLIENT_ID nicht konfiguriert

**Issue:** sport-challenge-xga | Priorität P2
**Working Directory:** /Users/schrammn/Documents/VSCodium/sport-challenge

## Mission

OAuth-Provider (wie Strava) sollen in der Connector-Liste ausgeblendet werden, wenn die notwendigen Env-Vars (CLIENT_ID/SECRET) nicht gesetzt sind.

## Konkrete Änderungen

### 1. `app/connectors/base.py` – is_configured() Klassenmethode

Füge in `BaseConnector` eine neue Klassenmethode ein:

```python
@classmethod
def is_configured(cls) -> bool:
    """Gibt True zurück wenn der Provider einsatzbereit ist.
    OAuth-Provider können diese Methode überschreiben um Config-Checks durchzuführen."""
    return True
```

### 2. `app/connectors/strava.py` – is_configured() überschreiben

Füge in `StravaConnector` hinzu:

```python
@classmethod
def is_configured(cls) -> bool:
    try:
        from flask import current_app
        return bool(
            current_app.config.get("STRAVA_CLIENT_ID")
            and current_app.config.get("STRAVA_CLIENT_SECRET")
        )
    except RuntimeError:
        return False
```

### 3. `app/routes/connectors.py` – index() filtern

Aktuell (Zeilen 55–65):
```python
    providers = []
    for provider_type, cls in PROVIDER_REGISTRY.items():
        cred = _get_credential(current_user.id, provider_type)
        providers.append(...)
```

Ändern zu:
```python
    providers = []
    for provider_type, cls in PROVIDER_REGISTRY.items():
        if not cls.is_configured():
            continue
        cred = _get_credential(current_user.id, provider_type)
        providers.append(...)
```

## Acceptance Criteria

- [ ] `grep "is_configured" app/connectors/base.py app/connectors/strava.py app/routes/connectors.py` → 3 Dateien mit Treffern
- [ ] `.venv/bin/pytest -q --tb=no` → alle Tests grün

## File Ownership
- `app/connectors/base.py`
- `app/connectors/strava.py`
- `app/routes/connectors.py`

## Structured Result (PFLICHT)
```
RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/connectors/base.py, app/connectors/strava.py, app/routes/connectors.py
SUMMARY: <1-2 Sätze>
BLOCKERS:
RESULT_END
```
