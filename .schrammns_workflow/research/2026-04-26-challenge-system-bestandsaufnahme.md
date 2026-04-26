# Research: Challenge-System – Bestandsaufnahme der Codebasis

**Date:** 2026-04-26
**Scope:** Vollständige Bestandsaufnahme der sport-challenge Codebasis als Grundlage für die Implementierung des Challenge-Systems

## Executive Summary

- Die App ist eine Flask-Anwendung mit App-Factory-Pattern, 5 Blueprints, 2 Models (User, ConnectorCredential) und Provider-Registry für Garmin/Strava-Connectors
- **Kein File-Upload** existiert – muss komplett neu gebaut werden (für Screenshot-Beweise)
- **Kein WTForms** – alle Formulare sind raw HTML mit manuellen CSRF-Tokens; dieses Pattern sollte beibehalten werden
- Frontend ist rein Bootstrap 5.3 via CDN, kein Build-Tooling, minimales JS – neue Templates können dem bestehenden Pattern folgen
- 41 Tests vorhanden (Auth, Approval, Connectors, Retry, Smoke, Strava) – gute Basis für Test-Erweiterung
- Connector-Architektur normalisiert Aktivitäten auf einheitliches Dict-Format – kann für den Import von Garmin/Strava-Aktivitäten in die Challenge genutzt werden

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | App Factory, Blueprint-Registrierung, Extension-Init |
| `app/extensions.py` | db, migrate, login_manager, csrf, limiter |
| `app/models/user.py` | User-Model mit scrypt-Hashing, Admin-Role, Approval |
| `app/models/connector.py` | ConnectorCredential mit Fernet-verschlüsseltem JSON |
| `app/connectors/__init__.py` | PROVIDER_REGISTRY + @register Decorator |
| `app/connectors/base.py` | BaseConnector ABC |
| `app/connectors/garmin.py` | GarminConnector (Token-basiert) |
| `app/connectors/strava.py` | StravaConnector (OAuth2) |
| `app/garmin/client.py` | GarminClient Wrapper um garminconnect-Lib |
| `app/routes/auth.py` | Login/Register/Logout mit Lockout |
| `app/routes/activities.py` | Wochenansicht (aktuell direkt via Connector) |
| `app/routes/connectors.py` | Connect/Disconnect für Provider |
| `app/routes/admin.py` | User-Verwaltung (Approve/Reject) |
| `app/routes/strava_oauth.py` | Strava OAuth2 Flow |
| `app/utils/crypto.py` | HKDF + FernetField TypeDecorator |
| `app/utils/decorators.py` | @admin_required |
| `app/utils/retry.py` | @retry_on_rate_limit |
| `app/templates/base.html` | Base-Template: Bootstrap 5.3, Navbar, Blocks: content + scripts |
| `config.py` | Config-Klasse (env-basiert, SECRET_KEY Pflicht) |
| `run.py` | Entry Point: load_dotenv() → create_app() |
| `tests/conftest.py` | Fixtures: app, client, db (In-Memory-SQLite) |

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| Flask | >=3.0 | Web-Framework |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| Flask-Migrate | 4.1.0 | Alembic-Wrapper |
| Flask-Login | 0.6.3 | Session/Auth |
| Flask-WTF | 1.3.0 | CSRF-Schutz |
| Flask-Limiter | 4.1.1 | Rate-Limiting |
| cryptography | 46.0.7 | Fernet + HKDF |
| garminconnect | 0.3.3 (pinned) | Garmin API |
| stravalib | (unpinned) | Strava API |
| Bootstrap | 5.3.3 (CDN) | Frontend-CSS/JS |
| SQLite | (built-in) | Datenbank |
| pytest | >=8.0 | Tests |

## Findings

### 1. App-Architektur (Depth: 4/4)

Flask App-Factory (`app/__init__.py`) mit deferred Extension-Init. Fünf Blueprints:
- `auth_bp` (`/auth`) – Login, Register, Logout (`app/routes/auth.py`)
- `activities_bp` (`/activities`) – Wochenansicht (`app/routes/activities.py`)
- `connectors_bp` (`/connectors`) – Connect/Disconnect (`app/routes/connectors.py`)
- `admin_bp` (`/admin`) – User-Verwaltung (`app/routes/admin.py`)
- `strava_oauth_bp` – OAuth2-Flow (`app/routes/strava_oauth.py`)

Root-Route `/` → Redirect zu `auth.login`.

### 2. Datenmodell (Depth: 4/4)

**User** (`users`): id, email, password_hash (scrypt N=2^17), role, created_at, is_approved, approved_at, approved_by_id, failed_login_attempts, locked_until. Properties: `is_active` = `is_approved`, `is_admin` = `role == "admin"`. Erster User = Admin + auto-approved.

**ConnectorCredential** (`connector_credentials`): id, user_id (FK), provider_type, credentials (_JsonFernetField), created_at, updated_at. UniqueConstraint(user_id, provider_type).

Keine Relationships definiert (kein `db.relationship()`), nur Foreign Keys.

### 3. Connector-System (Depth: 4/4)

Provider-Registry-Pattern mit `@register` Decorator. `BaseConnector` ABC definiert: `connect(credentials)`, `get_activities(start, end)`, `disconnect()`, `is_configured()`, `get_token_updates()`.

**Aktivitäts-Datenflow:** Route → ConnectorCredential aus DB → Connector instanziieren → `connect(cred.credentials)` → `get_activities(start, end)` → Normalisiertes Dict-Format → Template.

Normalisiertes Format (beide Provider):
```python
{
    "startTimeLocal": "2026-04-20 10:30:00",
    "activityName": "Morning Run",
    "activityType": {"typeKey": "running"},
    "duration": 1800.0,  # Sekunden
    "distance": 5000.0,  # Meter
    "averageHR": 145.0,
    "calories": 350.0
}
```

### 4. Frontend (Depth: 3/4)

7 Templates, alle erben von `base.html`. Bootstrap 5.3.3 via CDN. Keine lokalen Static-Assets, kein Build-Tooling. Zwei Block-Extension-Points: `content` und `scripts`.

Navbar: Dark-Theme, Brand "Sport Challenge", Settings-Dropdown (⚙) mit Connectors + Admin (konditional), separater Logout-Button.

**Potentielles Problem:** Flash-Message-Handling inkonsistent – `base.html` konsumiert Messages ohne Kategorien, Connector-Templates versuchen kategorisierte Messages zu nutzen. Da base.html zuerst rendert, werden Messages dort als `alert-info` konsumiert.

### 5. Security (Depth: 3/4)

- Passwort: scrypt N=2^17 (OWASP)
- Credentials: Fernet via HKDF-SHA256 aus SECRET_KEY
- CSRF: Flask-WTF auf allen POST-Forms
- Rate-Limiting: 3/min Register, 5/min Login
- Lockout: 10 Fehlversuche → 10 Min Sperre
- Admin-Approval: Neue User müssen freigeschalten werden
- SECRET_KEY-Validierung beim Startup

### 6. File-Upload (Depth: 4/4)

**Existiert nicht.** Kein `enctype="multipart/form-data"`, kein `request.files`, kein Upload-Verzeichnis, keine Datei-Validierung. Muss komplett neu gebaut werden.

### 7. Test-Suite (Depth: 3/4)

41 Tests in 6 Dateien. In-Memory-SQLite, CSRF disabled in Tests. Abdeckung: Auth (6), Approval (9), Connectors (9), Strava (10), Retry (6), Smoke (1). Kein Playwright/E2E. Keine Test-Abdeckung für Activities-Route (nur Smoke-Test prüft Server-Start).

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| App-Architektur | 4 | Vollständig verstanden: Factory, Blueprints, Extensions |
| Datenmodell | 4 | Alle Felder, Constraints, Encryption verstanden |
| Connector-System | 4 | Beide Provider, Registry, Datenflow komplett klar |
| Frontend/Templates | 3 | Alle Templates gelesen, Block-Struktur klar; Flash-Bug identifiziert |
| Security | 3 | Alle Maßnahmen verstanden; keine Penetration-Tests |
| File-Upload | 4 | Bestätigt: existiert nicht, muss neu gebaut werden |
| Test-Suite | 3 | Alle Tests gelesen, Patterns verstanden; Coverage-Lücken identifiziert |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Maximale Dateigröße für Screenshot-Upload | must-fill | Klären mit Käpt'n: Limit? Speicherort (lokal vs. S3)? |
| Flash-Message-Bug in Connector-Templates | nice-to-have | Prüfen ob base.html Messages vor Child-Templates konsumiert |
| Activities-Route hat keine Tests | nice-to-have | Beim Challenge-Bau mittesten |
| SQLite-Limits bei vielen Aktivitäten | nice-to-have | Performance-Test bei ~100 Usern × 12 Wochen |

## Anforderung: Responsive Design (Mobile-First)

Die Anwendung muss auf Smartphones gut bedienbar sein. Bootstrap 5.3 liefert das Responsive-Grid, aber alle neuen Templates müssen explizit mobile-optimiert werden:
- **Tabellen:** Horizontales Scrollen oder Card-Layout auf kleinen Screens (kein Overflow)
- **Formulare:** Touch-freundliche Input-Größen, ausreichend Padding
- **Dashboard/Leaderboard:** Kompakte Darstellung auf Mobile, ggf. gestapelt statt nebeneinander
- **Navigation:** Bestehende Navbar ist bereits responsive (Bootstrap `navbar-expand-lg`)
- **File-Upload:** Kamera-Zugriff via `accept="image/*"` auf Mobile-Geräten ermöglichen

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| SQLite bleibt als DB | Yes | `config.py` defaults to sqlite, keine andere DB-Config |
| Bootstrap 5.3 CDN bleibt | Yes | `base.html:4-8` |
| Kein WTForms, raw HTML Forms | Yes | Kein forms.py, alle Templates nutzen raw HTML |
| Provider-Registry erweiterbar | Yes | `@register` Decorator-Pattern in `connectors/__init__.py` |
| Fernet-Encryption für sensible Daten | Yes | `_JsonFernetField` in `connector.py` |
| Erste User = Admin | Yes | `auth.py` Registration-Logic |
| Screenshots lokal speichern (kein S3) | No | Noch nicht diskutiert – muss geklärt werden |

## Recommendations

### Neue Models (mindestens 6)
1. **Challenge** – Start/Enddatum, Name, Status, erstellt von Admin
2. **ChallengeParticipation** – User ↔ Challenge, individuelles Ziel (2x/3x), Status (invited/accepted/bailed_out), Bailout-Zeitpunkt
3. **Activity** – User, Challenge, Datum, Dauer (Minuten), Sportart (Freitext), optionaler Screenshot-Pfad, Quelle (manual/garmin/strava), externe Activity-ID
4. **SickWeek** – User, Challenge, KW/Startdatum der Woche
5. **BonusChallenge** – Challenge, Datum, Beschreibung
6. **BonusChallengeEntry** – User, BonusChallenge, Zeit (Sekunden)
7. **PenaltyOverride** – User, Challenge, KW, Override-Betrag, Grund, gesetzt von Admin

### Neue Blueprints/Routes
- `challenges_bp` – Challenge-CRUD (Admin), Einladungen, Annahme
- `challenge_activities_bp` – Aktivitäts-Eingabe (manuell + Connector-Import)
- `dashboard_bp` – Startseite mit Leaderboard

### File-Upload-Infrastruktur
- `app/static/uploads/` oder konfigurierbarer Pfad
- Erlaubte Typen: JPEG, PNG, (WebP?)
- Größenlimit festlegen (z.B. 5 MB)
- Dateinamen-Sanitisierung (UUID-basiert)
- Thumbnail-Generierung optional

### Nächster Schritt
→ `/set-course` für den Implementierungsplan mit konkreten Issues und Abhängigkeiten
