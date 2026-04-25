# Research: Strava Connector Integration für sport-challenge Flask-App

**Date:** 2026-04-25
**Scope:** Bestehende Connector-Architektur (BaseConnector, GarminConnector, ConnectorCredential, Routen) vs. Strava OAuth2-Anforderungen; Implementierungsplan für StravaConnector

---

## Executive Summary

- Das bestehende Connector-Pattern ist solide und erweiterbar, **aber es enthält zwei kritische Garmin-Hardcodings**, die vor oder gleichzeitig mit der Strava-Integration bereinigt werden müssen.
- Strava verwendet **OAuth2 Authorization Code Flow** (kein Username/Password) – das aktuelle `connect_form`-Muster (HTML-Formular mit `credential_fields`) passt nicht. Es braucht ein Redirect-Flow mit Callback-Route.
- `stravalib` v2.3 ist ein aktiv gewartetes Python-SDK mit automatischer Token-Refresh-Logik – passt gut als Wrapper.
- Access Tokens laufen nach **6 Stunden** ab; Refresh Tokens sind langlebig und werden nach jedem Refresh ausgetauscht (rotating).
- Der Gesamtaufwand ist **mittel**: 1 neuer Connector, 2 neue Routen (OAuth-Start + Callback), 2 Refactoring-Fixes, Template-Anpassung, ~8 neue Tests.

---

## Key Files

| Datei | Zweck |
|-------|-------|
| `app/connectors/base.py` | BaseConnector ABC – Klassenattribute + Abstract Methods |
| `app/connectors/__init__.py` | PROVIDER_REGISTRY + `@register` Decorator |
| `app/connectors/garmin.py` | GarminConnector – Vorlage für neuen StravaConnector |
| `app/models/connector.py` | ConnectorCredential mit `_JsonFernetField` (Fernet-verschlüsseltes JSON) |
| `app/utils/crypto.py` | FernetField TypeDecorator + HKDF Key Derivation |
| `app/routes/connectors.py` | Connector-UI Routen (connect_form, connect_save, disconnect) |
| `app/routes/activities.py` | week_view – **hardcoded "garmin"** (Zeilen 29–35) |
| `tests/conftest.py` | Test-Fixtures: app (session), db, client |
| `tests/test_connectors.py` | 9 Connector-Tests (Mocking-Muster für neue Tests) |

---

## Technology Stack

| Library/Framework | Version | Rolle |
|---|---|---|
| Flask | – | Web-Framework |
| Flask-Login | – | Auth / current_user |
| SQLAlchemy | – | ORM, TypeDecorator für FernetField |
| cryptography | – | Fernet, HKDF |
| stravalib | v2.3 (aktuell) | Python-Wrapper für Strava API v3 |
| requests/httpx | – | Strava Token-Exchange (direkt oder via stravalib) |

---

## Findings

### 1. BaseConnector ABC (`app/connectors/base.py:5–17`)

```python
class BaseConnector(ABC):
    provider_type: str = ""
    display_name: str = ""
    credential_fields: list[str] = []

    @abstractmethod
    def connect(self, credentials: dict) -> None: ...

    @abstractmethod
    def get_activities(self, start: datetime, end: datetime) -> list: ...

    @abstractmethod
    def disconnect(self) -> None: ...
```

- `credential_fields` steuert, welche Felder das HTML-Formular anzeigt.
- Für Strava muss `credential_fields = []` sein (kein Passwort-Formular), aber der OAuth-Flow braucht eine andere Route.
- Es gibt **keinen Mechanismus** im ABC für OAuth-Flows – das ist **Lücke #1**.

### 2. PROVIDER_REGISTRY + @register (`app/connectors/__init__.py:1–10`)

```python
PROVIDER_REGISTRY: dict = {}

def register(cls):
    PROVIDER_REGISTRY[cls.provider_type] = cls
    return cls

from app.connectors import garmin  # noqa
```

- Neuer Connector: `from app.connectors import strava` hier hinzufügen → automatisch registriert.
- Kein weiterer Boilerplate nötig.

### 3. GarminConnector als Vorlage (`app/connectors/garmin.py`)

Voller Daten-Fluss:
1. `__init__(user_id)` → speichert `_user_id`, `_client=None`, `_current_token_json=None`
2. `connect(credentials)` → Zwei-Pfad: Reconnect (wenn `_garmin_tokens` in credentials) oder Erstlogin
3. `get_fresh_token_json()` → gibt Token-String zurück für DB-Persistenz
4. `get_activities(start, end)` → delegiert an `_client.get_week_activities()`
5. `disconnect()` → setzt `_client` und `_current_token_json` auf None

Für Strava: gleiche Struktur, aber `connect()` bekommt `access_token`, `refresh_token`, `expires_at` aus dem OAuth-Callback statt Username/Password.

### 4. ConnectorCredential Fernet-Feld (`app/models/connector.py:26–44`)

```python
credentials: Mapped[dict] = mapped_column(_JsonFernetField(), nullable=False)
```

- Speichert beliebiges JSON-Dict Fernet-verschlüsselt.
- Für Strava wird das Dict so aussehen:
  ```json
  {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1745600000
  }
  ```
- Kein Schema-Change nötig – das Model unterstützt Strava ohne Migration.

### 5. KRITISCH: Hardcoding `_garmin_tokens` in connect_save (`app/routes/connectors.py:107–109`)

```python
token_json = connector.get_fresh_token_json()
if token_json:
    credentials["_garmin_tokens"] = token_json  # ← GARMIN-SPEZIFISCH!
```

Das ist ein **Garmin-spezifischer Key** im generischen `connect_save`. Für Strava würde hier kein Token gespeichert. **Fix:** Connector-Methode `get_token_updates() -> dict` einführen, die einen Dict mit zu speichernden Zusatz-Keys zurückgibt, und `connect_save` so umbauen:
```python
credentials.update(connector.get_token_updates())
```

### 6. KRITISCH: Hardcoding `"garmin"` in week_view (`app/routes/activities.py:29–35`)

```python
cred = ConnectorCredential.query.filter_by(
    user_id=current_user.id, provider_type="garmin"  # ← HARDCODED!
).first()
...
connector_cls = PROVIDER_REGISTRY["garmin"]  # ← HARDCODED!
```

Die Aktivitäts-Route unterstützt aktuell **nur Garmin**. Für Multi-Connector muss entweder:
- Ein Prioritäts-System implementiert werden (erster verbundener Provider), oder
- Die Route auf einen `provider`-Query-Parameter umgestellt werden, oder
- Strava eine eigene Route `/activities/week?provider=strava` bekommt.

**Empfehlung:** Query-Parameter `?provider=strava` mit Fallback auf ersten verbundenen Provider.

### 7. OAuth2 Flow für Strava (externe Quelle)

Strava Authorization Code Flow:
1. **Start:** `GET https://www.strava.com/oauth/authorize?client_id=X&redirect_uri=Y&response_type=code&scope=activity:read_all`
2. **Callback:** `GET /connectors/strava/oauth/callback?code=ABC` → POST to `https://www.strava.com/api/v3/oauth/token` mit `code`, `client_id`, `client_secret`, `grant_type=authorization_code`
3. **Response:** `{ "access_token": "...", "refresh_token": "...", "expires_at": 1234567890 }`
4. **Refresh:** Wenn `expires_at < time.time()`, POST mit `grant_type=refresh_token`
5. **Rotating Refresh Tokens:** Jeder Refresh gibt einen neuen `refresh_token` zurück – muss persistiert werden.

Neue Routen nötig:
- `GET /connectors/strava/oauth/start` → Redirect zu Strava
- `GET /connectors/strava/oauth/callback` → Code-Exchange, Token speichern

### 8. stravalib API-Patterns

```python
from stravalib.client import Client

# Initialisierung mit gespeicherten Tokens
client = Client(
    access_token="...",
    refresh_token="...",
    token_expires=expires_at  # Unix-Timestamp
)

# Aktivitäten abrufen
activities = list(client.get_activities(
    after=start_datetime,
    before=end_datetime,
    limit=100
))

# Manueller Refresh (falls nötig)
token_response = client.refresh_access_token(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=current_refresh_token
)
```

- stravalib prüft bei jedem API-Call automatisch `token_expires` und refresht bei Bedarf, wenn `refresh_token` und Credentials gesetzt sind.
- Alternativ: manueller Check in `connect()` mit `time.time() > expires_at`.

### 9. Test-Patterns (aus `tests/test_connectors.py`)

Mocking-Strategie: `patch("app.connectors.garmin.GarminClient")` – auf Modul-Ebene, nicht auf Instanz.
Für Strava analog: `patch("app.connectors.strava.Client")` (stravalib Client).

Noch nicht getestete Szenarien (Lücken):
- OAuth-Callback-Route (Code-Exchange)
- Token-Refresh nach Ablauf
- Rotation des Refresh-Tokens (neuer Token nach Refresh)
- `scope` fehlt / abgelehnt vom User

---

## Depth Ratings

| Bereich | Rating | Notiz |
|---------|--------|-------|
| BaseConnector ABC | 4 | Vollständig gelesen, alle Methoden verstanden |
| PROVIDER_REGISTRY / @register | 4 | Vollständig, trivial |
| GarminConnector (Vorlage) | 4 | Vollständiger Datenfluss nachvollzogen |
| ConnectorCredential / FernetField | 4 | Vollständig verstanden |
| connect_save / disconnect Routen | 4 | Kritisches Hardcoding identifiziert |
| week_view / activities Route | 3 | Hardcoding klar, Refactoring-Strategie noch offen |
| Strava OAuth2 Flow | 3 | Aus API-Doku verstanden, noch nicht lokal implementiert |
| stravalib Python API | 2 | Doku gelesen, konkrete Methoden bekannt, nicht ausprobiert |
| Test-Patterns für OAuth | 2 | Mocking-Muster bekannt, OAuth-spezifische Tests fehlen komplett |

---

## Knowledge Gaps

| Gap | Priorität | Wie füllen |
|-----|-----------|------------|
| `client_id`/`client_secret` Verwaltung: wo in config.py? Env-Vars? | must-fill | Design-Entscheidung vor Impl. |
| stravalib auto-refresh: funktioniert es out-of-the-box oder braucht es custom Logik? | must-fill | Lokaler Test mit `stravalib` |
| State-Parameter im OAuth-Callback (CSRF-Schutz des OAuth-Flows) | must-fill | Strava-Docs + Flask-Session |
| Welche Felder liefert `client.get_activities()` zurück? (Mapping auf vorhandenes Template-Format) | must-fill | stravalib-Doku lesen |
| Granularität der Aktivitäten-API: Reicht ein Wochenfilter oder nur "alle Aktivitäten paginiert"? | nice-to-have | stravalib-Doku |
| Scope `activity:read_all` vs `activity:read`: welcher reicht? | nice-to-have | Strava Developer Docs |
| Strava Developer Program Approval für Multi-User: Prozess/Dauer? | nice-to-have | Strava Dev Portal |

---

## Assumptions

| Annahme | Verifiziert? | Belege |
|---------|-------------|--------|
| ConnectorCredential speichert beliebige JSON-Dicts ohne Schema-Änderung | Ja | `connector.py:33` – `credentials: Mapped[dict]` |
| FernetField funktioniert für Strava-Tokens ohne Änderung | Ja | `crypto.py:20–44` – generischer TypeDecorator |
| `@register` + Import in `__init__.py` reicht für Registry | Ja | `__init__.py:10` |
| stravalib v2.3 ist kompatibel mit Python 3.14 | Nein | Nur PyPI gelesen, nicht lokal getestet |
| Strava liefert `expires_at` als Unix-Timestamp (nicht `expires_in`) | Ja | Strava API Docs |
| `week_view` muss refactored werden – Garmin-Hardcoding blockiert Strava | Ja | `activities.py:29,35` |
| `connect_save` Garmin-Hardcoding blockiert Token-Speicherung für Strava | Ja | `connectors.py:109` |

---

## Recommendations

### Pflicht-Refactorings (vor oder gleichzeitig mit Strava-Impl.)

**R-1: `connect_save` generalisieren** (`connectors.py:107–109`)
```python
# Vorher (Garmin-spezifisch):
credentials["_garmin_tokens"] = token_json

# Nachher (generisch):
credentials.update(connector.get_token_updates())
```
BaseConnector erhält Default-Implementierung `get_token_updates() -> dict: return {}`.
GarminConnector überschreibt: `return {"_garmin_tokens": self._current_token_json} if self._current_token_json else {}`.

**R-2: `week_view` auf Multi-Connector umstellen** (`activities.py:29–35`)
`?provider=<type>` Query-Parameter einführen, Fallback auf ersten verbundenen Provider.

### OAuth-Erweiterung des BaseConnector

**R-3:** Optionales Klassenattribut `oauth_flow: bool = False` in BaseConnector.
Wenn `True`, zeigt `connect_form`-Route statt Formular einen "Verbinden"-Button → redirect zu `/<provider>/oauth/start`.

### StravaConnector Implementierung

**R-4:** Neue Datei `app/connectors/strava.py`:
```python
@register
class StravaConnector(BaseConnector):
    provider_type = "strava"
    display_name = "Strava"
    credential_fields = []
    oauth_flow = True

    def connect(self, credentials: dict) -> None:
        # credentials = {"access_token": ..., "refresh_token": ..., "expires_at": ...}
        # Refresh prüfen, stravalib.Client initialisieren

    def get_token_updates(self) -> dict:
        # Aktualisierte Tokens zurückgeben (nach Refresh)

    def get_activities(self, start, end) -> list: ...
    def disconnect(self) -> None: ...
```

**R-5:** Neue Routen in `app/routes/strava_oauth.py`:
- `GET /connectors/strava/oauth/start` → Strava-Redirect mit State (CSRF)
- `GET /connectors/strava/oauth/callback` → Code-Exchange, Token in DB speichern

**R-6:** `STRAVA_CLIENT_ID` und `STRAVA_CLIENT_SECRET` als Env-Vars in `config.py`.

### Tests

**R-7:** ~8 neue Tests in `tests/test_connectors_strava.py`:
- `StravaConnector` im Registry
- `connect()` mit gültigem Token (kein Refresh nötig)
- `connect()` mit abgelaufenem Token (Refresh wird ausgelöst)
- `get_token_updates()` gibt aktualisierten Token zurück
- `get_activities()` gibt formatierte Liste zurück
- OAuth-Callback-Route: erfolgreicher Code-Exchange
- OAuth-Callback-Route: ungültiger State (CSRF-Fehler)
- OAuth-Callback-Route: Strava-Fehler (access_denied)

---

## Quellen

- [stravalib Authentifizierung Doku v2.3](https://stravalib.readthedocs.io/en/v2.3/get-started/authenticate-with-strava.html)
- [Strava API OAuth2 Authentifizierung](https://developers.strava.com/docs/authentication/)
- [stravalib PyPI](https://pypi.org/project/stravalib/)
- [stravalib GitHub](https://github.com/stravalib/stravalib)
