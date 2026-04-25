# Sport Challenge

Flask-Webanwendung zur Anzeige von Fitness-Aktivitäten aus Garmin Connect – mit Multi-User-Support und Connector-Architektur.

## Was macht dieses Projekt?

- Nutzer registrieren sich und verbinden ihren Garmin-Account
- Die Wochenansicht zeigt alle Aktivitäten (mit optionalem 30-Minuten-Filter)
- Connector-Architektur erlaubt spätere Erweiterung auf weitere Provider (Strava, Polar, …)
- Credentials werden Fernet-verschlüsselt in der DB gespeichert; Passwörter mit scrypt N=2^17 gehasht

## Lokale Entwicklung

### Voraussetzungen

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) für venv-Management

### Setup

```bash
# 1. venv erstellen und Dependencies installieren
uv venv .venv --python 3.14
uv pip install -r requirements.txt

# 2. Datenbank initialisieren
FLASK_APP=run.py SECRET_KEY=dev .venv/bin/flask db upgrade

# 3. Dev-Server starten
SECRET_KEY=dev FLASK_DEBUG=1 .venv/bin/python run.py
```

**Pflicht-Umgebungsvariablen:**

| Variable | Beschreibung |
|---|---|
| `SECRET_KEY` | Flask Secret Key – **Pflichtfeld**, App startet nicht ohne diesen Key |
| `FLASK_DEBUG` | Optional: `1` für Debug-Modus |

> **Hinweis:** Nach Projektumzug (Ordner umbenennen/verschieben) ist das `.venv` durch gebrochene Shebangs unbrauchbar.  
> Fix: `uv venv .venv --clear --python 3.14 && uv pip install -r requirements.txt`

### Tests

```bash
.venv/bin/pytest -v
```

22 Tests (Auth, Connector, Retry, Smoke) – kein externer Service nötig.

### Schnell-Check für neue Sessions

```bash
./scripts/verify-handover.sh
```

## Architektur

```
app/
├── __init__.py          # App Factory
├── extensions.py        # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── user.py          # User + UserMixin, scrypt-Hashing
│   └── connector.py     # ConnectorCredential mit Fernet-Encryption
├── connectors/
│   ├── base.py          # BaseConnector ABC
│   ├── __init__.py      # PROVIDER_REGISTRY + @register
│   └── garmin.py        # GarminConnector (Tokens Fernet-verschlüsselt in DB)
├── routes/
│   ├── auth.py          # Login/Register/Logout, Rate-Limit
│   ├── activities.py    # /activities/week – Wochenansicht
│   └── connectors.py    # /connectors/ – Verbinden + Status
├── utils/
│   ├── crypto.py        # HKDF-Key-Derivation + FernetField TypeDecorator
│   ├── decorators.py    # admin_required
│   └── retry.py         # @retry_on_rate_limit (exponential backoff)
└── templates/
    ├── activities/
    └── connectors/
migrations/              # Alembic-Migrationen
tests/                   # pytest, In-Memory-SQLite
```

**Datenfluss Aktivitäten-Abruf:**

1. User ruft `/activities/week` auf
2. Route lädt `ConnectorCredential` für `current_user` (Fernet-entschlüsselt)
3. `GarminConnector` wird aus `PROVIDER_REGISTRY` instanziiert
4. `connector.connect(credentials)` → Token-basierter Reconnect (oder Erstlogin mit Credentials); ggf. refreshte Tokens werden verschlüsselt in DB gespeichert
5. `connector.get_activities(start, end)` → gefilterte Aktivitätsliste

## Weiterführend

- **Plan:** `.schrammns_workflow/plans/2026-04-23-sport-challenge-multi-user-rebuild.md`
- **Research:** `.schrammns_workflow/research/`
- **Lessons Learned:** `docs/lessons-learned.md`
- **AI-Agent-Kontext:** `CLAUDE.md`
