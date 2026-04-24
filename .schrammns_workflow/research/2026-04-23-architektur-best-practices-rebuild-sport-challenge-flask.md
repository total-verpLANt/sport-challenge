# Research: Architektur & Best Practices – Sport-Challenge Flask Rebuild

**Date:** 2026-04-23
**Scope:** Architekturentscheidungen, Extension-Stack, Sicherheit, Connector-Pattern und Provider-APIs fuer den Rebuild von Single-User-Prototyp zu Multi-User-App
**Semantic Analysis:** Vollstaendig via Serena MCP
**Web Research:** Teilweise degradiert – WebSearch auf Opus blockiert, Sonnet-Sub-Agent als Fallback, Context7 fuer Flask-SQLAlchemy und Flask-Login

## Executive Summary

- Die bestehende App (250 Zeilen Python, 120 Zeilen HTML) ist sauber strukturiert (App Factory + Blueprints), hat aber **keine Datenbank, kein User-Management, keine Tests und mehrere Security-Luecken** (kein CSRF, debug=True, world-readable Tokens).
- Der empfohlene Stack: **Flask-SQLAlchemy + Flask-Migrate + Flask-Login + Fernet (cryptography)** – bewaehrte Extensions mit guter Doku und Kompatibilitaet.
- **Connector-Architektur**: Abstract Base Class mit Provider-Registry. Garmin ist sofort integrierbar, Strava via OAuth2, Komoot nur via inoffizieller API (fragil), Samsung Health **nicht realistisch integrierbar** (kein Web-API).
- **HKDF statt PBKDF2** fuer Fernet-Key-Ableitung aus SECRET_KEY (hochentropisches Secret, nicht Passwort).
- **Werkzeug scrypt-Default** ist fuer ein lokales Projekt ausreichend; fuer Produktion waere argon2id besser.

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | App Factory – muss um Extensions, neue Blueprints und Error Handler erweitert werden |
| `app/routes/auth.py` | Komplett-Rewrite: von Garmin-Direct zu lokalem Username/Passwort-Login |
| `app/routes/activities.py` | Umbau: von direktem GarminClient-Aufruf auf Connector-Abstraction |
| `app/garmin/client.py` | UNVERAENDERT beibehalten – wird von GarminConnector gewrapped |
| `config.py` | Erweitern um SQLALCHEMY_DATABASE_URI |
| `app/templates/base.html` | Erweitern: current_user, Dropdown-Navigation, Flash-Messages |
| `requirements.txt` | Erweitern um flask-sqlalchemy, flask-migrate, flask-login, cryptography |

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| Flask | >=3.0 (aktuell 3.1.3) | Web-Framework |
| Flask-SQLAlchemy | >=3.1 | ORM-Integration (App Factory via `db.init_app(app)`) |
| Flask-Migrate | >=4.0 | Alembic-Migrationen (`flask db migrate/upgrade`) |
| Flask-Login | >=0.6 | Session-Management (`UserMixin`, `login_required`, `current_user`) |
| cryptography | >=41.0 | Fernet-Verschluesselung fuer Connector-Credentials |
| werkzeug | >=3.0 (via Flask) | Passwort-Hashing (scrypt-Default) |
| garminconnect | ==0.3.3 | Garmin Connect API-Wrapper (0.3.3 vom 22.04.2026, Fix fuer OAuth-Breaking-Change vom 17.03.2026) |
| SQLite | (stdlib) | Lokale Datenbank |
| Bootstrap | 5.3.3 (CDN) | Frontend-Framework |

## Findings

### 1. Flask Extensions Zusammenspiel (App Factory Pattern)

**Quelle:** Context7 Flask-SQLAlchemy Doku, Flask-Login GitHub

Das empfohlene Pattern fuer Flask 3.x mit App Factory:

```python
# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
```

```python
# app/__init__.py
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    # ... Blueprints registrieren
    return app
```

**Wichtig:** Flask-SQLAlchemy 3.x erwartet `DeclarativeBase` statt `db.Model` als Basis. Der User-Loader wird am `login_manager` registriert:

```python
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
```

Flask-Login stellt `current_user` als Template-Variable bereit – kein manuelles `session`-Handling mehr noetig. `current_user.is_authenticated` und `current_user.is_active` ersetzen den aktuellen `session["garmin_email"]`-Check.
Citation: `app/routes/auth.py:20-26` (aktueller custom decorator wird ersetzt)

### 2. Passwort-Hashing

**Ergebnis:** Werkzeug 3.x nutzt **scrypt** als Default (seit 3.0.0).

Parameter: `n=2^15`, `r=8`, `p=1`, Salt: 16 Bytes.
OWASP empfiehlt `n=2^17` – Werkzeug liegt knapp darunter.

Fuer ein **lokales Projekt ist der Default ausreichend**. Argon2id (via `argon2-cffi`) waere die OWASP-Topwahl, erfordert aber eine zusaetzliche C-Extension. Empfehlung: Werkzeug-Default beibehalten, spaeter optional auf Argon2 upgraden.

### 3. Fernet-Key-Ableitung

**Kernentscheidung: HKDF, nicht PBKDF2.**

Begruendung: `SECRET_KEY` ist ein hochentropisches Secret (64 hex chars = 256 Bit), kein Passwort. PBKDF2 ist designed fuer niedrigentropische Passwoerter und verschwendet hier CPU-Zyklen ohne Sicherheitsgewinn. HKDF (RFC 5869) ist der korrekte KDF fuer key-to-key Derivation.

```python
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
import base64

def derive_fernet_key(secret_key: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"sport-challenge-v1",        # fixer Context-Salt, ok bei hochentropischem Input
        info=b"connector-credentials",
    )
    return base64.urlsafe_b64encode(hkdf.derive(secret_key.encode()))
```

Fester Salt ist laut RFC 5869 Sec. 3.1 akzeptabel, solange das Ausgangsgeheimnis hochentropisch ist. Wichtig: SECRET_KEY muss mindestens 32 Bytes haben (aktuell: 64 hex = 32 Bytes, passt).
Citation: `config.py:5`, `.env` (SECRET_KEY ist 64 hex chars)

### 4. Connector/Provider-Architektur

**Empfehlung: Abstract Base Class mit Provider-Registry.**

Protocol-basiert (typing.Protocol) waere Pythonischer, bietet aber keinen Laufzeit-Enforcement. ABC gibt klare Fehlermeldungen, wenn eine Methode fehlt.

```python
# app/connectors/base.py
from abc import ABC, abstractmethod
from datetime import date

class BaseConnector(ABC):
    provider_type: str
    display_name: str
    credential_fields: list[dict]  # [{"name": "email", "type": "email", "label": "E-Mail"}, ...]

    @abstractmethod
    def connect(self, credentials: dict) -> None: ...

    @abstractmethod
    def get_activities(self, start: date, end: date) -> list[dict]: ...

    @abstractmethod
    def disconnect(self) -> None: ...
```

Registry-Pattern:
```python
# app/connectors/__init__.py
PROVIDER_REGISTRY: dict[str, type[BaseConnector]] = {}

def register(cls):
    PROVIDER_REGISTRY[cls.provider_type] = cls
    return cls
```

Neuen Provider hinzufuegen = 1 Datei mit `@register` Decorator. Kein anderer Code muss geaendert werden.

**credential_fields** erlaubt dynamische Formular-Generierung: Garmin braucht Email+Passwort, Strava braucht OAuth2-Redirect, Komoot braucht Username+Passwort.

### 5. Provider-API-Analyse

#### Garmin Connect (garminconnect 0.3.3)
- **Version-Pinning:** 0.3.3 (Release 22.04.2026) – enthaelt Fix fuer Garmin-Breaking-Change vom 17.03.2026 (Issue #332, geschlossen)
- **Auth:** SSO-basiert, Tokens auf Disk in `~/.garminconnect/garmin_tokens.json` (Mode 0600, lib-seitig gesetzt)
- **Risiken:** Cloudflare-Blocking beim Login (Issue #350), 429 Rate Limiting (Issue #337)
- **MFA:** Via Callback-Funktion unterstuetzt: `Garmin(..., prompt_mfa=lambda: input("MFA code: "))`. Im Flask-Kontext muss der Callback aus dem Request-Cycle austreten (Session + Redirect zu MFA-Form + Resume Login)
- **Auto-Refresh:** Library prueft Token-Expiry vor jedem Request, refreshed via `diauth.garmin.com` automatisch
- **Empfehlung:** Robust mit Retry-Logik und spezifischer Exception-Behandlung (`GarminConnectAuthenticationError`, `GarminConnectConnectionError`, `GarminConnectTooManyRequestsError`) umgehen
- **Token-Isolation:** Fuer Multi-User muss `token_dir` pro User sein (z.B. `GARMIN_TOKEN_DIR/<user_id>/`)
Citation: `app/garmin/client.py:16` (`os.makedirs(self._token_dir, exist_ok=True)`)

#### Strava
- **Auth:** OAuth2 Authorization Code Flow (3-legged)
- **Scopes:** `activity:read_all` fuer alle Aktivitaeten inkl. privater
- **Tokens:** Access (6h), Refresh (langlebig, Single-Use)
- **Lokal nutzbar:** Ja, `redirect_uri=http://localhost:PORT/callback`
- **Python-Lib:** `stravalib` verfuegbar
- **Empfehlung:** OAuth2-Flow in Connector kapseln, Tokens verschluesselt in DB speichern, Auto-Refresh

#### Komoot
- **Auth:** Inoffizielle REST-API mit Basic Auth (Email + Passwort)
- **Basis-URL:** `https://api.komoot.de/v007/`
- **Risiken:** Nicht dokumentiert, nicht stabil, potenzieller ToS-Verstoss
- **Empfehlung:** Als "experimentell" kennzeichnen, mit Risiko-Hinweis im UI

#### Samsung Health
- **Auth:** KEIN Web-API vorhanden
- **Status:** Android SDK deprecated seit Juli 2025
- **Realistische Integration:** Nur via manuellem Datei-Upload (CSV/JSON)
- **Empfehlung:** Nicht als Connector implementieren, sondern ggf. als "Import"-Feature spaeter

### 6. RBAC (Role-Based Access Control)

Einfaches Decorator-Pattern ohne Flask-Principal:

```python
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

Stacking: `@login_required` UNTER `@admin_required` (Flask evaluiert von unten nach oben).
Rolle als String-Feld (`'user'`/`'admin'`) reicht fuer dieses Projekt.

### 7. Security-Audit des Ist-Zustands

| Finding | Severity | Location | Fix in Phase |
|---------|----------|----------|--------------|
| Kein CSRF | CRITICAL | `auth/login.html:14` | Phase 2 (optional Flask-WTF) |
| Garmin-Tokens world-readable (644) | CRITICAL | `client.py:16` | Phase 3 (per-User Token-Dir mit 700) |
| `debug=True` hardcoded | HIGH | `run.py:6` | Phase 1 (env-basiert) |
| Weak SECRET_KEY Fallback | HIGH | `config.py:5` | Phase 1 (Fallback entfernen) |
| Exception-Leakage | MEDIUM | `auth.py:47`, `activities.py:51` | Phase 2 (generische Messages) |
| Kein Rate Limiting | MEDIUM | `auth.py:29` | Phase 5 (Flask-Limiter optional) |
| Logout via GET | LOW | `auth.py:52` | Phase 2 (POST-only) |

### 8. SQLite Sicherheit

**Entscheidung: Application-Level Fernet-Encryption auf Feldebene.**

SQLCipher (ganze DB verschluesselt) ist Over-Engineering fuer ein lokales Hobby-Projekt. Fernet auf sensiblen Feldern (Connector-Credentials) ist ausreichend, wartbar und hat keine Drittbibliothek-Risiken.

**Update 2026-04-23:** Falls SQLCipher spaeter doch gewuenscht wird, ist `pysqlcipher3` inzwischen deprecated. Aktiver Nachfolger ist `sqlcipher3` (coleifer, v0.6.2 vom 07.01.2026) mit Python-3.14-Wheels fuer macOS ARM64/x86_64 inkl. Free-Threaded-Variante. Installation via `pip install sqlcipher3-binary` (self-contained, keine libsqlcipher-Abhaengigkeit). SQLAlchemy-Dialect-Kompatibilitaet ist im Upstream unter Tracking (Issue #5848).

Sichtbare DB-Metadaten (Schema, Usernamen) sind fuer ein lokales Projekt kein realistisches Bedrohungsszenario.

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Flask Extension Stack | 4 | Context7-Doku + Code analysiert, Patterns verifiziert |
| Passwort-Hashing | 3 | Werkzeug-Defaults bekannt, OWASP-Vergleich gemacht |
| Fernet/HKDF | 3 | RFC 5869 referenziert, Code-Pattern entworfen |
| Connector-Architektur | 3 | ABC-Pattern designed, Registry-Mechanismus klar |
| Garmin API | 3 | client.py analysiert, Issue-Landschaft bekannt |
| Strava API | 2 | OAuth2-Flow bekannt, Details aus Sub-Agent (keine offizielle Doku verifiziert) |
| Komoot API | 1 | Nur Geruechte/Community-Wissen, keine offizielle Quelle |
| Samsung Health | 2 | Kein Web-API, Faktenlage klar |
| Bestehende Codebase | 4 | Jede Zeile gelesen und analysiert |
| Security-Ist-Zustand | 4 | Vollstaendiger Audit mit 12 Findings |
| RBAC/Decorator-Pattern | 3 | Pattern verifiziert, Stacking-Reihenfolge klar |

## Knowledge Gaps

**Update 2026-04-23:** Die must-fill und nice-to-have Luecken wurden durch die WebSearch-Nachrecherche geschlossen. Details in `.schrammns_workflow/research/2026-04-23-websearch-ergebnisse.md`.

| Gap | Priority | Status | Erkenntnis |
|-----|----------|--------|------------|
| Strava OAuth2: exakte redirect_uri-Regeln fuer localhost | must-fill | ✅ GEFUELLT | `localhost` + `127.0.0.1` sind explizit whitelisted (Strava Developer Docs). Access-Token: 6h, Refresh: rollierend single-use |
| Komoot API: Stabilitaet und aktuelle Endpunkte | nice-to-have | ✅ GEFUELLT | Keine oeffentliche API (nur Partner). Inoffiziell: `api.komoot.de/v007/` mit Basic Auth. Aktivste Python-Lib: `Tsadoq/kompy` v0.0.10 (Feb 2025). Empfehlung: nur als "experimentell" oder GPX-Upload statt API |
| garminconnect >0.3.2: Breaking Changes seit unserer Version? | must-fill | ✅ GEFUELLT | Version **0.3.3** released 22.04.2026 mit Fix fuer Issue #332 (Garmin-Breaking-Change am OAuth-Endpoint, 17.03.2026). Upgrade empfohlen |
| werkzeug scrypt auf macOS/Python 3.14: Kompatibilitaet? | nice-to-have | ✅ GEFUELLT | Keine bekannten Probleme, scrypt ist hashlib-C-Binding. Werkzeug-Default (N=2^15) liegt unter OWASP-Empfehlung (N=2^17) – fuer lokales Projekt akzeptabel |
| Flask-SQLAlchemy DeclarativeBase: Migration von db.Model? | nice-to-have | ✅ BEREITS KLAR | Context7 Doku gelesen, Pattern verifiziert |
| Samsung Health Web-API | verified | ✅ BESTAETIGT | Existiert nicht. Android-SDK End-of-Service 2028. Neue Data SDK ist ebenfalls Android-only. Nicht als Connector integrierbar |
| SQLCipher Python-3.14-Support | neu erhoben | ✅ GEFUELLT | `pysqlcipher3` deprecated. Nachfolger: `sqlcipher3` (v0.6.2 vom 07.01.2026), Python-3.14-Wheels fuer macOS ARM64/x86_64 verfuegbar |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Flask-SQLAlchemy 3.x kompatibel mit Python 3.14 | No | Nicht getestet, aber keine bekannten Inkompatibilitaeten |
| werkzeug scrypt funktioniert auf macOS | Yes | Standard-hashlib-C-Binding, keine bekannten macOS/Python-3.14-Inkompatibilitaeten |
| HKDF mit festem Salt ist sicher bei hochentropischem Input | Yes | RFC 5869 Section 3.1 |
| Garmin-Token-Dir kann per-User isoliert werden | Yes | `client.py:10` – `token_dir` ist Konstruktor-Parameter |
| Strava erlaubt localhost als redirect_uri | Yes | Offiziell bestaetigt in Strava Developer Docs: "`localhost` and `127.0.0.1` are white-listed" |
| Samsung Health hat kein Web-API | Yes | developer.samsung.com, Android-SDK-only |
| Komoot hat keine offizielle API | Yes | Keine Doku auf komoot.com/developer |
| SECRET_KEY in .env ist 256 Bit | Yes | `.env`: 64 hex chars = 32 Bytes = 256 Bit |

## Recommendations

1. **Stack beibehalten** wie geplant: Flask-SQLAlchemy + Flask-Migrate + Flask-Login + cryptography (Fernet)
2. **HKDF statt PBKDF2** fuer Fernet-Key-Ableitung – korrekter Ansatz fuer key-to-key Derivation
3. **Samsung Health streichen** als Connector – kein Web-API, nicht realistisch integrierbar. End-of-Service der Android-SDK 2028. Ggf. spaeter als manueller Import via Datei-Upload
4. **Komoot als experimentell** kennzeichnen – inoffizielle API, kann jederzeit brechen. Alternative: GPX/FIT-Datei-Upload statt Credential-basierte Integration
5. **Security-Findings sofort adressieren**: debug=True und SECRET_KEY-Fallback in Phase 1 fixen
6. **Per-User Token-Isolation** fuer Garmin: `GARMIN_TOKEN_DIR/<user_id>/` statt globalem Verzeichnis
7. **garminconnect auf 0.3.3 pinnen** (Release 22.04.2026) – enthaelt Fix fuer Breaking Change vom 17.03.2026
8. **`admin_required` verkettet `login_required`** intern – kein Stacking durch Caller noetig, reduziert Fehlerrisiko (POST-Routen vergessen etc.)
9. **MFA-Support fuer Garmin** im Multi-User-Modell von Anfang an planen – Callback-Flow erfordert Session-basierte Zwischenspeicherung und Redirect zu MFA-Formular
10. ~~WebSearch-Nachrecherche fuer Luecken bei Strava und garminconnect durchfuehren~~ ✅ **ERLEDIGT am 2026-04-23**, Ergebnisse in `.schrammns_workflow/research/2026-04-23-websearch-ergebnisse.md`
