# Research: Garmin Connect Python + Flask – Wochenansicht Aktivitäten

**Date:** 2026-04-23  
**Scope:** garminconnect-Bibliothek (cyberjunky), Auth-Flow, Activity-API, Flask Blueprints  
**Web Research:** Verfügbar  
**Semantic Analysis:** Nicht anwendbar (neues Projekt, kein lokaler Code)

---

## Executive Summary

- `garminconnect` v0.3.2 (April 2026) ist aktiv gepflegt und die beste Wahl für Python-Garmin-Integration
- Auth nutzt Garmin Mobile SSO (Android-App-Flow); `garth` ist **deprecated** und darf nicht mehr verwendet werden
- Kritisches Risiko: Garmin hat kürzlich (Issue #332, April 2026) die Auth-API geändert – frische Logins können fehlschlagen; Token-Reuse funktioniert noch
- `get_activities_by_date(startdate, enddate)` ist die richtige Methode für wochenbasierte Abfragen
- Flask Application Factory + Blueprints ist der empfohlene Ansatz für modulare Struktur

---

## Key Files (extern – Bibliothek)

| Quelle | Zweck |
|--------|-------|
| [github.com/cyberjunky/python-garminconnect](https://github.com/cyberjunky/python-garminconnect) | Haupt-Repo, README, example.py |
| [garminconnect/__init__.py](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/__init__.py) | Alle API-Methoden |
| [example.py](https://github.com/cyberjunky/python-garminconnect/blob/master/example.py) | Auth-Muster, Usage |
| [pypi.org/project/garminconnect](https://pypi.org/project/garminconnect/) | Aktuelle Version |

---

## Technology Stack

| Library/Framework | Version | Rolle |
|-------------------|---------|-------|
| `garminconnect` | 0.3.2 (2026-04-11) | Garmin Connect API-Wrapper |
| `Flask` | 3.x | Web-Framework |
| `python-dotenv` | aktuell | Credentials aus .env laden |
| `Bootstrap 5` | 5.x | UI-Styling (CDN) |

---

## Findings

### 1. Authentifizierung

**Flow:** Garmin Mobile SSO (Android App Client-ID), nicht Browser-basiert.

```python
from garminconnect import Garmin

garmin = Garmin(
    email=email,
    password=password,
    prompt_mfa=lambda: input("MFA code: ").strip(),
)
garmin.login(tokenstore_path)  # Tokens werden gespeichert/wiederverwendet
```

**Token Storage:**
- Default-Pfad: `~/.garminconnect/` → `garmin_tokens.json`
- Überschreibbar via `GARMINTOKENS`-Umgebungsvariable
- Automatische Token-Erneuerung vor jedem API-Call
- `login()` gibt `(None, None)` bei Erfolg zurück

**Kritisch:** `garth` ist deprecated (github.com/matin/garth, Discussion #222). Nicht verwenden.

**Bekannte Probleme:**
- Issue #332: Garmin änderte kürzlich ihre Auth-API, Fresh-Logins können scheitern
- Issue #312: MFA-Accounts haben Probleme mit OAuth1→OAuth2-Migration
- Login-Rate-Limiting (Issue #213): zu viele Login-Versuche → temporäre Sperre

**Empfehlung:** Token-Reuse implementieren; Login nur wenn nötig; Fehlerbehandlung für `GarminConnectAuthenticationError` einbauen.

### 2. Aktivitäten-API

**Methode für Wochenansicht:**

```python
def get_activities_by_date(
    startdate: str,    # ISO-Format: "2026-04-14"
    enddate: str | None = None,  # ISO-Format: "2026-04-20"
    activitytype: str | None = None,  # "running", "cycling", "swimming" …
    sortorder: str | None = None,
) -> list[dict[str, Any]]
```

**Paginierte Alternative (nicht für Datumsfilter geeignet):**
```python
def get_activities(start: int = 0, limit: int = 20, activitytype: str | None = None)
```

**Wöchentliche Aggregate:**
```python
get_weekly_steps(end: str, weeks: int = 52)
get_weekly_stress(end: str, weeks: int = 52)
get_weekly_intensity_minutes(start: str, end: str)
```

**Typische Activity-Felder** (aus API-Responses bekannt):
- `activityId`, `activityName`, `activityType.typeKey`
- `startTimeLocal`, `duration` (Sekunden), `distance` (Meter)
- `averageHR`, `maxHR`, `calories`
- `elevationGain`, `averageSpeed`

### 3. Flask Modulstruktur – Blueprints

**Empfohlenes Muster: Application Factory**

```python
# app/__init__.py
def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or "config.Config")
    
    from app.routes.activities import activities_bp
    app.register_blueprint(activities_bp, url_prefix="/activities")
    
    return app
```

**Blueprint-Beispiel:**
```python
# app/routes/activities.py
from flask import Blueprint, render_template
activities_bp = Blueprint("activities", __name__)

@activities_bp.route("/week")
def week_view():
    ...
```

**Best Practices:**
- Unique URL-Prefixe pro Blueprint (keine Überlappungen)
- Templates in `app/templates/<blueprint_name>/`
- Config aus Umgebungsvariablen (niemals hardcoded)

---

## Geplante Projektstruktur

```
sport-challenge/
├── app/
│   ├── __init__.py          # create_app() Factory
│   ├── garmin/
│   │   ├── __init__.py
│   │   └── client.py        # GarminClient-Wrapper (Login, Token-Reuse)
│   ├── routes/
│   │   └── activities.py    # Blueprint: /activities/week
│   └── templates/
│       └── activities/
│           └── week.html
├── .env                     # GARMIN_EMAIL, GARMIN_PASSWORD (in .gitignore!)
├── .gitignore
├── config.py
├── requirements.txt
└── run.py
```

---

## Depth Ratings

| Bereich | Rating | Notizen |
|---------|--------|---------|
| Auth-Flow garminconnect | 3 | Methoden-Signaturen gelesen, Issues analysiert |
| Activity-API Methoden | 3 | Signaturen bekannt, Felder teilweise inferiert |
| Token-Storage-Mechanismus | 3 | Verhalten dokumentiert |
| Flask Blueprint Pattern | 3 | Best Practices klar |
| Konkrete Activity-Response-Felder | 2 | Typische Felder bekannt, exaktes Schema nicht gelesen |
| Garmin MFA in Web-App | 1 | Unklar wie MFA in Web-Flow integriert werden soll |

---

## Knowledge Gaps

| Gap | Priorität | Wie füllen |
|-----|-----------|------------|
| Exaktes JSON-Schema einer Activity-Response | nice-to-have | `print(json.dumps(activity, indent=2))` beim ersten Run |
| MFA-Handling im Web-Kontext (kein Terminal) | must-fill | Session-basierter MFA-Flow nötig; ggf. pre-auth mit Token-Only |
| Garmin Rate-Limits für API-Calls | nice-to-have | Monitoring + Retry-Decorator |
| Issue #332 Status (Auth-Breakage) | must-fill | Vor Impl. prüfen ob 0.3.2 stabil ist |

---

## Assumptions

| Annahme | Verifiziert? | Evidenz |
|---------|-------------|---------|
| `garminconnect` 0.3.2 ist installierbar | Nein | PyPI-Seite zeigt 0.3.2 als latest |
| Token-Reuse funktioniert trotz Issue #332 | Teilweise | Bestehende Tokens sollen noch ~1 Jahr gültig sein |
| `get_activities_by_date` gibt Liste zurück | Ja | Signatur: `-> list[dict[str, Any]]` |
| Flask 3.x kompatibel mit Python 3.11+ | Ja | Flask-Docs |
| MFA nicht zwingend für ersten Login | Nein | Abhängig vom Garmin-Konto-Setup |

---

## Sicherheitshinweise

1. **Credentials**: Niemals `GARMIN_EMAIL`/`GARMIN_PASSWORD` hardcoden → `.env` + `.gitignore`
2. **Token-Datei**: `~/.garminconnect/garmin_tokens.json` enthält OAuth-Tokens → Dateisystem-Rechte prüfen (600)
3. **Session-Sicherheit**: Flask `SECRET_KEY` aus Umgebungsvariable, nie aus Code
4. **Rate-Limiting**: Login-Attempts zählen; zu viele Versuche → Garmin-Account-Sperre

---

## Recommendations

1. **Sofort**: `pip install garminconnect python-dotenv flask` testen – prüfen ob Auth in 0.3.2 funktioniert
2. **Phase 1**: GarminClient-Modul mit Token-Reuse + Wochenansicht via `get_activities_by_date`
3. **Phase 2**: Blueprint für Auth-Flow (Login-Seite im Browser falls MFA nötig)
4. **Phase 3**: Weitere Aktivitätstypen, Charts, Statistiken
5. **Alternative**: Falls garminconnect auth weiter bricht → Garmin Connect offizielle Developer API prüfen (OAuth2, aber limitiert)

---

## Quellen

- [cyberjunky/python-garminconnect – GitHub](https://github.com/cyberjunky/python-garminconnect)
- [garminconnect – PyPI](https://pypi.org/project/garminconnect/)
- [Issue #332 – Auth-Breakage April 2026](https://github.com/cyberjunky/python-garminconnect/issues/332)
- [garth Deprecation – Discussion #222](https://github.com/matin/garth/discussions/222)
- [Flask Blueprints – Offizielle Doku](https://flask.palletsprojects.com/en/stable/blueprints/)
- [Flask Large App Structure – DigitalOcean](https://www.digitalocean.com/community/tutorials/how-to-structure-a-large-flask-application-with-flask-blueprints-and-flask-sqlalchemy)
