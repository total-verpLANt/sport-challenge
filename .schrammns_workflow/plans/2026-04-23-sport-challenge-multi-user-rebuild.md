# Plan: Sport-Challenge – Multi-User Rebuild mit Connector-Architektur

**Date:** 2026-04-23
**Goal:** Rebuild vom Single-User-Prototyp zur Multi-User-Flask-App mit Connector-Architektur (Garmin sofort, Strava/Komoot optional)
**Research:** `.schrammns_workflow/research/2026-04-23-architektur-best-practices-rebuild-sport-challenge-flask.md`
**WebSearch-Ergebnisse:** `.schrammns_workflow/research/2026-04-23-websearch-ergebnisse.md`
**Phase-1-Plan (vorhanden):** `.schrammns_workflow/plans/2026-04-23-garmin-flask-wochenansicht.md` (bereits implementiert, Wave 1+2)

---

## Baseline Audit

| Metrik | Wert | Befehl |
|--------|------|--------|
| Python-Module (app/) | 6 | `find app -name "*.py" \| wc -l` |
| Gesamt-LOC Python | 193 | `wc -l run.py config.py app/**/*.py` |
| Templates (HTML) | 3 | `find app/templates -name "*.html" \| wc -l` |
| Blueprints registriert | 2 (auth, activities) | `grep -c register_blueprint app/__init__.py` |
| Tests vorhanden | 0 | `find . -name "test_*.py" -not -path "./.venv/*"` |
| User-Model | ❌ Keine DB, Email in Session | `app/routes/auth.py:login()` |
| CSRF-Schutz | ❌ Kein Flask-WTF | `grep -r CSRF .` → 0 Treffer |
| DEBUG-Mode | ⚠️ Hardcoded `True` | `run.py:6` |
| SECRET_KEY-Fallback | ⚠️ `"dev-only-change-in-prod"` | `config.py:5` |
| garminconnect-Version | 0.3.2 (veraltet) | `requirements.txt` |
| Git-Status | clean + 2 untracked (.schrammns_workflow, .serena) | `git status` |

---

## Files to Modify (Roadmap)

| Datei | Änderung |
|-------|----------|
| `run.py` | DEBUG via env-Variable steuern |
| `config.py` | SECRET_KEY-Fallback entfernen, DB-URI, DEBUG via env |
| `requirements.txt` | Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, Flask-Limiter, cryptography, garminconnect 0.3.3 |
| `app/extensions.py` | **NEU** – db, migrate, login_manager, csrf, limiter |
| `app/__init__.py` | App Factory: Extensions initialisieren, neue Blueprints registrieren |
| `app/utils/__init__.py` | **NEU** – leer |
| `app/utils/crypto.py` | **NEU** – HKDF-Key-Derivation + FernetField |
| `app/utils/decorators.py` | **NEU** – admin_required (verkettet login_required) |
| `app/utils/retry.py` | **NEU** – retry_on_rate_limit Decorator |
| `app/models/__init__.py` | **NEU** – Model-Exporte |
| `app/models/user.py` | **NEU** – User mit UserMixin, is_admin, set/check_password |
| `app/models/connector.py` | **NEU** – ConnectorCredential mit Fernet-verschlüsselten Feldern |
| `app/connectors/__init__.py` | **NEU** – PROVIDER_REGISTRY + register-Decorator |
| `app/connectors/base.py` | **NEU** – BaseConnector ABC |
| `app/connectors/garmin.py` | **NEU** – GarminConnector (wrapt bestehenden GarminClient) |
| `app/garmin/client.py` | UNVERÄNDERT – wird vom GarminConnector gewrapped |
| `app/routes/auth.py` | REWRITE – Flask-Login, Register + Login + Logout (POST) |
| `app/routes/activities.py` | Auf Connector-Abstraction umbauen |
| `app/routes/connectors.py` | **NEU** – UI zum Verbinden/Trennen von Providern |
| `app/templates/base.html` | Navbar-Update mit current_user + Dropdown |
| `app/templates/auth/login.html` | CSRF-Token, neues Flask-Login-Form |
| `app/templates/auth/register.html` | **NEU** |
| `app/templates/connectors/index.html` | **NEU** – Provider-Übersicht |
| `app/templates/connectors/connect.html` | **NEU** – Credential-Formular |
| `migrations/` | **NEU** – Alembic-Migrationsordner (via `flask db init`) |
| `tests/` | **NEU** – pytest + pytest-flask Suite |

---

## Boundaries

**Always:**
- Alle neuen `<form>` haben CSRF-Token (Flask-WTF)
- Connector-Credentials werden NIE im Klartext in DB/Logs geschrieben – Fernet-Feldverschlüsselung
- `SECRET_KEY` ist zwingend via Umgebung zu setzen – kein Fallback mehr
- Atomare Commits: ein Issue = ein Fix = ein Commit
- Token-Verzeichnisse pro User isoliert (`GARMIN_TOKEN_DIR/<user_id>/`)
- Rollen-Check ausschließlich via `@admin_required`, niemals direkt `current_user.role == "admin"`

**Never:**
- Bestehenden `GarminClient` (app/garmin/client.py) umbauen – nur wrappen
- Samsung Health als Connector-Modul anlegen (kein Web-API)
- Komoot-Credentials speichern, ohne explizit als "experimentell" zu kennzeichnen
- `garth`-Library importieren (deprecated)
- Alembic-Migrationen nachträglich manipulieren nach Merge

**Ask First:**
- Soll Komoot im Rebuild-Scope bleiben (nur als GPX-Upload) oder auf späteren Plan verschoben werden?
- Soll Strava im Rebuild-Scope bleiben oder separater Plan?
- Sollen Tests parallel zur Feature-Implementation gebaut werden (TDD) oder am Ende als Nachzieh-Wave?

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Begründung |
|--------------|---------|-----------|------------|
| ORM | Flask-SQLAlchemy 3.x (DeclarativeBase) | Raw SQLite, Peewee | Alembic-Integration, Community, App Factory-Pattern |
| Auth | Flask-Login | custom Session, Flask-Security | Single-Purpose, leichtgewichtig, Community |
| KDF | HKDF (RFC 5869) | PBKDF2, Scrypt | Key-to-Key-Ableitung, SECRET_KEY ist hochentropisch |
| Feld-Encryption | Fernet (cryptography) | SQLCipher | Application-Level, keine Build-Dependency |
| Passwort-Hash | scrypt:131072:8:1 (OWASP) | Werkzeug-Default 2^15, bcrypt, Argon2id | OWASP-konform, keine C-Extension nötig |
| Rollen-Modell | String-Feld + is_admin-Property | Flask-Principal, Rollen-Tabelle | 2 Rollen reichen, simpel und auditierbar |
| RBAC-Decorator | admin_required verkettet login_required intern | separates Stacking | DX-Gewinn, weniger Fehler bei POST-Routen |
| Connector-Pattern | ABC + Registry-Decorator | typing.Protocol | Laufzeit-Enforcement, klare Fehlermeldungen |
| Token-Isolation | `GARMIN_TOKEN_DIR/<user_id>/` | Globaler Token-Dir | Multi-User-Sicherheit |
| Samsung Health | GESTRICHEN | — | Kein Web-API (WebSearch-Bestätigung) |
| Komoot | Entweder GPX-Upload ODER experimentell-Connector | Komoot als First-Class | ToS-Risiko, API instabil |
| CSRF | Flask-WTF global (CSRFProtect) | manuelles Token | Standard, auch für AJAX nutzbar |

---

## Issues

> Bestehende bd-Issues (`gvl`, `gdc`, `t65`) werden in die Struktur als Blatt-Knoten eingefädelt. Ihre Abhängigkeiten werden via `bd dep add` gesetzt.

### Wave 0 – Security Hotfixes (parallel, KEINE Deps)

Sofortige Härtung, ohne DB-Eingriffe. Ist unabhängig vom Rest durchführbar und reduziert Risiko im laufenden Betrieb.

**I-01 – `FLASK_DEBUG` env-basiert**
- Titel: DEBUG-Mode via Umgebungsvariable steuern
- Datei: `run.py`
- Änderung: `app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")`
- Akzeptanz: `FLASK_DEBUG=1 python run.py` → debug aktiv. Ohne Variable: debug aus.
- Risiko: reversible / local / autonomous-ok | Größe: XS

**I-02 – SECRET_KEY-Fallback entfernen**
- Titel: SECRET_KEY muss gesetzt sein – kein Fallback
- Datei: `config.py`
- Änderung: `SECRET_KEY = os.environ["SECRET_KEY"]` (KeyError wenn nicht gesetzt), Fehler-Meldung im README
- Akzeptanz: `unset SECRET_KEY && python -c "from config import Config"` → KeyError mit klarer Meldung
- Risiko: reversible / local / autonomous-ok | Größe: XS

**I-03 – garminconnect auf 0.3.3 upgraden**
- Titel: garminconnect 0.3.3 pinnen (Fix für Garmin-Breaking-Change 17.03.2026)
- Datei: `requirements.txt`
- Änderung: `garminconnect==0.3.3`
- Akzeptanz: `pip install -r requirements.txt && python -c "import garminconnect; print(garminconnect.__version__)"` → `0.3.3`
- Risiko: reversible / local / autonomous-ok | Größe: XS

---

### Wave 1 – Foundation (parallel, depends: Wave 0)

Extensions und Utilities, die alle weiteren Waves benötigen.

**I-04 – Requirements erweitern**
- Titel: Flask-SQLAlchemy, -Migrate, -Login, -WTF, -Limiter, cryptography hinzufügen
- Dateien: `requirements.txt`
- Akzeptanz: `pip install -r requirements.txt` läuft, alle Libs importierbar
- Risiko: reversible / local / autonomous-ok | Größe: S

**I-05 – Extensions-Modul**
- Titel: `app/extensions.py` mit `db`, `migrate`, `login_manager`, `csrf`, `limiter`
- Datei: `app/extensions.py` (NEU)
- Details: `db = SQLAlchemy(model_class=Base)` mit eigener `DeclarativeBase`; `login_manager.login_view = "auth.login"`
- Akzeptanz: `from app.extensions import db, migrate, login_manager, csrf, limiter` ohne Fehler
- Risiko: reversible / local / autonomous-ok | Größe: S

**I-06 – Crypto-Utils (HKDF + FernetField)**
- Titel: `app/utils/crypto.py` mit `derive_fernet_key()` (HKDF) und `FernetField` (SQLAlchemy-TypeDecorator)
- Dateien: `app/utils/__init__.py` (NEU), `app/utils/crypto.py` (NEU)
- Details: HKDF mit SHA256, fester Context-Salt `b"sport-challenge-v1"`, info-Parameter für Domain-Separation
- Akzeptanz: Unit-Test zeigt Encrypt/Decrypt-Roundtrip über FernetField
- Risiko: reversible / local / autonomous-ok | Größe: M

**I-07 – Config erweitern**
- Titel: SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, DEBUG via env
- Datei: `config.py`
- Änderung: Config-Klasse um DB-URI erweitern (`sqlite:///sport-challenge.db` default)
- Akzeptanz: `from config import Config; Config.SQLALCHEMY_DATABASE_URI` liefert String
- Risiko: reversible / local / autonomous-ok | Größe: XS

---

### Wave 2 – User & Migrations (nach Wave 1)

**I-08 – User-Model** 🔗 **blocks: t65, gvl**
- Titel: User-Model mit UserMixin, is_admin-Property, set/check_password
- Datei: `app/models/user.py` (NEU), `app/models/__init__.py` (NEU)
- Details: `role: Mapped[str]`, `is_admin: bool` als `@property`, `set_password(pw)` nutzt `scrypt:131072:8:1` (= gvl), `check_password()`, UserMixin für Flask-Login
- Akzeptanz: `User(email="x", ...).set_password("p"); u.check_password("p") is True`; `u.is_admin` wenn `role="admin"`
- Risiko: reversible / local / autonomous-ok | Größe: M

**I-09 – App Factory: Extensions initialisieren**
- Titel: `create_app()` initialisiert db, migrate, login_manager, csrf, limiter
- Datei: `app/__init__.py`
- Details: `db.init_app(app)`, `migrate.init_app(app, db)`, `login_manager.init_app(app)`, `csrf.init_app(app)`, User-Loader registrieren
- Akzeptanz: `from app import create_app; app = create_app()` läuft, alle Extensions aktiv
- Risiko: reversible / system / autonomous-ok | Größe: S

**I-10 – Initial Migration `users`**
- Titel: Alembic init + erste Migration für users-Tabelle
- Dateien: `migrations/` (NEU via `flask db init`)
- Details: `flask db init && flask db migrate -m "users table" && flask db upgrade`
- Akzeptanz: SQLite-DB existiert, Tabelle `users` mit allen Columns
- Risiko: irreversible / local / requires-approval | Größe: S

---

### Wave 3 – Auth + CSRF (nach Wave 2)

**I-11 – Auth-Blueprint Rewrite (Login + Register + Logout)**
- Titel: Flask-Login-basierte Auth, Logout als POST
- Datei: `app/routes/auth.py` (REWRITE)
- Details: `/auth/login` (GET+POST), `/auth/register` (GET+POST), `/auth/logout` (POST-only). `login_user()` / `logout_user()` aus Flask-Login. Kein custom Decorator mehr.
- Akzeptanz: Login mit gültigen Creds → current_user.is_authenticated. Logout via GET → 405. Register legt User an.
- Risiko: reversible / system / requires-approval | Größe: M

**I-12 – Login/Register/Base Templates mit CSRF**
- Titel: Auth-Templates auf Flask-Login + CSRF-Token umstellen
- Dateien: `app/templates/base.html`, `app/templates/auth/login.html`, `app/templates/auth/register.html` (NEU)
- Details: `{{ form.csrf_token }}` in jedem Form; base.html Navbar zeigt `current_user.email` oder Login-Link
- Akzeptanz: Formulare rendern CSRF-Token, POST ohne Token → 400
- Risiko: reversible / local / autonomous-ok | Größe: S

**I-13 – t65: admin_required verkettet login_required** *(bestehendes Issue)* 🔗 **depends: I-08**
- Existiert als `sport-challenge-t65`. Dependency auf User-Model setzen.
- Datei: `app/utils/decorators.py` (NEU)
- Akzeptanz: `@admin_required` reicht allein, `@login_required` wird intern verkettet. Non-Admin → 403, Anonym → 401-Redirect
- Risiko: reversible / local / autonomous-ok | Größe: S

---

### Wave 4 – Connector-Core (nach Wave 3)

**I-14 – BaseConnector ABC + Registry**
- Titel: Abstract Base Class mit Provider-Registry
- Dateien: `app/connectors/__init__.py` (NEU), `app/connectors/base.py` (NEU)
- Details: ABC mit `connect()`, `get_activities()`, `disconnect()`, Class-Attribute `provider_type`, `display_name`, `credential_fields`. Registry via `@register`-Decorator.
- Akzeptanz: `PROVIDER_REGISTRY` ist dict, eine abstrakte Subklasse ohne Implementation wirft TypeError
- Risiko: reversible / local / autonomous-ok | Größe: M

**I-15 – ConnectorCredential-Model**
- Titel: Model mit Fernet-verschlüsselten Feldern für Provider-Credentials
- Datei: `app/models/connector.py` (NEU)
- Details: `user_id: ForeignKey(User)`, `provider_type: str`, `credentials: FernetField(JSON)`, `created_at`, `updated_at`; Unique-Constraint (user_id, provider_type)
- Akzeptanz: DB speichert verschlüsselt (Rohabfrage zeigt Fernet-Token), Python-Access gibt dict zurück
- Risiko: reversible / local / autonomous-ok | Größe: M

**I-16 – Migration `connector_credentials`**
- Titel: Alembic-Migration für ConnectorCredential-Tabelle
- Dateien: `migrations/versions/*.py` (NEU via autogenerate)
- Akzeptanz: `flask db upgrade` legt Tabelle an, Downgrade funktioniert
- Risiko: irreversible / local / requires-approval | Größe: XS

---

### Wave 5 – GarminConnector (nach Wave 4)

**I-17 – GarminConnector-Implementation** 🔗 **blocks: gdc**
- Titel: GarminConnector wrapped GarminClient, pro-User Token-Isolation
- Datei: `app/connectors/garmin.py` (NEU)
- Details: `@register`-Decorator, `provider_type = "garmin"`, `credential_fields = [{email}, {password}]`. `connect()` instanziiert GarminClient mit `token_dir = f"{GARMIN_TOKEN_DIR}/{user_id}"`. `get_activities(start, end)` delegiert an `client.get_week_activities()`.
- Akzeptanz: Unit-Test mit Mock-GarminClient zeigt korrekte Delegation + Token-Pfad
- Risiko: reversible / system / autonomous-ok | Größe: M

**I-18 – gdc: Retry-Decorator für 429** *(bestehendes Issue)* 🔗 **depends: I-17**
- Existiert als `sport-challenge-gdc`. Dependency auf GarminConnector setzen.
- Datei: `app/utils/retry.py` (NEU)
- Akzeptanz: Decorator retryt NUR `GarminConnectTooManyRequestsError`, 60s → 120s → fail
- Risiko: reversible / local / autonomous-ok | Größe: S

**I-19 – Connector-UI (Verbinden + Status)**
- Titel: Routes + Templates für Connector-Management
- Dateien: `app/routes/connectors.py` (NEU), `app/templates/connectors/index.html` (NEU), `app/templates/connectors/connect.html` (NEU)
- Details: `/connectors/` listet alle registrierten Provider + User-Status (verbunden/nicht). `/connectors/<provider>/connect` zeigt dynamisches Formular basierend auf `credential_fields`. Auf POST: Credentials verschlüsselt speichern.
- Akzeptanz: User kann sich mit Garmin verbinden, DB enthält verschlüsselte Credentials, UI zeigt "verbunden"-Status
- Risiko: reversible / system / requires-approval | Größe: L

---

### Wave 6 – Activities auf Connector umbauen (nach Wave 5)

**I-20 – Activities-Route auf Connector-Abstraction**
- Titel: `/activities/week` nutzt GarminConnector via Registry statt direktem GarminClient
- Datei: `app/routes/activities.py`
- Details: Connector-Credentials aus DB laden (nur eigene, `user_id=current_user.id`), entschlüsseln, an GarminConnector übergeben, Activities holen. Bei keinem verbundenen Provider: Redirect zu `/connectors/`.
- Akzeptanz: Activities-Ansicht funktioniert mit Connector-Abstraction, Session-basierter Zugriff entfällt
- Risiko: reversible / system / requires-approval | Größe: M

---

### Wave 7 – Hardening (parallel, nach Wave 3+2)

**I-21 – Flask-Limiter am Login-Endpoint** 🔗 **blocks: gvl**
- Titel: Flask-Limiter initialisieren + `/auth/login` rate-limiten (5/min/IP)
- Dateien: `app/extensions.py`, `app/routes/auth.py`
- Details: `limiter.init_app(app)` in App Factory. `@limiter.limit("5 per minute")` auf Login-Route. Storage: Memory (lokal), Redis als optionaler Upgrade-Pfad
- Akzeptanz: 6. Login-Versuch innerhalb einer Minute → 429
- Risiko: reversible / system / autonomous-ok | Größe: S

**I-22 – gvl: OWASP scrypt:131072:8:1** *(bestehendes Issue)* 🔗 **depends: I-08, I-21**
- Existiert als `sport-challenge-gvl`. Dependencies auf User-Model + Flask-Limiter setzen.
- Akzeptanz: `set_password()` nutzt explizit `scrypt:131072:8:1`, alte Hashes werden beim nächsten Login rehashed
- Risiko: reversible / local / autonomous-ok | Größe: S

---

### Wave 8 – Tests (parallel ab Wave 3)

**I-23 – pytest + Flask-Fixtures Setup**
- Titel: pytest, pytest-flask, Test-App-Fixture, In-Memory-SQLite
- Dateien: `tests/__init__.py` (NEU), `tests/conftest.py` (NEU), `requirements.txt`, `pytest.ini` (NEU)
- Akzeptanz: `pytest` läuft, App-Fixture liefert Test-App mit In-Memory-DB
- Risiko: reversible / local / autonomous-ok | Größe: S

**I-24 – Auth-Flow-Tests**
- Titel: Login/Register/Logout + CSRF-Tests
- Datei: `tests/test_auth.py` (NEU)
- Tests: `test_register_creates_user`, `test_login_with_valid_credentials`, `test_login_rate_limited`, `test_logout_get_returns_405`, `test_csrf_missing_returns_400`
- Akzeptanz: alle Tests grün
- Risiko: reversible / local / autonomous-ok | Größe: M

**I-25 – Connector-Tests**
- Titel: BaseConnector ABC + GarminConnector-Unit-Tests
- Datei: `tests/test_connectors.py` (NEU)
- Tests: `test_base_connector_abstract`, `test_registry_registers_provider`, `test_garmin_connector_token_path_per_user`, `test_credential_fernet_roundtrip`
- Akzeptanz: alle Tests grün
- Risiko: reversible / local / autonomous-ok | Größe: M

---

### Optional Phases (nicht im Rebuild-Scope ohne explizite Freigabe)

- **Strava-OAuth2-Integration** – eigenes Planning-Dokument
- **Komoot GPX-Upload** – eigenes Planning-Dokument
- **Garmin MFA-Callback im Flask-Request-Cycle** – braucht Prototyping
- **Admin-Panel** – User-Listen, Rollen-Verwaltung, Logs

---

## Wave-Struktur (DAG)

```
Wave 0 (parallel, no deps):
  I-01 (FLASK_DEBUG)
  I-02 (SECRET_KEY)
  I-03 (garminconnect 0.3.3)

Wave 1 (depends: Wave 0, parallel untereinander):
  I-04 (Requirements)
  I-05 (Extensions)    [depends: I-04]
  I-06 (Crypto-Utils)  [depends: I-04]
  I-07 (Config)

Wave 2 (depends: Wave 1):
  I-08 (User-Model)    [depends: I-05, I-06]
  I-09 (App Factory)   [depends: I-05]
  I-10 (Migration)     [depends: I-08, I-09]

Wave 3 (depends: Wave 2):
  I-11 (Auth Rewrite)  [depends: I-08, I-09]
  I-12 (Templates)     [depends: I-11]
  I-13 / t65 (admin_required) [depends: I-08]

Wave 4 (depends: Wave 3):
  I-14 (BaseConnector) [depends: I-09]
  I-15 (CredentialModel)[depends: I-06, I-08]
  I-16 (Migration)     [depends: I-15]

Wave 5 (depends: Wave 4):
  I-17 (GarminConnector)[depends: I-14, I-15]
  I-18 / gdc (Retry)   [depends: I-17]
  I-19 (Connector-UI)  [depends: I-17]

Wave 6 (depends: Wave 5):
  I-20 (Activities Refactor) [depends: I-17, I-19]

Wave 7 (parallel ab Wave 3):
  I-21 (Flask-Limiter) [depends: I-11]
  I-22 / gvl (OWASP scrypt) [depends: I-08, I-21]

Wave 8 (parallel ab Wave 3):
  I-23 (pytest setup) [depends: I-09]
  I-24 (Auth-Tests)   [depends: I-11, I-23]
  I-25 (Connector-Tests) [depends: I-17, I-23]
```

**Bestehende Issues** (`gvl`, `gdc`, `t65`) bleiben als eigenständige bd-IDs erhalten, werden aber als Leaf-Knoten in Wave 3/5/7 eingehängt via `bd dep add`.

---

## Invalidation Risks

| Annahme | Risiko | Betroffene Issues |
|---------|--------|-------------------|
| garminconnect 0.3.3 bleibt stabil | Garmin kann weiter Breaking-Changes deployen | I-03, I-17 |
| Flask-SQLAlchemy 3.x + Python 3.14 kompatibel | Nicht getestet, aber keine bekannten Probleme | I-04, I-08 |
| HKDF mit festem Salt sicher | Nur bei hochentropischem SECRET_KEY (RFC 5869 §3.1) | I-06 |
| Fernet-Rotation nicht nötig | Kein Rotation-Mechanismus vorgesehen → wenn doch, nachträglich einbauen | I-06, I-15 |
| scrypt N=2^17 verträglich auf Dev-Maschine | ~128 MB RAM / Hash – bei vielen parallelen Logins Engpass | I-22 / gvl |

**Mitigierung:** Bei Auth-/Connector-Fehlern klare Fehlermeldung im UI statt Stack-Trace; Rate-Limiter verhindert Login-Overload.

---

## Rollback-Strategie

- **Pre-Rebuild-Tag:** `git tag pre-rebuild-2026-04-23` setzen
- **Pro Wave:** Feature-Branch, nach grünen Tests mergen; Revert via `git revert <merge-commit>` möglich
- **Migrations:** Jedes Issue mit Migration hat Downgrade → `flask db downgrade -1`
- **DB-Backup:** Vor Wave 2 (erste Migration) SQLite-Datei sichern (`cp sport-challenge.db sport-challenge.db.bak`)
- **Bestehende Issues unberührt:** `gvl/gdc/t65` bleiben als bd-Issues; bei Rollback einzelner Waves überleben sie im Tracker

---

## Offene Fragen vor Start

1. **Scope Strava/Komoot:** In diesem Rebuild eingeschlossen oder separater Plan?
2. **Testing-Strategie:** TDD (parallel zur Feature-Entwicklung in Wave 3–5) oder Nachzieh-Wave 8?
3. **DB-Reset:** Darf beim ersten `flask db upgrade` die bestehende SQLite-Datei verworfen werden, oder wollen wir Migration von Altdaten (gibt es nicht wirklich, da keine User persistent)?
4. **MFA-Flow für Garmin:** Jetzt einbauen oder als Folge-Issue (braucht Prototyping)?

---

## Status

- **Plan geschrieben:** ✅ 2026-04-23
- **bd-Issues angelegt:** ⏳ nach Kapitän-Freigabe
- **Wave 0 gestartet:** ⏳ nach Freigabe
