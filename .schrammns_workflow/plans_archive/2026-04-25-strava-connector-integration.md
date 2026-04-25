# Plan: Strava Connector Integration

**Datum:** 2026-04-25
**Ziel:** StravaConnector implementieren, der das bestehende BaseConnector/Provider-Registry-Pattern
nutzt, OAuth2 Authorization Code Flow abwickelt, Tokens Fernet-verschlüsselt in
ConnectorCredential speichert, und über stravalib Aktivitäten abruft. Inklusive zwei
Pflicht-Refactorings (connect_save generalisieren, week_view Multi-Connector).
**Research:** `.schrammns_workflow/research/2026-04-25-strava-connector-integration.md`

---

## Baseline (verifiziert 2026-04-25)

| Metrik | Wert | Verifizierungsbefehl |
|--------|------|----------------------|
| Produktionsdateien geändert | 8 | `ls app/connectors/base.py app/connectors/garmin.py app/routes/connectors.py app/routes/activities.py config.py .env.example requirements.txt app/__init__.py` |
| Neue Produktionsdateien | 2 | `app/connectors/strava.py`, `app/routes/strava_oauth.py` |
| Neue Testdateien | 1 | `tests/test_strava.py` |
| Garmin-Hardcodings in Routen | 5 | `grep -n "garmin_tokens\|provider_type.*garmin\|REGISTRY\[.garmin" app/routes/connectors.py app/routes/activities.py` |
| stravalib in requirements.txt | Nein | `grep stravalib requirements.txt` |
| Aktuelle Testanzahl | 31 | `.venv/bin/pytest --collect-only -q 2>/dev/null \| tail -1` |
| Alle Tests grün | Ja | `.venv/bin/pytest -q --tb=no` |
| Git-Branch | main | `git branch --show-current` |
| Uncommitted changes | 2 Research-MDs | `git status --short` |

---

## Boundaries

**Always:**
- OAuth-State-Parameter (CSRF-Schutz im Callback) muss via `flask.session` verifiziert werden
- `access_token`, `refresh_token`, `expires_at` dürfen nie in Logs oder Flash-Messages erscheinen
- Tokens werden immer über `ConnectorCredential.credentials` Fernet-verschlüsselt gespeichert
- `get_token_updates()` ist der einzige Mechanismus, mit dem ein Connector Tokens in die DB persistiert
- Strava Client-ID und Client-Secret kommen ausschließlich aus Env-Vars (nie hardcoden)
- Nach Token-Refresh muss der neue `refresh_token` sofort persistiert werden (rotating tokens)
- `connect_save`-Route darf nur Felder aus `credential_fields` aus dem Formular übernehmen (kein willkürlicher Input)

**Never:**
- `_garmin_tokens` als Key in generischem Code verwenden (nur innerhalb von GarminConnector)
- `provider_type="garmin"` in Routen hardcoden
- OAuth-`code` Parameter in Logs schreiben
- Strava-Scope auf mehr als `activity:read` erweitern (kein Schreibzugriff)

**Ask First:** keine offenen Entscheidungen (alle durch Research geklärt, s. Design Decisions)

---

## Design Decisions

| Entscheidung | Gewählt | Verworfen | Begründung |
|---|---|---|---|
| OAuth-Flow-Erkennung | `oauth_flow: bool = False` in BaseConnector | Separate OAuth-Blueprint-Klasse | Minimale ABC-Erweiterung, keine Vererbungshierarchie nötig |
| Token-Persistenz-API | `get_token_updates() -> dict` in BaseConnector (Default: `{}`) | `get_fresh_token_json()` überladen | Expliziter, Garmin-unabhängig, passt zu beliebigen Token-Dicts |
| Multi-Provider week_view | `?provider=<type>` Query-Parameter, Fallback auf ersten verbundenen Provider | Eigene Route pro Provider | Kleinste Änderung; keine neuen URL-Muster, rückwärtskompatibel mit Garmin-Bookmarks |
| Strava Token-Refresh | Manueller Check `expires_at < time.time()` in `connect()`, dann `stravalib`-Client-Refresh | stravalib auto-refresh | Explizite Kontrolle; refreshter Token wird sofort in DB persistiert |
| OAuth-State | `secrets.token_urlsafe(16)` in Session gespeichert | Statisches Secret | CSRF-Schutz für OAuth-Callback, State-Rotation per Request |
| Blueprint-Struktur | Separates `strava_oauth.py` für `/connectors/strava/oauth/*` | OAuth-Routes in `connectors.py` | Klare Trennung, `connectors.py` bleibt generisch |
| Template OAuth-Branch | `connect.html` prüft `{% if oauth_flow %}` | Separates Template | DRY; ein Template für alle Provider |

---

## Files to Modify

| File | Change | LOC heute |
|------|--------|-----------|
| `requirements.txt` | `stravalib` hinzufügen | – |
| `app/connectors/base.py` | `oauth_flow: bool = False`; `get_token_updates() -> dict` Default | 17 |
| `app/connectors/garmin.py` | `get_token_updates()` überschreiben; `get_fresh_token_json()` behalten | 60 |
| `app/connectors/__init__.py` | `from app.connectors import strava` hinzufügen | 10 |
| `app/routes/connectors.py` | `connect_save`: `credentials["_garmin_tokens"]` → `connector.get_token_updates()` | 143 |
| `app/routes/activities.py` | `week_view`: `?provider=` Query-Param; Garmin-Hardcodings entfernen | 88 |
| `config.py` | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` aus env | – |
| `.env.example` | `STRAVA_CLIENT_ID=`, `STRAVA_CLIENT_SECRET=` | – |
| `app/__init__.py` | `strava_oauth_bp` registrieren | – |
| `app/templates/connectors/connect.html` | `{% if oauth_flow %}`-Branch: Button statt Formular | 49 |
| **`app/connectors/strava.py`** | **NEU** – StravaConnector | – |
| **`app/routes/strava_oauth.py`** | **NEU** – OAuth-Start + Callback-Routen | – |
| **`tests/test_strava.py`** | **NEU** – ~10 Tests | – |

---

## Implementation Detail

### S-01: Foundation – stravalib + BaseConnector-Erweiterung

**`requirements.txt`:** Zeile `stravalib` hinzufügen.

**`app/connectors/base.py` (aktuell Zeilen 5–17):**
```python
class BaseConnector(ABC):
    provider_type: str = ""
    display_name: str = ""
    credential_fields: list[str] = []
    oauth_flow: bool = False          # NEU: True → OAuth-Redirect statt Formular

    @abstractmethod
    def connect(self, credentials: dict) -> None: ...

    @abstractmethod
    def get_activities(self, start: datetime, end: datetime) -> list: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    def get_token_updates(self) -> dict:  # NEU: Default-Impl., kein abstractmethod
        """Gibt Token-Keys zurück, die nach connect() in credentials gespeichert werden."""
        return {}
```

### S-02: connect_save generalisieren + GarminConnector.get_token_updates()

**`app/routes/connectors.py` Zeilen 106–109 (aktuell):**
```python
# Vorher:
token_json = connector.get_fresh_token_json()
if token_json:
    credentials["_garmin_tokens"] = token_json

# Nachher:
credentials.update(connector.get_token_updates())
```

**`app/connectors/garmin.py`** – neue Methode ergänzen:
```python
def get_token_updates(self) -> dict:
    if self._current_token_json:
        return {"_garmin_tokens": self._current_token_json}
    return {}
```
`get_fresh_token_json()` kann stehen bleiben (wird in `activities.py` genutzt) oder durch
Aufruf von `get_token_updates()` ersetzt werden.

### S-03: StravaConnector

**`app/connectors/strava.py`** (NEU):
```python
import time
from datetime import datetime
from stravalib.client import Client
from app.connectors import register
from app.connectors.base import BaseConnector

@register
class StravaConnector(BaseConnector):
    provider_type = "strava"
    display_name = "Strava"
    credential_fields = []   # kein Passwort-Formular
    oauth_flow = True

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._client: Client | None = None
        self._token_data: dict = {}  # access_token, refresh_token, expires_at

    def connect(self, credentials: dict) -> None:
        """Initialisiert Client; refresht Token wenn abgelaufen."""
        access_token = credentials["access_token"]
        refresh_token = credentials["refresh_token"]
        expires_at = credentials["expires_at"]

        if time.time() > expires_at:
            from flask import current_app
            client_id = current_app.config["STRAVA_CLIENT_ID"]
            client_secret = current_app.config["STRAVA_CLIENT_SECRET"]
            tmp = Client()
            token_response = tmp.refresh_access_token(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
            access_token = token_response["access_token"]
            refresh_token = token_response["refresh_token"]
            expires_at = token_response["expires_at"]
            self._token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
            }
        else:
            self._token_data = {}  # kein Update nötig

        self._client = Client(access_token=access_token)

    def get_token_updates(self) -> dict:
        return self._token_data  # leer wenn kein Refresh, gefüllt nach Refresh

    def get_activities(self, start: datetime, end: datetime) -> list:
        if self._client is None:
            raise RuntimeError("StravaConnector nicht verbunden.")
        raw = list(self._client.get_activities(after=start, before=end, limit=100))
        return [_to_activity_dict(a) for a in raw]

    def disconnect(self) -> None:
        self._client = None
        self._token_data = {}


def _to_activity_dict(a) -> dict:
    """Konvertiert stravalib-Aktivität in das interne Format (wie Garmin-Dict)."""
    return {
        "startTimeLocal": str(a.start_date_local) if a.start_date_local else "",
        "activityName": a.name or "–",
        "activityType": {"typeKey": str(a.type).lower() if a.type else "–"},
        "duration": float(a.elapsed_time.total_seconds()) if a.elapsed_time else 0,
        "distance": float(a.distance) if a.distance else None,
        "averageHR": a.average_heartrate,
        "calories": a.calories,
    }
```

**`app/connectors/__init__.py`** – Zeile hinzufügen:
```python
from app.connectors import garmin  # noqa
from app.connectors import strava  # noqa  ← NEU
```

### S-04: OAuth-Routen + Config + Blueprint + Template

**`config.py`** – neue Felder in Config-Klasse:
```python
STRAVA_CLIENT_ID: str = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET: str = os.environ.get("STRAVA_CLIENT_SECRET", "")
```

**`.env.example`** – neue Zeilen:
```
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
```

**`app/routes/strava_oauth.py`** (NEU):
```python
import secrets
from flask import Blueprint, current_app, flash, redirect, request, session, url_for
from flask_login import current_user, login_required
from stravalib.client import Client
from app.extensions import db
from app.models.connector import ConnectorCredential

strava_oauth_bp = Blueprint("strava_oauth", __name__)
_STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"

@strava_oauth_bp.route("/connectors/strava/oauth/start")
@login_required
def oauth_start():
    state = secrets.token_urlsafe(16)
    session["strava_oauth_state"] = state
    client = Client()
    redirect_uri = url_for("strava_oauth.oauth_callback", _external=True)
    authorize_url = client.authorization_url(
        client_id=current_app.config["STRAVA_CLIENT_ID"],
        redirect_uri=redirect_uri,
        scope=["activity:read"],
        state=state,
    )
    return redirect(authorize_url)

@strava_oauth_bp.route("/connectors/strava/oauth/callback")
@login_required
def oauth_callback():
    error = request.args.get("error")
    if error:
        flash(f"Strava-Verbindung abgelehnt: {error}", "danger")
        return redirect(url_for("connectors.index"))

    state = request.args.get("state", "")
    expected = session.pop("strava_oauth_state", None)
    if not expected or state != expected:
        flash("Ungültiger OAuth-State. Bitte erneut versuchen.", "danger")
        return redirect(url_for("connectors.index"))

    code = request.args.get("code", "")
    tmp = Client()
    token_response = tmp.exchange_code_for_token(
        client_id=current_app.config["STRAVA_CLIENT_ID"],
        client_secret=current_app.config["STRAVA_CLIENT_SECRET"],
        code=code,
    )
    credentials = {
        "access_token": token_response["access_token"],
        "refresh_token": token_response["refresh_token"],
        "expires_at": token_response["expires_at"],
    }

    existing = db.session.execute(
        db.select(ConnectorCredential).where(
            ConnectorCredential.user_id == current_user.id,
            ConnectorCredential.provider_type == "strava",
        )
    ).scalar_one_or_none()

    if existing is None:
        db.session.add(ConnectorCredential(
            user_id=current_user.id,
            provider_type="strava",
            credentials=credentials,
        ))
    else:
        existing.credentials = credentials

    db.session.commit()
    flash("Strava erfolgreich verbunden.", "success")
    return redirect(url_for("connectors.index"))
```

**`app/__init__.py`** – Blueprint registrieren (nach vorhandenen Blueprints):
```python
from app.routes.strava_oauth import strava_oauth_bp
app.register_blueprint(strava_oauth_bp)
```

**`app/templates/connectors/connect.html`** – OAuth-Branch vor dem Formular:
```html
{% if oauth_flow %}
<div class="d-grid mt-4">
  <a href="{{ url_for('strava_oauth.oauth_start') }}"
     class="btn btn-primary">
    Mit {{ display_name }} verbinden
  </a>
</div>
{% else %}
<form method="post" ...>  {# bestehender Formular-Block #}
  ...
</form>
{% endif %}
```
`connect_form`-Route muss `oauth_flow=cls.oauth_flow` an Template übergeben.

**`app/routes/connectors.py` `connect_form`-Funktion** – `oauth_flow` übergeben:
```python
return render_template(
    "connectors/connect.html",
    provider_type=provider,
    display_name=cls.display_name,
    credential_fields=cls.credential_fields,
    oauth_flow=cls.oauth_flow,   # NEU
)
```

### S-05: week_view Multi-Connector

**`app/routes/activities.py` `week_view()`** – Refactoring:
```python
@activities_bp.route("/week")
@login_required
def week_view():
    # Provider-Auswahl: ?provider=strava, Fallback auf ersten verbundenen
    provider_type = request.args.get("provider")
    if not provider_type:
        cred = ConnectorCredential.query.filter_by(
            user_id=current_user.id
        ).first()
        if cred is None:
            return redirect(url_for("connectors.index"))
        provider_type = cred.provider_type
    else:
        cred = ConnectorCredential.query.filter_by(
            user_id=current_user.id, provider_type=provider_type
        ).first()
        if cred is None:
            return redirect(url_for("connectors.index"))

    connector_cls = PROVIDER_REGISTRY.get(provider_type)
    if connector_cls is None:
        abort(404)

    connector = connector_cls(user_id=current_user.id)
    try:
        connector.connect(cred.credentials)
        # Token-Refresh-Persistenz: generisch via get_token_updates()
        updates = connector.get_token_updates()
        if updates:
            updated = dict(cred.credentials)
            updated.update(updates)
            cred.credentials = updated
            db.session.commit()
        raw = connector.get_activities(monday, sunday)
        ...
    except Exception as exc:
        error = str(exc)
```

Alle fünf Hardcodings (`_garmin_tokens`, `provider_type="garmin"`, `REGISTRY["garmin"]`) entfernt.

### S-06: Tests

**`tests/test_strava.py`** (NEU) – Test-Funktionen:

```
test_strava_registered_in_provider_registry
    StravaConnector unter "strava" in PROVIDER_REGISTRY

test_strava_connector_connect_uses_existing_valid_token
    connect() mit gültigem expires_at → kein Refresh, Client wird gesetzt

test_strava_connector_connect_refreshes_expired_token
    connect() mit expires_at in Vergangenheit → refresh_access_token() aufgerufen,
    get_token_updates() gibt neue Tokens zurück

test_strava_connector_get_token_updates_empty_without_refresh
    get_token_updates() → leeres Dict wenn kein Refresh nötig

test_strava_connector_get_token_updates_after_refresh
    get_token_updates() → Dict mit access_token, refresh_token, expires_at nach Refresh

test_strava_connector_get_activities_returns_mapped_list
    get_activities() → Liste mit internem Dict-Format (startTimeLocal, activityName, etc.)

test_strava_connector_get_activities_raises_without_connect
    get_activities() ohne connect() → RuntimeError

test_strava_connector_disconnect_clears_state
    disconnect() → _client=None, _token_data={}

test_oauth_callback_rejects_invalid_state
    GET /connectors/strava/oauth/callback?state=WRONG → 302, Flash-Fehlermeldung

test_oauth_callback_stores_tokens_on_success
    GET /connectors/strava/oauth/callback?code=X&state=Y (State aus Session) →
    ConnectorCredential in DB angelegt, redirect zu connectors.index
```

**Mocking-Strategie** (analog zu `test_connectors.py`):
- `patch("app.connectors.strava.Client")` für stravalib-Client
- `patch("app.routes.strava_oauth.Client")` für OAuth-Token-Exchange

---

## Wave-Struktur

```
Wave 1 (keine Deps, parallel ausführbar)
└── S-01: Foundation – stravalib + BaseConnector-Erweiterung

Wave 2 (depends on S-01, untereinander parallel)
├── S-02: connect_save generalisieren + GarminConnector.get_token_updates()
└── S-03: StravaConnector + Registry-Import

Wave 3 (depends on S-02+S-03, untereinander parallel)
├── S-04: OAuth-Routen + Config + Blueprint + Template
└── S-05: week_view Multi-Connector

Wave 4 (depends on S-02, S-03, S-04, S-05)
└── S-06: Tests
```

---

## Issues

### S-01 – Foundation: stravalib + BaseConnector-Erweiterung
**Wave:** 1 | **Größe:** S | **Risiko:** reversible / local / autonomous-ok

**Was zu tun:**
1. `requirements.txt`: `stravalib` hinzufügen
2. `app/connectors/base.py`: `oauth_flow: bool = False` + `get_token_updates() -> dict` (Default `{}`)

**Acceptance Criteria:**
- [ ] `grep stravalib requirements.txt` liefert eine Zeile
- [ ] `BaseConnector.oauth_flow` ist `False` per Default
- [ ] `BaseConnector().get_token_updates()` raises `TypeError` (abstract) → nein, ist keine abstractmethod, Default-Impl. gibt `{}` zurück
- [ ] `python -c "from app.connectors.base import BaseConnector; print(BaseConnector.oauth_flow)"` → `False`
- [ ] Alle 31 bestehenden Tests weiterhin grün

---

### S-02 – connect_save generalisieren + GarminConnector.get_token_updates()
**Wave:** 2 (depends: S-01) | **Größe:** S | **Risiko:** reversible / local / autonomous-ok

**Was zu tun:**
1. `app/routes/connectors.py:107–109`: `credentials["_garmin_tokens"] = token_json` ersetzen durch `credentials.update(connector.get_token_updates())`
2. `app/connectors/garmin.py`: `get_token_updates()` hinzufügen (gibt `{"_garmin_tokens": ...}` zurück)

**Acceptance Criteria:**
- [ ] `grep "_garmin_tokens" app/routes/connectors.py` → keine Treffer
- [ ] `GarminConnector.get_token_updates()` gibt `{"_garmin_tokens": <token>}` nach connect() zurück
- [ ] `GarminConnector.get_token_updates()` gibt `{}` zurück wenn nicht verbunden
- [ ] Alle 31 Tests grün

---

### S-03 – StravaConnector + Registry-Import
**Wave:** 2 (depends: S-01) | **Größe:** M | **Risiko:** reversible / local / autonomous-ok

**Was zu tun:**
1. `app/connectors/strava.py` neu erstellen (s. Implementation Detail S-03)
2. `app/connectors/__init__.py`: `from app.connectors import strava` ergänzen

**Acceptance Criteria:**
- [ ] `python -c "from app.connectors import PROVIDER_REGISTRY; assert 'strava' in PROVIDER_REGISTRY"` → kein Fehler
- [ ] `StravaConnector.oauth_flow` ist `True`
- [ ] `StravaConnector.credential_fields` ist `[]`
- [ ] Import läuft ohne Fehler: `from app.connectors.strava import StravaConnector`
- [ ] Alle 31 Tests grün

---

### S-04 – OAuth-Routen + Config + Blueprint + Template
**Wave:** 3 (depends: S-02, S-03) | **Größe:** M | **Risiko:** reversible / system / requires-approval

**Was zu tun:**
1. `config.py`: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` aus env
2. `.env.example`: neue Zeilen
3. `app/routes/strava_oauth.py` neu (s. Implementation Detail S-04)
4. `app/__init__.py`: `strava_oauth_bp` registrieren
5. `app/templates/connectors/connect.html`: `{% if oauth_flow %}`-Branch
6. `app/routes/connectors.py` `connect_form`: `oauth_flow=cls.oauth_flow` übergeben

**Acceptance Criteria:**
- [ ] `GET /connectors/strava/connect` rendert Button (kein Formular)
- [ ] `GET /connectors/strava/oauth/start` (eingeloggt) → 302 Redirect zu `strava.com`
- [ ] `GET /connectors/strava/oauth/callback?error=access_denied` → 302 + Flash-Fehlermeldung
- [ ] `GET /connectors/strava/oauth/callback?state=FALSCH` → 302 + Flash „Ungültiger OAuth-State"
- [ ] Alle 31 Tests grün

---

### S-05 – week_view Multi-Connector
**Wave:** 3 (depends: S-03) | **Größe:** S | **Risiko:** reversible / local / autonomous-ok

**Was zu tun:**
1. `app/routes/activities.py:29–50`: `?provider=` Query-Parameter, alle 5 Garmin-Hardcodings entfernen

**Acceptance Criteria:**
- [ ] `grep "provider_type.*garmin\|REGISTRY\[.garmin\|_garmin_tokens" app/routes/activities.py` → keine Treffer
- [ ] `GET /activities/week` ohne `?provider=` → nutzt ersten verbundenen Provider
- [ ] `GET /activities/week?provider=garmin` → nutzt Garmin (Regression-Check)
- [ ] Alle 31 Tests grün

---

### S-06 – Tests
**Wave:** 4 (depends: S-02, S-03, S-04, S-05) | **Größe:** M | **Risiko:** reversible / local / autonomous-ok

**Was zu tun:**
1. `tests/test_strava.py` neu mit 10 Test-Funktionen (s. Implementation Detail S-06)

**Acceptance Criteria:**
- [ ] `.venv/bin/pytest tests/test_strava.py -v` → 10/10 grün
- [ ] `.venv/bin/pytest -q --tb=no` → alle Tests grün (≥ 41 collected)
- [ ] Keine neuen Warnings

---

## Invalidation Risks

| Risiko | Betrifft | Mitigation |
|--------|----------|-----------|
| stravalib v2.3 inkompatibel mit Python 3.14 | S-03, S-06 | `pip install stravalib` in S-01 sofort testen |
| stravalib `Client.authorization_url()` / `exchange_code_for_token()` API anders als dokumentiert | S-04 | stravalib-Doku und Changelog prüfen vor Impl. |
| `app/__init__.py` Blueprint-Registrierungs-Pattern unbekannt | S-04 | Vorhandene Blueprint-Registrierungen als Vorlage nutzen |
| `activities.py` Refactoring bricht bestehende Garmin-Smoke-Tests | S-05 | `?provider=garmin` explizit testen nach Impl. |

---

## Rollback-Strategie

**Gesamt:** `git tag -a before-strava -m "Checkpoint vor Strava-Integration"` vor Wave 1
**Pro Wave:** `git revert HEAD~N` wenn Wave-Commit fehlerhaft
**Pro Issue:** jedes Issue wird atomar committed → einzeln revertierbar
**DB:** kein Schema-Change → keine Migration nötig, kein Backup erforderlich

---

## Verifikations-Befehle (Gesamtplan)

```bash
# Nach jedem Issue:
.venv/bin/pytest -q --tb=no

# Nach S-05 (Regression Garmin):
grep -n "garmin" app/routes/activities.py  # nur noch in Kommentaren/Strings ok

# Nach S-06 (Gesamt):
.venv/bin/pytest -v
grep -rn "_garmin_tokens\|provider_type.*=.*garmin" app/routes/  # keine Treffer

# Strava-Endpoint manuell (Dev-Server laufend):
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/connectors/strava/connect
# → 200 oder 302 (je nach Login-Status)
```
