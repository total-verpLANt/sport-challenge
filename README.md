# Sport Challenge

Flask-Webanwendung für Fitness-Challenges mit Leaderboard, Strafberechnung und Connector-Integration (Garmin, Strava).

## Was macht dieses Projekt?

- **Challenge-System:** Admin erstellt Challenges mit Start-/Enddatum, lädt Teilnehmer ein, die individuell 2x oder 3x pro Woche ≥30 Min Sport als Ziel setzen
- **Leaderboard/Dashboard:** Wochenweise Übersicht aller Teilnehmer mit Farbcodierung (grün/gelb/rot), Krankmeldungen (🤒) und Spendentopf
- **Aktivitäts-Tracking:** Manuelles Eintragen (mit Foto-/Video-Upload) oder Import aus Garmin/Strava
- **Automatische Strafberechnung:** 5 €/verpasster Tag, Admin-Override möglich, Krankmeldung befreit wochenweise
- **Bonus-Challenges:** Admin-definierte Termine (z.B. 50 Squat Jumps), Zeiterfassung mit Ranking und Video-Beweis
- **Bailout-Option:** Teilnehmer können aussteigen (+25 € Gebühr), werden im Leaderboard ausgegraut
- **Connector-Architektur:** Garmin (Credentials-Form) und Strava (OAuth2) integriert; weitere Provider erweiterbar
- Credentials werden Fernet-verschlüsselt in der DB gespeichert; Passwörter mit scrypt N=2^17 gehasht

## Deployment (Docker)

Das Projekt wird als Docker-Image über Docker Hub bereitgestellt und per `docker compose` betrieben.

### Voraussetzungen

- Docker + Docker Compose Plugin
- Eine `.env`-Datei mit den nötigen Umgebungsvariablen (siehe unten)

### Starten

```bash
# Image holen
docker compose pull

# Container starten (Migrationen laufen automatisch)
docker compose up -d

# Logs beobachten
docker compose logs -f
```

### .env (Pflicht)

```
SECRET_KEY=<mind. 32 zufällige Zeichen>
DATABASE_URL=sqlite:///sport-challenge.db
FLASK_APP=run.py
GUNICORN_WORKERS=1
```

Optionale Vars für Strava:
```
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
```

> ⚠️ `.env` niemals ins Git-Repository einchecken. `SECRET_KEY` darf sich nie ändern – er ist die Basis der Fernet-Verschlüsselung aller Connector-Credentials.

### Volumes

| Host | Container | Inhalt |
|---|---|---|
| `./data/instance/` | `/app/instance/` | SQLite-Datenbank |
| `./data/uploads/` | `/app/app/static/uploads/` | Foto-/Video-Uploads |
| `./data/logs/` | `/app/logs/` | Access-Log (Rotating) |

### CI/CD

Pull Requests und Pushes auf `main` laufen durch Tests, Dependency-Audit (`pip-audit`) und statische Security-Prüfung (`bandit`). Jeder Push auf `main` baut danach automatisch ein neues Image via GitHub Actions und pusht es zu Docker Hub. Auf dem Server dann:

```bash
docker compose pull && docker compose up -d
```

### Migration von bare-metal auf Docker

Siehe `docs/prod-migration-guide.md`.

---

## Lokale Entwicklung

### Voraussetzungen

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) für venv-Management

### Setup

```bash
# 1. venv erstellen und Dev-Dependencies installieren
uv venv .venv --python 3.14
uv pip install -r requirements-dev.txt

# 2. Datenbank initialisieren
FLASK_APP=run.py SECRET_KEY=dev .venv/bin/flask db upgrade

# 3. Dev-Server starten
SECRET_KEY=dev FLASK_DEBUG=1 .venv/bin/python run.py
```

> **Hinweis:** Nach Projektumzug ist das `.venv` durch gebrochene Shebangs unbrauchbar.
> Fix: `uv venv .venv --clear --python 3.14 && uv pip install -r requirements-dev.txt`

### Tests

```bash
.venv/bin/pytest -v
```

158 Tests (Auth, Connector, Challenge, Aktivitäten, Penalty, Dashboard, Bonus) – kein externer Service nötig.

---

## Architektur

```
app/
├── __init__.py          # App Factory, 10 Blueprints
├── extensions.py        # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── user.py          # User + UserMixin, scrypt-Hashing
│   ├── connector.py     # ConnectorCredential mit Fernet-Encryption
│   ├── challenge.py     # Challenge + ChallengeParticipation
│   ├── activity.py      # Activity + ActivityMedia (Foto/Video)
│   ├── sick_week.py     # SickWeek (wochenweise Krankmeldung)
│   ├── penalty.py       # PenaltyOverride (Admin-Korrektur)
│   └── bonus.py         # BonusChallenge + BonusChallengeEntry
├── connectors/
│   ├── base.py          # BaseConnector ABC
│   ├── __init__.py      # PROVIDER_REGISTRY + @register
│   ├── garmin.py        # GarminConnector (Tokens Fernet-verschlüsselt in DB)
│   └── strava.py        # StravaConnector (OAuth2, Token-Refresh automatisch)
├── services/
│   ├── penalty.py       # Strafberechnung (wöchentlich + gesamt)
│   └── weekly_summary.py # Dashboard-Aggregation (Leaderboard-Daten)
├── routes/
│   ├── auth.py          # Login/Register/Logout, Rate-Limit
│   ├── activities.py    # /activities/week – Wochenansicht (Connector)
│   ├── connectors.py    # /connectors/ – Verbinden + Status
│   ├── strava_oauth.py  # /strava/oauth/ – OAuth2-Start + Callback
│   ├── admin.py         # /admin/ – Nutzerverwaltung
│   ├── challenges.py    # /challenges/ – Erstellen, Einladen, Annehmen, Bailout, Krankmeldung
│   ├── challenge_activities.py  # /challenge-activities/ – Eintragen, Meine Woche, Import, Medien
│   ├── dashboard.py     # /dashboard/ – Leaderboard
│   └── bonus.py         # /bonus/ – Bonus-Challenges + Einträge
├── utils/
│   ├── crypto.py        # HKDF-Key-Derivation + FernetField TypeDecorator
│   ├── decorators.py    # admin_required
│   ├── retry.py         # @retry_on_rate_limit (exponential backoff)
│   └── uploads.py       # Foto-/Video-Upload (UUID-Naming, 50 MB, ffprobe)
└── templates/
    ├── base.html         # Bootstrap 5.3.3, Navbar mit Settings-Dropdown
    ├── activities/       # Connector-Wochenansicht
    ├── connectors/       # Connect/Disconnect
    ├── challenges/       # Erstellen, Detail, Übersicht
    ├── dashboard/        # Leaderboard-Tabelle
    └── bonus/            # Bonus-Challenges + Ranking
migrations/              # Alembic-Migrationen (16 Versionen, 9 Tabellen)
tests/                   # 158 pytest-Tests, In-Memory-SQLite
```

**Datenfluss Challenge-System:**

1. Admin erstellt Challenge (`/challenges/create`) mit Name, Start-/Enddatum
2. Admin lädt Nutzer ein → `ChallengeParticipation` mit Status `invited`
3. Nutzer nimmt an → setzt individuelles Wochenziel (2x oder 3x), Status `accepted`
4. Nutzer trägt Aktivitäten ein (manuell oder Import aus Garmin/Strava)
5. `penalty.py` berechnet pro Woche: Tage mit ≥30 Min Gesamtdauer → verfehlte Tage × 5 €
6. `weekly_summary.py` aggregiert alle Daten für das Dashboard/Leaderboard
7. Dashboard zeigt Fortschritt aller Teilnehmer, Spendentopf, Bonus-Rankings

**Datenfluss Aktivitäten-Abruf (Connector):**

1. User ruft `/activities/week` auf
2. Route lädt `ConnectorCredential` für `current_user` (Fernet-entschlüsselt)
3. Passender Connector wird aus `PROVIDER_REGISTRY` instanziiert
4. `connector.connect(credentials)` → Reconnect mit gespeicherten Tokens
5. `connector.get_activities(start, end)` → gefilterte Aktivitätsliste

**Connector-Verbindungsfluss (einmalig pro User):**

- **Garmin:** Nutzer gibt E-Mail + Passwort im Formular ein → Tokens werden verschlüsselt gespeichert
- **Strava:** Nutzer wird zu strava.com weitergeleitet → autorisiert die App → Callback speichert OAuth-Tokens verschlüsselt in DB

## Weiterführend

- **Lessons Learned:** `docs/lessons-learned.md`
- **Migrations-Guide:** `docs/prod-migration-guide.md`
- **AI-Agent-Kontext:** `CLAUDE.md`
