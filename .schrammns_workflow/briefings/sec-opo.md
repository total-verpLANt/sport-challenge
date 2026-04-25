# Briefing: SEC-F5 – connect_save für OAuth-Provider sperren (abort 400)

**Issue:** sport-challenge-opo | Priorität P1
**Working Directory:** /Users/schrammn/Documents/VSCodium/sport-challenge

## Mission

Einen `abort(400)`-Guard in `connect_save` einbauen, der OAuth-Provider (oauth_flow=True) daran hindert, den Passwort-Formular-POST-Handler zu erreichen.

## Konkrete Änderung

### `app/routes/connectors.py` – connect_save (Zeilen 82–124)

Füge direkt nach `cls = _get_provider_cls(provider)` (Zeile 86) ein:

```python
    # OAuth-Provider haben kein Credentials-Formular – POST ist nicht erlaubt
    if cls.oauth_flow:
        abort(400)
```

Die Funktion sieht danach so aus:
```python
@connectors_bp.route("/<provider>/connect", methods=["POST"])
@login_required
def connect_save(provider: str):
    """Credentials speichern: Test-Login, Token in DB ablegen (Fernet-verschlüsselt)."""
    cls = _get_provider_cls(provider)

    # OAuth-Provider haben kein Credentials-Formular – POST ist nicht erlaubt
    if cls.oauth_flow:
        abort(400)

    # Nur bekannte Felder aus dem Formular übernehmen – niemals beliebige Input-Keys
    credentials = {
    ...
```

## Acceptance Criteria

- [ ] `grep "oauth_flow" app/routes/connectors.py` → Treffer in connect_save
- [ ] `.venv/bin/pytest -q --tb=no` → alle Tests grün
- [ ] Manuell verifizierbar: `StravaConnector.oauth_flow` ist True → POST /connectors/strava/connect würde 400 zurückgeben

## File Ownership
- `app/routes/connectors.py`

## Structured Result (PFLICHT)
```
RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/connectors.py
SUMMARY: <1-2 Sätze>
BLOCKERS:
RESULT_END
```
