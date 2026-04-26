# Sport Challenge

Flask-Webanwendung für Fitness-Challenges mit Leaderboard, Strafberechnung und Connector-Integration (Garmin, Strava).

## Was macht dieses Projekt?

- **Challenge-System:** Admin erstellt Challenges mit Start-/Enddatum, lädt Teilnehmer ein, die individuell 2x oder 3x pro Woche ≥30 Min Sport als Ziel setzen
- **Leaderboard/Dashboard:** Wochenweise Übersicht aller Teilnehmer mit Farbcodierung (grün/gelb/rot), Krankmeldungen (🤒) und Spendentopf
- **Aktivitäts-Tracking:** Manuelles Eintragen (mit optionalem Screenshot-Upload) oder Import aus Garmin/Strava
- **Automatische Strafberechnung:** 5 €/verpasster Tag, Admin-Override möglich, Krankmeldung befreit wochenweise
- **Bonus-Challenges:** Admin-definierte Termine (z.B. 50 Squat Jumps), Zeiterfassung mit Ranking
- **Bailout-Option:** Teilnehmer können aussteigen (+25 € Gebühr), werden im Leaderboard ausgegraut
- **Connector-Architektur:** Garmin (Credentials-Form) und Strava (OAuth2) integriert; weitere Provider erweiterbar
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

**Optionale Umgebungsvariablen (Strava-Connector):**

| Variable | Beschreibung |
|---|---|
| `STRAVA_CLIENT_ID` | Client-ID der registrierten Strava-App |
| `STRAVA_CLIENT_SECRET` | Client-Secret der registrierten Strava-App |

> **Strava einrichten:** App unter [strava.com/settings/api](https://www.strava.com/settings/api) registrieren. Als Callback-URL `http://localhost:5000/strava/oauth/callback` (Dev) bzw. die eigene Domain eintragen. Ohne diese Keys bleibt Strava in der Connector-UI unsichtbar.

> **Hinweis:** Nach Projektumzug (Ordner umbenennen/verschieben) ist das `.venv` durch gebrochene Shebangs unbrauchbar.  
> Fix: `uv venv .venv --clear --python 3.14 && uv pip install -r requirements.txt`

### Tests

```bash
.venv/bin/pytest -v
```

68 Tests (Auth, Connector, Challenge, Aktivitäten, Penalty, Dashboard, Bonus) – kein externer Service nötig.

### Schnell-Check für neue Sessions

```bash
./scripts/verify-handover.sh
```

## Architektur

```
app/
├── __init__.py          # App Factory, 9 Blueprints
├── extensions.py        # db, migrate, login_manager, csrf, limiter
├── models/
│   ├── user.py          # User + UserMixin, scrypt-Hashing
│   ├── connector.py     # ConnectorCredential mit Fernet-Encryption
│   ├── challenge.py     # Challenge + ChallengeParticipation
│   ├── activity.py      # Activity (manuell/Garmin/Strava)
│   ├── sick_week.py     # SickWeek (wochenweise Krankmeldung)
│   ├── penalty.py       # PenaltyOverride (Admin-Korrektur)
│   └── bonus.py         # BonusChallenge + BonusChallengeEntry
├── connectors/
│   ├── base.py          # BaseConnector ABC
│   ├── __init__.py      # PROVIDER_REGISTRY + @register
│   ├── garmin.py        # GarminConnector (Credentials-Form, Tokens Fernet-verschlüsselt in DB)
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
│   ├── challenge_activities.py  # /challenge-activities/ – Eintragen, Meine Woche, Import
│   ├── dashboard.py     # /dashboard/ – Leaderboard
│   └── bonus.py         # /bonus/ – Bonus-Challenges + Einträge
├── utils/
│   ├── crypto.py        # HKDF-Key-Derivation + FernetField TypeDecorator
│   ├── decorators.py    # admin_required
│   ├── retry.py         # @retry_on_rate_limit (exponential backoff)
│   └── uploads.py       # Screenshot-Upload (UUID-Naming, Typ-Validierung, 5 MB)
└── templates/
    ├── base.html         # Bootstrap 5.3.3, Navbar mit Settings-Dropdown
    ├── activities/       # Connector-Wochenansicht
    ├── connectors/       # Connect/Disconnect
    ├── challenges/       # Erstellen, Detail, Übersicht
    ├── dashboard/        # Leaderboard-Tabelle
    └── bonus/            # Bonus-Challenges + Ranking
migrations/              # Alembic-Migrationen (9 Tabellen)
tests/                   # 68 pytest-Tests, In-Memory-SQLite
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
4. `connector.connect(credentials)` → Reconnect mit gespeicherten Tokens; abgelaufene Tokens werden automatisch refresht und verschlüsselt in DB gespeichert
5. `connector.get_activities(start, end)` → gefilterte Aktivitätsliste

**Connector-Verbindungsfluss (einmalig pro User):**

- **Garmin:** Nutzer gibt E-Mail + Passwort im Formular ein → Tokens werden verschlüsselt gespeichert
- **Strava:** Nutzer wird zu strava.com weitergeleitet → autorisiert die App → Callback speichert OAuth-Tokens verschlüsselt in DB

## Weiterführend

- **Plan (Challenge-System):** `.schrammns_workflow/plans/2026-04-26-challenge-system.md`
- **Plan (Multi-User Rebuild):** `.schrammns_workflow/plans/2026-04-23-sport-challenge-multi-user-rebuild.md`
- **Research:** `.schrammns_workflow/research/`
- **Lessons Learned:** `docs/lessons-learned.md`
- **AI-Agent-Kontext:** `CLAUDE.md`
